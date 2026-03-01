import asyncio
from datetime import timedelta
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from starlette.requests import Request

from app.core import rate_limit as rate_limit_module
from app.core.config import Settings, settings
from app.core.rate_limit import (
    _enforce_endpoint_rate_limit,
    client_ip_identifier,
    get_rate_limit_metrics_snapshot,
    get_rate_limiter_status_snapshot,
    reset_rate_limit_metrics,
)
from app.core.security import get_password_hash, verify_password
from app.db.timezone import utcnow
from app.main import _resolve_openapi_docs_config
from app.models.notification import NotificationOutbox, NotificationOutboxWorkerHeartbeat
from app.models.purchase import (
    StripePlanCleanupOutbox,
    StripeWebhookInbox,
    StripeWebhookWorkerHeartbeat,
)
from app.utils.csv_generator import LEAD_CSV_HEADERS, LEAD_CSV_REQUIRED_VALUE_FIELDS


def _production_settings_kwargs(**overrides):
    kwargs = {
        "_env_file": None,
        "APP_ENV": "production",
        "SECRET_KEY": "z" * 40,
        "INITIAL_ADMIN_PASSWORD": "StrongAdmin#123",
        "DB_PASSWORD": "db-password-123",
        "STRIPE_SECRET_KEY": "sk_live_example_123",
        "STRIPE_WEBHOOK_SECRET": "whsec_example_123",
        "CORS_ORIGINS": ["https://app.example.com"],
        "FRONTEND_URL": "https://app.example.com",
        "CORS_ALLOW_METHODS": ["GET", "POST"],
        "CORS_ALLOW_HEADERS": ["Authorization", "Content-Type"],
        "AUTH_COOKIE_SECURE": True,
        "NOTIFICATION_EMAIL_PROVIDER": "smtp2go",
        "SMTP_HOST": "mail.smtp2go.com",
        "SMTP_PORT": 587,
        "SMTP_FROM_EMAIL": "noreply@example.com",
        "NOTIFICATION_SMS_PROVIDER": "twilio",
        "TWILIO_ACCOUNT_SID": "AC1234567890abcdef",
        "TWILIO_AUTH_TOKEN": "twilio-auth-token",
        "TWILIO_MESSAGING_SERVICE_SID": "MG1234567890abcdef",
    }
    kwargs.update(overrides)
    return kwargs


def _find_sensitive_health_keys(payload):
    found: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in {"error", "last_error"}:
                found.append(key)
            found.extend(_find_sensitive_health_keys(value))
    elif isinstance(payload, list):
        for item in payload:
            found.extend(_find_sensitive_health_keys(item))
    return found


@pytest.fixture(autouse=True)
def reset_rate_limit_observability():
    reset_rate_limit_metrics()
    rate_limit_module._STATE.redis_client = None
    rate_limit_module._STATE.ready = False
    rate_limit_module._STATE.last_init_attempt_at = None
    rate_limit_module._STATE.last_ready_at = None
    rate_limit_module._STATE.last_error = None
    rate_limit_module._STATE.last_error_at = None
    rate_limit_module._STATE.next_retry_at = None
    rate_limit_module._STATE.failure_count = 0
    rate_limit_module._STATE.last_backoff_seconds = 0.0
    yield
    reset_rate_limit_metrics()
    rate_limit_module._STATE.redis_client = None
    rate_limit_module._STATE.ready = False
    rate_limit_module._STATE.last_init_attempt_at = None
    rate_limit_module._STATE.last_ready_at = None
    rate_limit_module._STATE.last_error = None
    rate_limit_module._STATE.last_error_at = None
    rate_limit_module._STATE.next_retry_at = None
    rate_limit_module._STATE.failure_count = 0
    rate_limit_module._STATE.last_backoff_seconds = 0.0


@pytest.mark.unit
def test_production_settings_require_strong_secret_key():
    with pytest.raises(ValidationError):
        Settings(**_production_settings_kwargs(SECRET_KEY="weak-secret"))


@pytest.mark.unit
def test_production_settings_reject_wildcard_cors():
    with pytest.raises(ValidationError):
        Settings(**_production_settings_kwargs(CORS_ALLOW_METHODS=["*"]))


@pytest.mark.unit
def test_production_settings_require_smtp2go_email_provider():
    with pytest.raises(ValidationError):
        Settings(**_production_settings_kwargs(NOTIFICATION_EMAIL_PROVIDER="sendgrid"))


@pytest.mark.unit
def test_production_settings_require_smtp2go_host():
    with pytest.raises(ValidationError):
        Settings(**_production_settings_kwargs(SMTP_HOST="smtp.gmail.com"))


@pytest.mark.unit
def test_production_settings_require_twilio_sms_provider():
    with pytest.raises(ValidationError):
        Settings(**_production_settings_kwargs(NOTIFICATION_SMS_PROVIDER="noop"))


@pytest.mark.unit
def test_production_settings_require_twilio_sender_source():
    with pytest.raises(ValidationError):
        Settings(
            **_production_settings_kwargs(
                TWILIO_MESSAGING_SERVICE_SID=None,
                TWILIO_FROM_NUMBER=None,
            )
        )


@pytest.mark.unit
def test_production_settings_require_https_frontend_url():
    with pytest.raises(ValidationError):
        Settings(**_production_settings_kwargs(FRONTEND_URL="http://app.example.com"))


@pytest.mark.unit
def test_production_settings_reject_loopback_frontend_url():
    with pytest.raises(ValidationError):
        Settings(**_production_settings_kwargs(FRONTEND_URL="https://127.0.0.1"))


@pytest.mark.integration
def test_cors_allows_configured_origin(client):
    origin = settings.CORS_ORIGINS[0]
    response = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Authorization,Content-Type,X-CSRF-Token",
        },
    )
    assert response.status_code in (200, 204)
    assert response.headers.get("access-control-allow-origin") == origin
    assert "POST" in response.headers.get("access-control-allow-methods", "")


@pytest.mark.integration
def test_cors_blocks_untrusted_origin(client):
    response = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.headers.get("access-control-allow-origin") is None


@pytest.mark.integration
def test_cookie_auth_mutation_without_csrf_header_returns_403(client, plan_factory):
    register_payload = {
        "email": "csrf.missing@example.com",
        "password": "CsrfMissing123!",
        "name": "CSRF Missing",
        "phone": "+13055551010",
    }
    register = client.post("/api/v1/auth/register", json=register_payload)
    assert register.status_code == 201, register.text

    login = client.post(
        "/api/v1/auth/login",
        json={"email": register_payload["email"], "password": register_payload["password"]},
    )
    assert login.status_code == 204, login.text
    plan = plan_factory(stripe_price_id="price_csrf_missing")

    checkout = client.post("/api/v1/purchases/checkout", json={"package_id": plan.id})
    assert checkout.status_code == 403
    assert checkout.json()["detail"] == "CSRF token validation failed"


@pytest.mark.integration
def test_cookie_auth_mutation_with_csrf_header_succeeds(client):
    register_payload = {
        "email": "csrf.valid@example.com",
        "password": "CsrfValid123!",
        "name": "CSRF Valid",
        "phone": "+13055552020",
    }
    register = client.post("/api/v1/auth/register", json=register_payload)
    assert register.status_code == 201, register.text

    login = client.post(
        "/api/v1/auth/login",
        json={"email": register_payload["email"], "password": register_payload["password"]},
    )
    assert login.status_code == 204, login.text
    csrf_token = client.cookies.get(settings.AUTH_CSRF_COOKIE_NAME)
    assert csrf_token
    logout = client.post(
        "/api/v1/auth/logout",
        headers={settings.AUTH_CSRF_HEADER_NAME: csrf_token},
    )
    assert logout.status_code == 204, logout.text


@pytest.mark.integration
def test_cookie_auth_get_endpoints_do_not_require_csrf_header(client):
    register_payload = {
        "email": "csrf.get@example.com",
        "password": "CsrfGet123!",
        "name": "CSRF GET",
        "phone": "+13055553030",
    }
    register = client.post("/api/v1/auth/register", json=register_payload)
    assert register.status_code == 201, register.text

    login = client.post(
        "/api/v1/auth/login",
        json={"email": register_payload["email"], "password": register_payload["password"]},
    )
    assert login.status_code == 204, login.text

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200, me.text
    assert me.json()["email"] == register_payload["email"]


@pytest.mark.integration
def test_rate_limit_fail_closed_returns_503_when_backend_unavailable(client, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_BACKEND", "redis")
    monkeypatch.setattr(settings, "RATE_LIMIT_FAIL_OPEN", False)
    monkeypatch.setattr("app.core.rate_limit.is_rate_limiter_ready", lambda: False)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "WrongPass123!"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Rate limiting service unavailable"
    metrics = get_rate_limit_metrics_snapshot()
    assert metrics.get("auth.login:redis_unavailable") == 1


@pytest.mark.integration
def test_rate_limit_fail_open_allows_requests_when_backend_unavailable(client, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_BACKEND", "redis")
    monkeypatch.setattr(settings, "RATE_LIMIT_FAIL_OPEN", True)
    monkeypatch.setattr("app.core.rate_limit.is_rate_limiter_ready", lambda: False)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "WrongPass123!"},
    )

    assert response.status_code == 401
    metrics = get_rate_limit_metrics_snapshot()
    assert metrics.get("auth.login:redis_unavailable") == 1
    assert metrics.get("auth.login:allowed") == 1


@pytest.mark.integration
def test_health_live_endpoint_is_always_healthy(client):
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


@pytest.mark.integration
def test_health_ready_reports_503_when_database_probe_is_unhealthy(client, monkeypatch):
    monkeypatch.setattr(settings, "NOTIFICATIONS_ENABLED", True)
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_FAST_ACK_ENABLED", True)
    monkeypatch.setattr(
        "app.main._check_database_readiness",
        lambda: {"status": "unhealthy", "timeout_seconds": 2.0, "error": "db unavailable"},
    )

    response = client.get("/health/ready")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "unhealthy"
    assert payload["checks"]["database"]["status"] == "unhealthy"
    assert payload["checks"]["notification_outbox_pipeline"]["reason"] == "database_unavailable"
    assert payload["checks"]["stripe_webhook_pipeline"]["reason"] == "database_unavailable"
    assert payload["checks"]["stripe_cleanup_outbox_pipeline"]["reason"] == "database_unavailable"
    assert _find_sensitive_health_keys(payload) == []


@pytest.mark.integration
def test_health_ready_redacts_notification_worker_last_error(client, db, monkeypatch):
    monkeypatch.setattr(settings, "NOTIFICATIONS_ENABLED", True)
    monkeypatch.setattr(settings, "NOTIFICATION_OUTBOX_HEALTH_HEARTBEAT_MAX_AGE_SECONDS", 600)
    now = utcnow()
    db.add(
        NotificationOutboxWorkerHeartbeat(
            source="notification_outbox_worker",
            last_started_at=now,
            last_completed_at=now,
            last_success_at=now,
            last_error="provider outage",
        )
    )
    db.commit()

    response = client.get("/health/ready")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert _find_sensitive_health_keys(payload) == []


@pytest.mark.integration
def test_health_ready_includes_database_probe_status(client):
    response = client.get("/health/ready")

    assert response.status_code in (200, 503)
    payload = response.json()
    assert payload["checks"]["database"]["status"] in {"healthy", "unhealthy"}
    assert payload["checks"]["database"]["timeout_seconds"] > 0


@pytest.mark.unit
def test_openapi_docs_are_disabled_in_production_by_default(monkeypatch):
    monkeypatch.setattr(settings, "API_DOCS_ENABLED", True)
    monkeypatch.setattr(settings, "API_DOCS_IN_PRODUCTION", False)
    monkeypatch.setattr(settings, "APP_ENV", "production")

    openapi_url, docs_url, redoc_url = _resolve_openapi_docs_config()
    assert openapi_url is None
    assert docs_url is None
    assert redoc_url is None


@pytest.mark.unit
def test_openapi_docs_can_be_explicitly_enabled_in_production(monkeypatch):
    monkeypatch.setattr(settings, "API_DOCS_ENABLED", True)
    monkeypatch.setattr(settings, "API_DOCS_IN_PRODUCTION", True)
    monkeypatch.setattr(settings, "APP_ENV", "production")

    openapi_url, docs_url, redoc_url = _resolve_openapi_docs_config()
    assert openapi_url == "/api/openapi.json"
    assert docs_url == "/api/docs"
    assert redoc_url == "/api/redoc"


@pytest.mark.integration
def test_health_ready_reports_503_when_fail_closed_limiter_unavailable(client, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_BACKEND", "redis")
    monkeypatch.setattr(settings, "RATE_LIMIT_FAIL_OPEN", False)
    monkeypatch.setattr("app.core.rate_limit.is_rate_limiter_ready", lambda: False)

    response = client.get("/health/ready")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "unhealthy"
    assert payload["checks"]["rate_limiter"]["redis_backend_enabled"] is True
    assert payload["checks"]["rate_limiter"]["ready"] is False


@pytest.mark.integration
def test_health_ready_stays_healthy_when_fail_open_limiter_unavailable(client, monkeypatch):
    monkeypatch.setattr(settings, "NOTIFICATIONS_ENABLED", False)
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_FAST_ACK_ENABLED", False)
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_BACKEND", "redis")
    monkeypatch.setattr(settings, "RATE_LIMIT_FAIL_OPEN", True)
    monkeypatch.setattr("app.core.rate_limit.is_rate_limiter_ready", lambda: False)

    response = client.get("/health/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["checks"]["rate_limiter"]["fail_open"] is True


@pytest.mark.integration
def test_health_ready_reports_503_when_notifications_enabled_and_worker_heartbeat_missing(
    client,
    monkeypatch,
):
    monkeypatch.setattr(settings, "NOTIFICATIONS_ENABLED", True)
    monkeypatch.setattr(settings, "NOTIFICATION_OUTBOX_HEALTH_HEARTBEAT_MAX_AGE_SECONDS", 60)

    response = client.get("/health/ready")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "unhealthy"
    notification_check = payload["checks"]["notification_outbox_pipeline"]
    assert notification_check["enabled"] is True
    assert notification_check["status"] == "unhealthy"
    assert "worker_heartbeat_stale" in notification_check["breaches"]


@pytest.mark.integration
def test_health_ready_reports_503_when_notifications_due_backlog_exceeds_threshold(
    client,
    db,
    monkeypatch,
):
    monkeypatch.setattr(settings, "NOTIFICATIONS_ENABLED", True)
    monkeypatch.setattr(settings, "NOTIFICATION_OUTBOX_HEALTH_HEARTBEAT_MAX_AGE_SECONDS", 600)
    monkeypatch.setattr(settings, "NOTIFICATION_OUTBOX_HEALTH_MAX_DUE_PENDING_COUNT", 0)
    monkeypatch.setattr(settings, "NOTIFICATION_OUTBOX_HEALTH_MAX_OLDEST_DUE_PENDING_SECONDS", 3600)

    now = utcnow()
    db.add(
        NotificationOutboxWorkerHeartbeat(
            source="notification_outbox_worker",
            last_started_at=now,
            last_completed_at=now,
            last_success_at=now,
        )
    )
    db.add(
        NotificationOutbox(
            user_id=None,
            lead_id=None,
            purchase_id=None,
            channel="email",
            event_type="lead_delivered",
            recipient="advisor@example.com",
            subject="New lead",
            message_body="You have a new lead",
            payload=None,
            idempotency_key="health-ready-notification-due-backlog-1",
            status="pending",
            attempt_count=0,
            max_attempts=5,
            next_retry_at=now - timedelta(seconds=5),
        )
    )
    db.commit()

    response = client.get("/health/ready")

    assert response.status_code == 503
    payload = response.json()
    notification_check = payload["checks"]["notification_outbox_pipeline"]
    assert notification_check["status"] == "unhealthy"
    assert "due_pending_count_exceeded" in notification_check["breaches"]
    assert notification_check["queue"]["due_pending_count"] == 1


@pytest.mark.integration
def test_health_ready_stays_healthy_when_notification_pipeline_within_thresholds(
    client,
    db,
    monkeypatch,
):
    monkeypatch.setattr(settings, "NOTIFICATIONS_ENABLED", True)
    monkeypatch.setattr(settings, "NOTIFICATION_OUTBOX_HEALTH_HEARTBEAT_MAX_AGE_SECONDS", 600)
    monkeypatch.setattr(settings, "NOTIFICATION_OUTBOX_HEALTH_MAX_DUE_PENDING_COUNT", 100)
    monkeypatch.setattr(settings, "NOTIFICATION_OUTBOX_HEALTH_MAX_OLDEST_DUE_PENDING_SECONDS", 600)
    monkeypatch.setattr(settings, "NOTIFICATION_OUTBOX_HEALTH_MAX_FAILED_COUNT", 10)
    monkeypatch.setattr(settings, "NOTIFICATION_OUTBOX_HEALTH_MAX_STALE_LOCK_COUNT", 1)

    now = utcnow()
    db.add(
        NotificationOutboxWorkerHeartbeat(
            source="notification_outbox_worker",
            last_started_at=now,
            last_completed_at=now,
            last_success_at=now,
        )
    )
    db.add(
        NotificationOutbox(
            user_id=None,
            lead_id=None,
            purchase_id=None,
            channel="email",
            event_type="lead_delivered",
            recipient="advisor@example.com",
            subject="New lead",
            message_body="You have a new lead",
            payload=None,
            idempotency_key="health-ready-notification-not-due-1",
            status="pending",
            attempt_count=0,
            max_attempts=5,
            next_retry_at=now + timedelta(minutes=5),
        )
    )
    db.commit()

    response = client.get("/health/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    notification_check = payload["checks"]["notification_outbox_pipeline"]
    assert notification_check["enabled"] is True
    assert notification_check["status"] == "healthy"
    assert notification_check["breaches"] == []


@pytest.mark.integration
def test_health_ready_reports_503_when_fast_ack_enabled_and_worker_heartbeat_missing(client, monkeypatch):
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_FAST_ACK_ENABLED", True)
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_HEALTH_HEARTBEAT_MAX_AGE_SECONDS", 60)

    response = client.get("/health/ready")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "unhealthy"
    webhook_check = payload["checks"]["stripe_webhook_pipeline"]
    assert webhook_check["enabled"] is True
    assert webhook_check["status"] == "unhealthy"
    assert "worker_heartbeat_stale" in webhook_check["breaches"]


@pytest.mark.integration
def test_health_ready_reports_503_when_fast_ack_due_backlog_exceeds_threshold(client, db, monkeypatch):
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_FAST_ACK_ENABLED", True)
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_HEALTH_HEARTBEAT_MAX_AGE_SECONDS", 600)
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_HEALTH_MAX_DUE_PENDING_COUNT", 0)
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_HEALTH_MAX_OLDEST_DUE_PENDING_SECONDS", 3600)

    now = utcnow()
    db.add(
        StripeWebhookWorkerHeartbeat(
            source="stripe_webhook_inbox_worker",
            last_started_at=now,
            last_completed_at=now,
            last_success_at=now,
        )
    )
    db.add(
        StripeWebhookInbox(
            stripe_event_id="evt_ready_due_backlog",
            event_type="checkout.session.completed",
            payload={"id": "evt_ready_due_backlog"},
            status="pending",
            attempt_count=0,
            max_attempts=10,
            next_retry_at=now - timedelta(seconds=5),
        )
    )
    db.commit()

    response = client.get("/health/ready")

    assert response.status_code == 503
    payload = response.json()
    webhook_check = payload["checks"]["stripe_webhook_pipeline"]
    assert webhook_check["status"] == "unhealthy"
    assert "due_pending_count_exceeded" in webhook_check["breaches"]
    assert webhook_check["queue"]["due_pending_count"] == 1


@pytest.mark.integration
def test_health_ready_stays_healthy_when_fast_ack_webhook_pipeline_within_thresholds(
    client,
    db,
    monkeypatch,
):
    monkeypatch.setattr(settings, "NOTIFICATIONS_ENABLED", False)
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_FAST_ACK_ENABLED", True)
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_HEALTH_HEARTBEAT_MAX_AGE_SECONDS", 600)
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_HEALTH_MAX_DUE_PENDING_COUNT", 100)
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_HEALTH_MAX_OLDEST_DUE_PENDING_SECONDS", 600)
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_HEALTH_MAX_FAILED_COUNT", 10)
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_HEALTH_MAX_STALE_LOCK_COUNT", 1)
    monkeypatch.setattr(settings, "STRIPE_PLAN_CLEANUP_HEALTH_HEARTBEAT_MAX_AGE_SECONDS", 600)
    monkeypatch.setattr(settings, "STRIPE_PLAN_CLEANUP_HEALTH_MAX_DUE_PENDING_COUNT", 100)
    monkeypatch.setattr(settings, "STRIPE_PLAN_CLEANUP_HEALTH_MAX_OLDEST_DUE_PENDING_SECONDS", 600)
    monkeypatch.setattr(settings, "STRIPE_PLAN_CLEANUP_HEALTH_MAX_FAILED_COUNT", 10)
    monkeypatch.setattr(settings, "STRIPE_PLAN_CLEANUP_HEALTH_MAX_STALE_LOCK_COUNT", 1)

    now = utcnow()
    db.add(
        StripeWebhookWorkerHeartbeat(
            source="stripe_webhook_inbox_worker",
            last_started_at=now,
            last_completed_at=now,
            last_success_at=now,
        )
    )
    db.add(
        StripeWebhookWorkerHeartbeat(
            source="stripe_plan_cleanup_outbox_worker",
            last_started_at=now,
            last_completed_at=now,
            last_success_at=now,
        )
    )
    db.add(
        StripeWebhookInbox(
            stripe_event_id="evt_ready_not_due",
            event_type="checkout.session.completed",
            payload={"id": "evt_ready_not_due"},
            status="pending",
            attempt_count=0,
            max_attempts=10,
            next_retry_at=now + timedelta(minutes=5),
        )
    )
    db.commit()

    response = client.get("/health/ready")

    assert response.status_code in (200, 503)
    payload = response.json()
    webhook_check = payload["checks"]["stripe_webhook_pipeline"]
    assert webhook_check["enabled"] is True
    assert webhook_check["status"] == "healthy"
    assert webhook_check["breaches"] == []


@pytest.mark.integration
def test_health_ready_reports_503_when_fast_ack_cleanup_worker_heartbeat_missing(client, monkeypatch):
    monkeypatch.setattr(settings, "NOTIFICATIONS_ENABLED", False)
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_FAST_ACK_ENABLED", True)
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_HEALTH_HEARTBEAT_MAX_AGE_SECONDS", 600)
    monkeypatch.setattr(settings, "STRIPE_PLAN_CLEANUP_HEALTH_HEARTBEAT_MAX_AGE_SECONDS", 60)

    response = client.get("/health/ready")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "unhealthy"
    cleanup_check = payload["checks"]["stripe_cleanup_outbox_pipeline"]
    assert cleanup_check["enabled"] is True
    assert cleanup_check["status"] == "unhealthy"
    assert "worker_heartbeat_stale" in cleanup_check["breaches"]


@pytest.mark.integration
def test_health_ready_reports_503_when_fast_ack_cleanup_due_backlog_exceeds_threshold(
    client,
    db,
    monkeypatch,
):
    monkeypatch.setattr(settings, "NOTIFICATIONS_ENABLED", False)
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_FAST_ACK_ENABLED", True)
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_HEALTH_HEARTBEAT_MAX_AGE_SECONDS", 600)
    monkeypatch.setattr(settings, "STRIPE_PLAN_CLEANUP_HEALTH_HEARTBEAT_MAX_AGE_SECONDS", 600)
    monkeypatch.setattr(settings, "STRIPE_PLAN_CLEANUP_HEALTH_MAX_DUE_PENDING_COUNT", 0)
    monkeypatch.setattr(settings, "STRIPE_PLAN_CLEANUP_HEALTH_MAX_OLDEST_DUE_PENDING_SECONDS", 3600)

    now = utcnow()
    db.add(
        StripeWebhookWorkerHeartbeat(
            source="stripe_webhook_inbox_worker",
            last_started_at=now,
            last_completed_at=now,
            last_success_at=now,
        )
    )
    db.add(
        StripeWebhookWorkerHeartbeat(
            source="stripe_plan_cleanup_outbox_worker",
            last_started_at=now,
            last_completed_at=now,
            last_success_at=now,
        )
    )
    db.add(
        StripePlanCleanupOutbox(
            source="health_check_test",
            stripe_price_id="price_health_due",
            stripe_product_id=None,
            status="pending",
            attempt_count=0,
            max_attempts=10,
            next_retry_at=now - timedelta(seconds=5),
            idempotency_key="health-ready-cleanup-due-backlog-1",
        )
    )
    db.commit()

    response = client.get("/health/ready")

    assert response.status_code == 503
    payload = response.json()
    cleanup_check = payload["checks"]["stripe_cleanup_outbox_pipeline"]
    assert cleanup_check["status"] == "unhealthy"
    assert "due_pending_count_exceeded" in cleanup_check["breaches"]
    assert cleanup_check["queue"]["due_pending_count"] == 1


@pytest.mark.integration
def test_health_ready_stays_healthy_when_fast_ack_cleanup_pipeline_within_thresholds(
    client,
    db,
    monkeypatch,
):
    monkeypatch.setattr(settings, "NOTIFICATIONS_ENABLED", False)
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_FAST_ACK_ENABLED", True)
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_HEALTH_HEARTBEAT_MAX_AGE_SECONDS", 600)
    monkeypatch.setattr(settings, "STRIPE_PLAN_CLEANUP_HEALTH_HEARTBEAT_MAX_AGE_SECONDS", 600)
    monkeypatch.setattr(settings, "STRIPE_PLAN_CLEANUP_HEALTH_MAX_DUE_PENDING_COUNT", 100)
    monkeypatch.setattr(settings, "STRIPE_PLAN_CLEANUP_HEALTH_MAX_OLDEST_DUE_PENDING_SECONDS", 600)
    monkeypatch.setattr(settings, "STRIPE_PLAN_CLEANUP_HEALTH_MAX_FAILED_COUNT", 10)
    monkeypatch.setattr(settings, "STRIPE_PLAN_CLEANUP_HEALTH_MAX_STALE_LOCK_COUNT", 1)

    now = utcnow()
    db.add(
        StripeWebhookWorkerHeartbeat(
            source="stripe_webhook_inbox_worker",
            last_started_at=now,
            last_completed_at=now,
            last_success_at=now,
        )
    )
    db.add(
        StripeWebhookWorkerHeartbeat(
            source="stripe_plan_cleanup_outbox_worker",
            last_started_at=now,
            last_completed_at=now,
            last_success_at=now,
        )
    )
    db.add(
        StripePlanCleanupOutbox(
            source="health_check_test",
            stripe_price_id="price_health_not_due",
            stripe_product_id=None,
            status="pending",
            attempt_count=0,
            max_attempts=10,
            next_retry_at=now + timedelta(minutes=5),
            idempotency_key="health-ready-cleanup-not-due-1",
        )
    )
    db.commit()

    response = client.get("/health/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    cleanup_check = payload["checks"]["stripe_cleanup_outbox_pipeline"]
    assert cleanup_check["enabled"] is True
    assert cleanup_check["status"] == "healthy"
    assert cleanup_check["breaches"] == []


@pytest.mark.unit
def test_rate_limiter_outage_cooldown_avoids_repeat_redis_connect_attempts(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_BACKEND", "redis")
    monkeypatch.setattr(settings, "RATE_LIMIT_FAIL_OPEN", False)

    connect_attempts = {"count": 0}

    class DownRedisClient:
        async def ping(self) -> None:
            raise RuntimeError("redis unavailable")

        async def aclose(self) -> None:
            return None

    def fake_from_url(*args, **kwargs):
        connect_attempts["count"] += 1
        return DownRedisClient()

    monkeypatch.setattr(
        rate_limit_module,
        "redis_asyncio",
        SimpleNamespace(from_url=fake_from_url),
    )
    monkeypatch.setattr(rate_limit_module, "RateLimiter", object)
    monkeypatch.setattr(rate_limit_module, "rate_limit_dependencies_available", lambda: True)

    request = Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/api/v1/auth/login",
            "raw_path": b"/api/v1/auth/login",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 50000),
            "server": ("testserver", 80),
            "root_path": "",
        }
    )
    response = rate_limit_module.Response()

    with pytest.raises(rate_limit_module.HTTPException) as first_blocked:
        asyncio.run(
            _enforce_endpoint_rate_limit(
                endpoint="auth.login",
                times=5,
                seconds=60,
                request=request,
                response=response,
            )
        )
    assert first_blocked.value.status_code == 503
    assert connect_attempts["count"] == 1

    with pytest.raises(rate_limit_module.HTTPException) as second_blocked:
        asyncio.run(
            _enforce_endpoint_rate_limit(
                endpoint="auth.login",
                times=5,
                seconds=60,
                request=request,
                response=response,
            )
        )
    assert second_blocked.value.status_code == 503
    assert connect_attempts["count"] == 1

    status = get_rate_limiter_status_snapshot()
    assert status["ready"] is False
    assert status["failure_count"] == 1
    assert status["retry_cooldown_seconds"] > 0


@pytest.mark.unit
def test_get_client_identifier_uses_forwarded_for_only_for_trusted_proxy(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_TRUST_PROXY_HEADERS", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_TRUSTED_PROXIES", ["10.0.0.0/8"])

    request = Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/api/v1/auth/login",
            "raw_path": b"/api/v1/auth/login",
            "query_string": b"",
            "headers": [(b"x-forwarded-for", b"203.0.113.60")],
            "client": ("10.1.2.3", 50000),
            "server": ("testserver", 80),
            "root_path": "",
        }
    )

    assert client_ip_identifier(request) == "203.0.113.60"


@pytest.mark.unit
def test_password_hashing_runtime_supports_argon2():
    password = "Argon2Runtime123!"
    password_hash = get_password_hash(password)

    assert password_hash.startswith("$argon2")
    assert verify_password(password, password_hash) is True


@pytest.mark.unit
def test_get_client_identifier_ignores_forwarded_for_for_untrusted_proxy(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_TRUST_PROXY_HEADERS", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_TRUSTED_PROXIES", ["10.0.0.0/8"])

    request = Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/api/v1/auth/login",
            "raw_path": b"/api/v1/auth/login",
            "query_string": b"",
            "headers": [(b"x-forwarded-for", b"203.0.113.60")],
            "client": ("198.51.100.10", 50000),
            "server": ("testserver", 80),
            "root_path": "",
        }
    )

    assert client_ip_identifier(request) == "198.51.100.10"


@pytest.mark.unit
def test_get_client_identifier_uses_x_real_ip_for_trusted_proxy_when_forwarded_invalid(monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_TRUST_PROXY_HEADERS", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_TRUSTED_PROXIES", ["10.0.0.0/8"])

    request = Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/api/v1/auth/login",
            "raw_path": b"/api/v1/auth/login",
            "query_string": b"",
            "headers": [
                (b"x-forwarded-for", b"invalid"),
                (b"x-real-ip", b"203.0.113.70"),
            ],
            "client": ("10.2.3.4", 50000),
            "server": ("testserver", 80),
            "root_path": "",
        }
    )

    assert client_ip_identifier(request) == "203.0.113.70"


@pytest.mark.integration
def test_license_upload_rejects_content_mismatch(client, user_factory, auth_headers):
    advisor = user_factory(
        role="advisor",
        password="LicenseMismatch123!",
        email="advisor.license.mismatch@example.com",
        name="License Mismatch",
    )
    advisor_headers = auth_headers(advisor.email, "LicenseMismatch123!")

    response = client.post(
        "/api/v1/licenses/",
        headers=advisor_headers,
        data={"state": "CA", "license_number": "CA-LIC-MISMATCH", "license_type": "Series 65"},
        files={"document": ("license.png", b"not-a-real-png", "image/png")},
    )

    assert response.status_code == 400
    assert "does not match file type" in response.json()["detail"]


@pytest.mark.integration
def test_bulk_import_rejects_non_csv_upload(client, user_factory, auth_headers):
    admin = user_factory(
        role="admin",
        password="AdminCsvReject123!",
        email="admin.csv.reject@example.com",
        name="CSV Reject Admin",
    )
    admin_headers = auth_headers(admin.email, "AdminCsvReject123!")

    response = client.post(
        "/api/v1/leads/bulk",
        headers=admin_headers,
        files={"csv_file": ("leads.txt", b"not,csv", "text/plain")},
    )
    assert response.status_code == 400
    assert "Expected .csv file" in response.json()["detail"]


@pytest.mark.integration
def test_bulk_import_schema_requires_admin(client, user_factory, auth_headers):
    advisor = user_factory(
        role="advisor",
        password="AdvisorSchema123!",
        email="advisor.bulk.schema@example.com",
        name="Bulk Schema Advisor",
    )
    advisor_headers = auth_headers(advisor.email, "AdvisorSchema123!")

    response = client.get("/api/v1/leads/bulk/schema", headers=advisor_headers)

    assert response.status_code == 403


@pytest.mark.integration
def test_bulk_import_schema_returns_backend_truth(client, user_factory, auth_headers):
    admin = user_factory(
        role="admin",
        password="AdminSchema123!",
        email="admin.bulk.schema@example.com",
        name="Bulk Schema Admin",
    )
    admin_headers = auth_headers(admin.email, "AdminSchema123!")

    response = client.get("/api/v1/leads/bulk/schema", headers=admin_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["headers"] == LEAD_CSV_HEADERS
    assert payload["required_values"] == LEAD_CSV_REQUIRED_VALUE_FIELDS
    assert payload["system_fields"] == {"source": "csv_import"}
