from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.security import create_access_token, hash_password_reset_token, hash_refresh_token
from app.db.timezone import utcnow
from app.models.auth_session import RefreshTokenSession
from app.models.notification import NotificationOutbox
from app.models.password_reset import PasswordResetRequestAttempt, PasswordResetToken
from app.schemas.auth import UserLogin, UserRegister
from app.services.auth_service import AuthService
from app.services.notification_service import NotificationDispatchResult, NotificationService


def _extract_password_reset_token_from_outbox(db, *, user_id: int) -> str:
    outbox_row = (
        db.query(NotificationOutbox)
        .filter(
            NotificationOutbox.user_id == user_id,
            NotificationOutbox.channel == "email",
            NotificationOutbox.event_type == "password_reset_requested",
        )
        .order_by(NotificationOutbox.id.desc())
        .first()
    )
    assert outbox_row is not None
    marker = "Reset your password: "
    reset_url = None
    for line in str(outbox_row.message_body or "").splitlines():
        if line.startswith(marker):
            reset_url = line.replace(marker, "", 1).strip()
            break
    assert reset_url
    token = parse_qs(urlparse(reset_url).query).get("token", [None])[0]
    assert token
    return token


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


@pytest.mark.unit
def test_register_duplicate_email_integrity_race_is_mapped_to_400(db, monkeypatch):
    register_data = UserRegister(
        email="dupe.race@example.com",
        password="StrongPass123!",
        name="Race User",
        phone="555-9090",
    )
    original_commit = db.commit
    commit_calls = {"count": 0}

    def commit_with_duplicate_race():
        commit_calls["count"] += 1
        if commit_calls["count"] == 1:
            raise IntegrityError(
                statement="INSERT INTO users (email, password_hash) VALUES (%s, %s)",
                params={"email": register_data.email},
                orig=Exception("Duplicate entry for key 'users.email'"),
            )
        return original_commit()

    monkeypatch.setattr(db, "commit", commit_with_duplicate_race)

    with pytest.raises(HTTPException) as exc_info:
        AuthService.register_user(db, register_data)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Email already registered"


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

    checkout = client.post("/api/v1/purchases/checkout", json={"package_id": plan.id})
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
    logout = client.post(
        "/api/v1/auth/logout",
        headers={settings.AUTH_CSRF_HEADER_NAME: csrf_token},
    )
    assert logout.status_code == 204, logout.text


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
def test_refresh_consume_guard_allows_single_consumer(session_factory, user_factory):
    email = "refresh.concurrent@example.com"
    password = "RefreshConcurrent123!"
    user = user_factory(email=email, password=password, name="Refresh Concurrent")

    bootstrap_db = session_factory()
    try:
        issued = AuthService.login_and_issue_tokens(
            bootstrap_db,
            UserLogin(email=email, password=password),
        )
        source_session = (
            bootstrap_db.query(RefreshTokenSession)
            .filter(RefreshTokenSession.token_hash == hash_refresh_token(issued.refresh_token))
            .first()
        )
        assert source_session is not None
        source_session_id = source_session.id
    finally:
        bootstrap_db.close()

    consumer_a = session_factory()
    try:
        first_consume = AuthService._consume_refresh_session(
            consumer_a,
            session_id=source_session_id,
            consumed_at=utcnow(),
            reason="rotated",
        )
        consumer_a.commit()
    finally:
        consumer_a.close()

    consumer_b = session_factory()
    try:
        second_consume = AuthService._consume_refresh_session(
            consumer_b,
            session_id=source_session_id,
            consumed_at=utcnow(),
            reason="rotated",
        )
        consumer_b.commit()
    finally:
        consumer_b.close()

    assert first_consume is True
    assert second_consume is False

    verify_db = session_factory()
    try:
        original_session = (
            verify_db.query(RefreshTokenSession)
            .filter(RefreshTokenSession.token_hash == hash_refresh_token(issued.refresh_token))
            .first()
        )
        assert original_session
        assert original_session.user_id == user.id
        assert original_session.revoked_at is not None
        assert original_session.revoked_reason == "rotated"
    finally:
        verify_db.close()


@pytest.mark.integration
def test_refresh_guard_failure_is_treated_as_reuse(client, monkeypatch):
    payload = {
        "email": "refresh.guard.failure@example.com",
        "password": "RefreshGuardFailure123!",
        "name": "Refresh Guard Failure",
        "phone": "555-1212",
    }
    register = client.post("/api/v1/auth/register", json=payload)
    assert register.status_code == 201, register.text

    login = client.post(
        "/api/v1/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert login.status_code == 204, login.text
    csrf = client.cookies.get(settings.AUTH_CSRF_COOKIE_NAME)
    assert csrf

    monkeypatch.setattr(
        AuthService,
        "_consume_refresh_session",
        staticmethod(lambda *args, **kwargs: False),
    )

    refresh = client.post(
        "/api/v1/auth/refresh",
        headers={settings.AUTH_CSRF_HEADER_NAME: csrf},
    )
    assert refresh.status_code == 401
    assert refresh.json()["detail"] == "Refresh token reuse detected"


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


@pytest.mark.integration
def test_password_reset_request_response_is_generic_for_known_and_unknown_email(
    client,
    db,
):
    payload = {
        "email": "reset.generic@example.com",
        "password": "ResetGeneric123!",
        "name": "Reset Generic",
        "phone": "555-1515",
    }
    register = client.post("/api/v1/auth/register", json=payload)
    assert register.status_code == 201, register.text

    existing = client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": payload["email"]},
    )
    assert existing.status_code == 202, existing.text

    unknown = client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": "unknown.reset@example.com"},
    )
    assert unknown.status_code == 202, unknown.text
    assert existing.json() == unknown.json()

    issued_tokens = db.query(PasswordResetToken).count()
    assert issued_tokens == 1
    queued_reset_emails = (
        db.query(NotificationOutbox)
        .filter(
            NotificationOutbox.user_id == register.json()["id"],
            NotificationOutbox.channel == "email",
            NotificationOutbox.event_type == "password_reset_requested",
        )
        .count()
    )
    assert queued_reset_emails == 1


@pytest.mark.integration
def test_password_reset_confirm_rejects_unissued_token(client):
    response = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": "invalid-token-that-was-never-issued-12345", "new_password": "AnyNewPass123!"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid or expired password reset token"


@pytest.mark.integration
def test_password_reset_confirm_updates_password_revokes_old_family_and_marks_token_used(
    client,
    db,
):
    payload = {
        "email": "reset.confirm@example.com",
        "password": "ResetOld123!",
        "name": "Reset Confirm",
        "phone": "555-1616",
    }
    register = client.post("/api/v1/auth/register", json=payload)
    assert register.status_code == 201, register.text

    login = client.post(
        "/api/v1/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert login.status_code == 204, login.text
    old_access = client.cookies.get(settings.AUTH_ACCESS_COOKIE_NAME)
    assert old_access

    request_reset = client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": payload["email"]},
    )
    assert request_reset.status_code == 202, request_reset.text
    token = _extract_password_reset_token_from_outbox(db, user_id=register.json()["id"])

    confirm = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": token, "new_password": "ResetNew123!"},
    )
    assert confirm.status_code == 204, confirm.text

    reuse = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": token, "new_password": "AnotherPass123!"},
    )
    assert reuse.status_code == 400
    assert reuse.json()["detail"] == "Invalid or expired password reset token"

    old_login = client.post(
        "/api/v1/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/api/v1/auth/login",
        json={"email": payload["email"], "password": "ResetNew123!"},
    )
    assert new_login.status_code == 204, new_login.text

    old_family_me = client.get(
        "/api/v1/auth/me",
        cookies={settings.AUTH_ACCESS_COOKIE_NAME: old_access},
    )
    assert old_family_me.status_code == 401


@pytest.mark.integration
def test_password_reset_confirm_rejects_expired_token(client, db):
    payload = {
        "email": "reset.expired@example.com",
        "password": "ResetExpired123!",
        "name": "Reset Expired",
        "phone": "555-1717",
    }
    register = client.post("/api/v1/auth/register", json=payload)
    assert register.status_code == 201, register.text

    request_reset = client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": payload["email"]},
    )
    assert request_reset.status_code == 202, request_reset.text
    token = _extract_password_reset_token_from_outbox(db, user_id=register.json()["id"])

    token_row = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token_hash == hash_password_reset_token(token))
        .first()
    )
    assert token_row is not None
    token_row.expires_at = utcnow() - timedelta(minutes=1)
    db.commit()

    confirm = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": token, "new_password": "ResetExpiredNew123!"},
    )
    assert confirm.status_code == 400
    assert confirm.json()["detail"] == "Invalid or expired password reset token"


@pytest.mark.integration
def test_password_reset_request_is_rate_limited_per_submitted_email_to_three_per_hour(
    client,
    db,
):
    payload = {
        "email": "reset.limit@example.com",
        "password": "ResetLimit123!",
        "name": "Reset Limit",
        "phone": "555-1818",
    }
    register = client.post("/api/v1/auth/register", json=payload)
    assert register.status_code == 201, register.text
    user_id = register.json()["id"]

    for _ in range(3):
        response = client.post(
            "/api/v1/auth/password-reset/request",
            json={"email": payload["email"]},
        )
        assert response.status_code == 202, response.text

    rate_limited_response = client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": payload["email"]},
    )
    assert rate_limited_response.status_code == 429, rate_limited_response.text
    assert "Too many password reset requests" in rate_limited_response.json()["detail"]
    assert rate_limited_response.headers.get("retry-after")

    issued_tokens = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.user_id == user_id)
        .count()
    )
    assert issued_tokens == 3
    queued_reset_emails = (
        db.query(NotificationOutbox)
        .filter(
            NotificationOutbox.user_id == user_id,
            NotificationOutbox.event_type == "password_reset_requested",
            NotificationOutbox.channel == "email",
        )
        .count()
    )
    assert queued_reset_emails == 3


@pytest.mark.integration
def test_password_reset_request_rate_limit_has_known_unknown_response_parity_under_retries(
    client,
    db,
):
    known_payload = {
        "email": "reset.parity@example.com",
        "password": "ResetParity123!",
        "name": "Reset Parity",
        "phone": "555-1919",
    }
    register = client.post("/api/v1/auth/register", json=known_payload)
    assert register.status_code == 201, register.text
    user_id = register.json()["id"]
    unknown_email = "reset.unknown.parity@example.com"

    for _ in range(3):
        known_response = client.post(
            "/api/v1/auth/password-reset/request",
            json={"email": known_payload["email"]},
        )
        assert known_response.status_code == 202, known_response.text

        unknown_response = client.post(
            "/api/v1/auth/password-reset/request",
            json={"email": unknown_email},
        )
        assert unknown_response.status_code == 202, unknown_response.text

    known_limited = client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": known_payload["email"]},
    )
    unknown_limited = client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": unknown_email},
    )

    assert known_limited.status_code == 429, known_limited.text
    assert unknown_limited.status_code == 429, unknown_limited.text
    assert known_limited.json()["detail"] == unknown_limited.json()["detail"]
    assert known_limited.headers.get("retry-after")
    assert unknown_limited.headers.get("retry-after")

    known_attempt_hash = AuthService._password_reset_rate_limit_subject_hash(known_payload["email"])
    unknown_attempt_hash = AuthService._password_reset_rate_limit_subject_hash(unknown_email)
    known_attempts = (
        db.query(PasswordResetRequestAttempt)
        .filter(PasswordResetRequestAttempt.subject_hash == known_attempt_hash)
        .count()
    )
    unknown_attempts = (
        db.query(PasswordResetRequestAttempt)
        .filter(PasswordResetRequestAttempt.subject_hash == unknown_attempt_hash)
        .count()
    )
    assert known_attempts == 3
    assert unknown_attempts == 3

    issued_tokens = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.user_id == user_id)
        .count()
    )
    assert issued_tokens == 3
    queued_reset_emails = (
        db.query(NotificationOutbox)
        .filter(
            NotificationOutbox.user_id == user_id,
            NotificationOutbox.event_type == "password_reset_requested",
            NotificationOutbox.channel == "email",
        )
        .count()
    )
    assert queued_reset_emails == 3


@pytest.mark.integration
def test_password_reset_request_enqueues_outbox_email_after_token_creation(client, db):
    payload = {
        "email": "reset.outbox@example.com",
        "password": "ResetOutbox123!",
        "name": "Reset Outbox",
        "phone": "555-2020",
    }
    register = client.post("/api/v1/auth/register", json=payload)
    assert register.status_code == 201, register.text
    user_id = register.json()["id"]

    response = client.post("/api/v1/auth/password-reset/request", json={"email": payload["email"]})
    assert response.status_code == 202, response.text

    outbox_row = (
        db.query(NotificationOutbox)
        .filter(
            NotificationOutbox.user_id == user_id,
            NotificationOutbox.channel == "email",
            NotificationOutbox.event_type == "password_reset_requested",
        )
        .order_by(NotificationOutbox.id.desc())
        .first()
    )
    assert outbox_row is not None
    assert outbox_row.status == "pending"
    assert outbox_row.attempt_count == 0
    assert outbox_row.recipient == payload["email"]
    assert "Reset your password:" in outbox_row.message_body
    assert "/reset-password?token=" in outbox_row.message_body
    assert isinstance(outbox_row.payload, dict)
    assert "/reset-password?token=" in str(outbox_row.payload.get("html_body", ""))


@pytest.mark.integration
def test_password_reset_outbox_email_retries_then_sends_when_worker_recovers(client, db, monkeypatch):
    payload = {
        "email": "reset.outbox.retry@example.com",
        "password": "ResetOutboxRetry123!",
        "name": "Reset Outbox Retry",
        "phone": "555-2121",
    }
    register = client.post("/api/v1/auth/register", json=payload)
    assert register.status_code == 201, register.text
    user_id = register.json()["id"]

    request_reset = client.post("/api/v1/auth/password-reset/request", json={"email": payload["email"]})
    assert request_reset.status_code == 202, request_reset.text

    row = (
        db.query(NotificationOutbox)
        .filter(
            NotificationOutbox.user_id == user_id,
            NotificationOutbox.channel == "email",
            NotificationOutbox.event_type == "password_reset_requested",
        )
        .order_by(NotificationOutbox.id.desc())
        .first()
    )
    assert row is not None

    monkeypatch.setattr(
        NotificationService,
        "_dispatch_row",
        staticmethod(lambda _row: NotificationDispatchResult(success=False, error="smtp outage")),
    )
    first_attempt = NotificationService.process_outbox_batch(db=db, batch_size=10)
    assert first_attempt["retried"] == 1
    db.refresh(row)
    assert row.status == "pending"
    assert row.attempt_count == 1
    assert row.last_error == "smtp outage"

    row.next_retry_at = utcnow() - timedelta(seconds=1)
    db.add(row)
    db.commit()

    monkeypatch.setattr(
        NotificationService,
        "_dispatch_row",
        staticmethod(lambda _row: NotificationDispatchResult(success=True, provider_message_id="msg-reset-123")),
    )
    second_attempt = NotificationService.process_outbox_batch(db=db, batch_size=10)
    assert second_attempt["sent"] == 1
    db.refresh(row)
    assert row.status == "sent"
    assert row.attempt_count == 2
    assert row.provider_message_id == "msg-reset-123"
