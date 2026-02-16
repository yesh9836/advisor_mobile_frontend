import pytest
from pydantic import ValidationError
from starlette.requests import Request

from app.core.config import Settings, settings
from app.core.rate_limit import RateLimitMiddleware, rate_limiter


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    rate_limiter.reset()
    yield
    rate_limiter.reset()


@pytest.mark.unit
def test_production_settings_require_strong_secret_key():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            APP_ENV="production",
            SECRET_KEY="weak-secret",
            INITIAL_ADMIN_PASSWORD="StrongAdmin#123",
            DB_PASSWORD="db-password-123",
            STRIPE_SECRET_KEY="sk_live_example_123",
            STRIPE_WEBHOOK_SECRET="whsec_example_123",
            CORS_ORIGINS=["https://app.example.com"],
            CORS_ALLOW_METHODS=["GET", "POST"],
            CORS_ALLOW_HEADERS=["Authorization", "Content-Type"],
        )


@pytest.mark.unit
def test_production_settings_reject_wildcard_cors():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            APP_ENV="production",
            SECRET_KEY="z" * 40,
            INITIAL_ADMIN_PASSWORD="StrongAdmin#123",
            DB_PASSWORD="db-password-123",
            STRIPE_SECRET_KEY="sk_live_example_123",
            STRIPE_WEBHOOK_SECRET="whsec_example_123",
            CORS_ORIGINS=["https://app.example.com"],
            CORS_ALLOW_METHODS=["*"],
            CORS_ALLOW_HEADERS=["Authorization", "Content-Type"],
        )


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
        "phone": "555-1010",
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
        "phone": "555-2020",
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
        "phone": "555-3030",
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
def test_rate_limit_blocks_excess_requests(client, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 2)
    monkeypatch.setattr(settings, "RATE_LIMIT_WINDOW_SECONDS", 60)

    headers = {"X-Forwarded-For": "203.0.113.60"}
    payload = {"email": "nobody@example.com", "password": "WrongPass123!"}

    first = client.post("/api/v1/auth/login", headers=headers, json=payload)
    second = client.post("/api/v1/auth/login", headers=headers, json=payload)
    third = client.post("/api/v1/auth/login", headers=headers, json=payload)

    assert first.status_code == 401
    assert second.status_code == 401
    assert third.status_code == 429
    assert third.headers.get("retry-after") is not None


@pytest.mark.integration
def test_rate_limit_ignores_spoofed_forwarded_for_by_default(client, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "RATE_LIMIT_PER_MINUTE", 1)
    monkeypatch.setattr(settings, "RATE_LIMIT_WINDOW_SECONDS", 60)
    monkeypatch.setattr(settings, "RATE_LIMIT_TRUST_PROXY_HEADERS", False)
    monkeypatch.setattr(settings, "RATE_LIMIT_TRUSTED_PROXIES", [])

    payload = {"email": "nobody@example.com", "password": "WrongPass123!"}

    first = client.post(
        "/api/v1/auth/login",
        headers={"X-Forwarded-For": "198.51.100.10"},
        json=payload,
    )
    second = client.post(
        "/api/v1/auth/login",
        headers={"X-Forwarded-For": "198.51.100.11"},
        json=payload,
    )

    assert first.status_code == 401
    assert second.status_code == 429


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

    assert RateLimitMiddleware._get_client_identifier(request) == "203.0.113.60"


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

    assert RateLimitMiddleware._get_client_identifier(request) == "198.51.100.10"


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
