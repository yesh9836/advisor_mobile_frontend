from datetime import timedelta

import pytest

from app.core.config import settings
from app.core.security import create_access_token


@pytest.mark.integration
def test_register_login_and_me_roundtrip(client):
    register_payload = {
        "email": "advisor.auth@example.com",
        "password": "StrongPass123!",
        "name": "Advisor Auth",
        "phone": "555-1111",
    }

    register_response = client.post("/api/v1/auth/register", json=register_payload)
    assert register_response.status_code == 201, register_response.text
    assert register_response.json()["role"] == "advisor"

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": register_payload["email"], "password": register_payload["password"]},
    )
    assert login_response.status_code == 204, login_response.text

    me_response = client.get("/api/v1/auth/me")
    assert me_response.status_code == 200, me_response.text
    data = me_response.json()
    assert data["email"] == register_payload["email"]
    assert data["name"] == register_payload["name"]


@pytest.mark.integration
def test_register_duplicate_email_is_rejected(client):
    payload = {
        "email": "dupe@example.com",
        "password": "StrongPass123!",
        "name": "User One",
        "phone": "555-2222",
    }
    first = client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201, first.text

    duplicate = client.post("/api/v1/auth/register", json=payload)
    assert duplicate.status_code == 400
    assert duplicate.json()["detail"] == "Email already registered"


@pytest.mark.integration
def test_login_with_invalid_password_returns_401(client):
    payload = {
        "email": "invalid.login@example.com",
        "password": "StrongPass123!",
        "name": "Login User",
        "phone": "555-3333",
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201, response.text

    bad_login = client.post(
        "/api/v1/auth/login",
        json={"email": payload["email"], "password": "WrongPassword!"},
    )
    assert bad_login.status_code == 401
    assert bad_login.json()["detail"] == "Incorrect email or password"


@pytest.mark.integration
def test_admin_only_endpoint_forbidden_for_advisor(client, auth_headers):
    advisor_payload = {
        "email": "advisor.only@example.com",
        "password": "StrongPass123!",
        "name": "Advisor Only",
        "phone": "555-4444",
    }
    response = client.post("/api/v1/auth/register", json=advisor_payload)
    assert response.status_code == 201, response.text

    headers = auth_headers(advisor_payload["email"], advisor_payload["password"])
    pending_response = client.get("/api/v1/licenses/pending", headers=headers)
    assert pending_response.status_code == 403
    assert pending_response.json()["detail"] == "Admin access required"


@pytest.mark.integration
def test_login_sets_auth_cookies(client):
    payload = {
        "email": "cookie.login@example.com",
        "password": "CookiePass123!",
        "name": "Cookie User",
        "phone": "555-5555",
    }
    register = client.post("/api/v1/auth/register", json=payload)
    assert register.status_code == 201, register.text

    response = client.post(
        "/api/v1/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert response.status_code == 204, response.text
    assert response.cookies.get(settings.AUTH_ACCESS_COOKIE_NAME)
    assert response.cookies.get(settings.AUTH_REFRESH_COOKIE_NAME)
    assert response.cookies.get(settings.AUTH_CSRF_COOKIE_NAME)
    assert "httponly" in response.headers.get("set-cookie", "").lower()


@pytest.mark.integration
def test_cookie_auth_me_roundtrip(client):
    payload = {
        "email": "cookie.me@example.com",
        "password": "CookieMe123!",
        "name": "Cookie Me",
        "phone": "555-6666",
    }
    register = client.post("/api/v1/auth/register", json=payload)
    assert register.status_code == 201, register.text

    login = client.post(
        "/api/v1/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert login.status_code == 204, login.text

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200, me.text
    assert me.json()["email"] == payload["email"]


@pytest.mark.integration
def test_cookie_auth_requires_csrf_for_mutating_request(client, plan_factory):
    payload = {
        "email": "cookie.csrf@example.com",
        "password": "CookieCsrf123!",
        "name": "Cookie CSRF",
        "phone": "555-7777",
    }
    register = client.post("/api/v1/auth/register", json=payload)
    assert register.status_code == 201, register.text
    plan = plan_factory(stripe_price_id="price_cookie_csrf")

    login = client.post(
        "/api/v1/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert login.status_code == 204, login.text

    checkout = client.post("/api/v1/subscriptions/checkout", json={"plan_id": plan.id})
    assert checkout.status_code == 403
    assert checkout.json()["detail"] == "CSRF token validation failed"


@pytest.mark.integration
def test_cookie_auth_allows_mutating_request_with_csrf(client):
    payload = {
        "email": "bearer.compat@example.com",
        "password": "BearerCompat123!",
        "name": "Bearer Compat",
        "phone": "555-7888",
    }
    register = client.post("/api/v1/auth/register", json=payload)
    assert register.status_code == 201, register.text
    login = client.post(
        "/api/v1/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert login.status_code == 204, login.text
    csrf_token = client.cookies.get(settings.AUTH_CSRF_COOKIE_NAME)
    assert csrf_token

    cancel = client.post(
        "/api/v1/subscriptions/cancel",
        headers={settings.AUTH_CSRF_HEADER_NAME: csrf_token},
    )
    assert cancel.status_code == 404
    assert cancel.json()["detail"] == "No subscription found"


@pytest.mark.integration
def test_refresh_rotates_token_and_detects_reuse(client):
    payload = {
        "email": "refresh.rotate@example.com",
        "password": "RefreshRotate123!",
        "name": "Refresh Rotate",
        "phone": "555-8888",
    }
    register = client.post("/api/v1/auth/register", json=payload)
    assert register.status_code == 201, register.text

    login = client.post(
        "/api/v1/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert login.status_code == 204, login.text

    old_access = client.cookies.get(settings.AUTH_ACCESS_COOKIE_NAME)
    old_refresh = client.cookies.get(settings.AUTH_REFRESH_COOKIE_NAME)
    old_csrf = client.cookies.get(settings.AUTH_CSRF_COOKIE_NAME)
    assert old_access
    assert old_refresh
    assert old_csrf

    refresh = client.post(
        "/api/v1/auth/refresh",
        headers={settings.AUTH_CSRF_HEADER_NAME: old_csrf},
    )
    assert refresh.status_code == 204, refresh.text

    rotated_refresh = client.cookies.get(settings.AUTH_REFRESH_COOKIE_NAME)
    rotated_csrf = client.cookies.get(settings.AUTH_CSRF_COOKIE_NAME)
    assert rotated_refresh
    assert rotated_refresh != old_refresh
    assert rotated_csrf

    old_access_still_valid = client.get(
        "/api/v1/auth/me",
        cookies={settings.AUTH_ACCESS_COOKIE_NAME: old_access},
    )
    assert old_access_still_valid.status_code == 200, old_access_still_valid.text

    reuse = client.post(
        "/api/v1/auth/refresh",
        headers={settings.AUTH_CSRF_HEADER_NAME: "reuse-attempt"},
        cookies={
            settings.AUTH_REFRESH_COOKIE_NAME: old_refresh,
            settings.AUTH_CSRF_COOKIE_NAME: "reuse-attempt",
        },
    )
    assert reuse.status_code == 401
    assert reuse.json()["detail"] == "Refresh token reuse detected"

    family_revoked = client.post(
        "/api/v1/auth/refresh",
        headers={settings.AUTH_CSRF_HEADER_NAME: rotated_csrf},
        cookies={
            settings.AUTH_REFRESH_COOKIE_NAME: rotated_refresh,
            settings.AUTH_CSRF_COOKIE_NAME: rotated_csrf,
        },
    )
    assert family_revoked.status_code == 401

    old_access_after_family_revoke = client.get(
        "/api/v1/auth/me",
        cookies={settings.AUTH_ACCESS_COOKIE_NAME: old_access},
    )
    assert old_access_after_family_revoke.status_code == 401


@pytest.mark.integration
def test_logout_revokes_family_and_clears_auth_cookies(client):
    payload = {
        "email": "logout.cookie@example.com",
        "password": "LogoutCookie123!",
        "name": "Logout Cookie",
        "phone": "555-9999",
    }
    register = client.post("/api/v1/auth/register", json=payload)
    assert register.status_code == 201, register.text

    login = client.post(
        "/api/v1/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert login.status_code == 204, login.text
    access_token = client.cookies.get(settings.AUTH_ACCESS_COOKIE_NAME)
    refresh_token = client.cookies.get(settings.AUTH_REFRESH_COOKIE_NAME)
    csrf_token = client.cookies.get(settings.AUTH_CSRF_COOKIE_NAME)
    assert access_token
    assert refresh_token
    assert csrf_token

    logout = client.post(
        "/api/v1/auth/logout",
        headers={settings.AUTH_CSRF_HEADER_NAME: csrf_token},
    )
    assert logout.status_code == 204, logout.text
    assert client.cookies.get(settings.AUTH_ACCESS_COOKIE_NAME) is None
    assert client.cookies.get(settings.AUTH_REFRESH_COOKIE_NAME) is None
    assert client.cookies.get(settings.AUTH_CSRF_COOKIE_NAME) is None

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 401

    me_with_prelogout_access = client.get(
        "/api/v1/auth/me",
        cookies={settings.AUTH_ACCESS_COOKIE_NAME: access_token},
    )
    assert me_with_prelogout_access.status_code == 401

    refresh = client.post(
        "/api/v1/auth/refresh",
        headers={settings.AUTH_CSRF_HEADER_NAME: "post-logout"},
        cookies={
            settings.AUTH_REFRESH_COOKIE_NAME: refresh_token,
            settings.AUTH_CSRF_COOKIE_NAME: "post-logout",
        },
    )
    assert refresh.status_code == 401


@pytest.mark.integration
def test_access_token_missing_family_claim_is_rejected(client):
    payload = {
        "email": "claims.missing.fid@example.com",
        "password": "ClaimsMissingFid123!",
        "name": "Claims Missing FID",
        "phone": "555-1313",
    }
    register = client.post("/api/v1/auth/register", json=payload)
    assert register.status_code == 201, register.text
    user_id = register.json()["id"]

    malformed_access = create_access_token(
        data={"sub": payload["email"], "uid": user_id, "typ": "access"},
        expires_delta=timedelta(minutes=5),
    )
    me = client.get(
        "/api/v1/auth/me",
        cookies={settings.AUTH_ACCESS_COOKIE_NAME: malformed_access},
    )
    assert me.status_code == 401


@pytest.mark.integration
def test_access_token_with_wrong_type_claim_is_rejected(client):
    payload = {
        "email": "claims.wrong.type@example.com",
        "password": "ClaimsWrongType123!",
        "name": "Claims Wrong Type",
        "phone": "555-1414",
    }
    register = client.post("/api/v1/auth/register", json=payload)
    assert register.status_code == 201, register.text
    user_id = register.json()["id"]

    wrong_type_access = create_access_token(
        data={
            "sub": payload["email"],
            "uid": user_id,
            "fid": "manual-family",
            "typ": "refresh",
        },
        expires_delta=timedelta(minutes=5),
    )
    me = client.get(
        "/api/v1/auth/me",
        cookies={settings.AUTH_ACCESS_COOKIE_NAME: wrong_type_access},
    )
    assert me.status_code == 401
