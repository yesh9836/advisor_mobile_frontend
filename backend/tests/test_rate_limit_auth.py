from __future__ import annotations

import os
import socket
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api import deps as deps_module
from app.core.config import settings
from app.core.rate_limit import (
    get_rate_limit_metrics_snapshot,
    rate_limit_dependencies_available,
    reset_rate_limit_metrics,
)
from app.main import app
from app.services import audit_service, subscription_service


def _redis_tests_required() -> bool:
    return os.getenv("REQUIRE_REDIS_RATE_LIMIT_TESTS", "").strip().lower() in {"1", "true", "yes"}


def _is_redis_available(host: str = "127.0.0.1", port: int = 6379) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.2):
            return True
    except OSError:
        return False


@pytest.fixture
def redis_rate_limited_client(session_factory, monkeypatch: pytest.MonkeyPatch, tmp_path):
    if not rate_limit_dependencies_available():
        message = "Rate-limit dependencies are unavailable (fastapi-limiter/redis)"
        if _redis_tests_required():
            pytest.fail(message)
        pytest.skip(message)

    if not _is_redis_available():
        message = "Redis is not available on 127.0.0.1:6379"
        if _redis_tests_required():
            pytest.fail(message)
        pytest.skip(message)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_BACKEND", "redis")
    monkeypatch.setattr(settings, "REDIS_URL", "redis://127.0.0.1:6379/15")
    monkeypatch.setattr(settings, "RATE_LIMIT_PREFIX", f"lm:test:rl:{uuid4().hex}")
    monkeypatch.setattr(settings, "RATE_LIMIT_FAIL_OPEN", False)
    monkeypatch.setattr(settings, "RATE_LIMIT_LOGIN_TIMES", 2)
    monkeypatch.setattr(settings, "RATE_LIMIT_LOGIN_SECONDS", 60)
    monkeypatch.setattr(settings, "RATE_LIMIT_AUTH_PASSWORD_RESET_ROUTE_TIMES", 20)
    monkeypatch.setattr(settings, "RATE_LIMIT_AUTH_PASSWORD_RESET_ROUTE_SECONDS", 60)
    monkeypatch.setattr(settings, "PASSWORD_RESET_REQUESTS_PER_HOUR", 3)

    monkeypatch.setattr("app.db.session.SessionLocal", session_factory)
    monkeypatch.setattr(deps_module, "SessionLocal", session_factory)
    monkeypatch.setattr(audit_service, "SessionLocal", session_factory)
    monkeypatch.setattr(subscription_service, "SessionLocal", session_factory)

    def override_get_db():
        test_db = session_factory()
        try:
            yield test_db
        finally:
            test_db.close()

    app.dependency_overrides[deps_module.get_db] = override_get_db

    reset_rate_limit_metrics()
    with TestClient(app) as test_client:
        yield test_client
    reset_rate_limit_metrics()

    app.dependency_overrides.clear()


@pytest.mark.integration
def test_login_route_rate_limits_with_redis(redis_rate_limited_client):
    register_payload = {
        "email": "redis.login.limit@example.com",
        "password": "RedisLogin123!",
        "name": "Redis Login",
        "phone": "+13055559292",
    }
    register = redis_rate_limited_client.post("/api/v1/auth/register", json=register_payload)
    assert register.status_code == 201, register.text

    for _ in range(2):
        login = redis_rate_limited_client.post(
            "/api/v1/auth/login",
            json={"email": register_payload["email"], "password": register_payload["password"]},
        )
        assert login.status_code == 204, login.text

    blocked = redis_rate_limited_client.post(
        "/api/v1/auth/login",
        json={"email": register_payload["email"], "password": register_payload["password"]},
    )

    assert blocked.status_code == 429, blocked.text
    assert blocked.headers.get("retry-after") is not None

    metrics = get_rate_limit_metrics_snapshot()
    assert metrics.get("auth.login:limited", 0) >= 1


@pytest.mark.integration
def test_password_reset_route_limit_and_business_limit_both_apply(
    redis_rate_limited_client,
    monkeypatch: pytest.MonkeyPatch,
):
    user_payload = {
        "email": "redis.reset.route@example.com",
        "password": "RedisReset123!",
        "name": "Redis Reset Route",
        "phone": "+13055559393",
    }
    register = redis_rate_limited_client.post("/api/v1/auth/register", json=user_payload)
    assert register.status_code == 201, register.text

    monkeypatch.setattr(settings, "RATE_LIMIT_AUTH_PASSWORD_RESET_ROUTE_TIMES", 2)
    monkeypatch.setattr(settings, "RATE_LIMIT_AUTH_PASSWORD_RESET_ROUTE_SECONDS", 60)

    first = redis_rate_limited_client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": user_payload["email"]},
    )
    second = redis_rate_limited_client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": user_payload["email"]},
    )
    route_blocked = redis_rate_limited_client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": user_payload["email"]},
    )

    assert first.status_code == 202, first.text
    assert second.status_code == 202, second.text
    assert route_blocked.status_code == 429, route_blocked.text
    assert route_blocked.headers.get("retry-after") is not None

    monkeypatch.setattr(settings, "RATE_LIMIT_AUTH_PASSWORD_RESET_ROUTE_TIMES", 20)

    business_payload = {
        "email": "redis.reset.business@example.com",
        "password": "RedisResetBusiness123!",
        "name": "Redis Reset Business",
        "phone": "+13055559494",
    }
    business_register = redis_rate_limited_client.post("/api/v1/auth/register", json=business_payload)
    assert business_register.status_code == 201, business_register.text

    for _ in range(3):
        response = redis_rate_limited_client.post(
            "/api/v1/auth/password-reset/request",
            json={"email": business_payload["email"]},
        )
        assert response.status_code == 202, response.text

    business_blocked = redis_rate_limited_client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": business_payload["email"]},
    )

    assert business_blocked.status_code == 429, business_blocked.text
    assert "Too many password reset requests" in business_blocked.json()["detail"]
    assert business_blocked.headers.get("retry-after") is not None

    metrics = get_rate_limit_metrics_snapshot()
    assert metrics.get("auth.password_reset.request:limited", 0) >= 1
