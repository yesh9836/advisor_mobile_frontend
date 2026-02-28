import smtplib

import pytest

import app.services.email_service as email_service_module
from app.core.config import settings
from app.services.email_service import EmailSendResult, EmailService


@pytest.mark.unit
def test_send_transactional_email_routes_smtp2go_to_smtp_transport(monkeypatch):
    monkeypatch.setattr(settings, "NOTIFICATION_EMAIL_PROVIDER", "smtp2go")

    calls = []

    def _smtp_stub(**kwargs):
        calls.append(kwargs)
        return EmailSendResult(success=True, provider_message_id="smtp-msg-1")

    monkeypatch.setattr(EmailService, "_send_via_smtp", staticmethod(_smtp_stub))

    result = EmailService.send_transactional_email(
        recipient_email="advisor@example.com",
        subject="Test subject",
        text_body="Text body",
        html_body="<p>HTML body</p>",
    )

    assert result.success is True
    assert result.provider_message_id == "smtp-msg-1"
    assert len(calls) == 1
    assert calls[0]["recipient_email"] == "advisor@example.com"


@pytest.mark.unit
def test_send_transactional_email_rejects_unknown_provider(monkeypatch):
    monkeypatch.setattr(settings, "NOTIFICATION_EMAIL_PROVIDER", "unknown-provider")

    result = EmailService.send_transactional_email(
        recipient_email="advisor@example.com",
        subject="Test subject",
        text_body="Text body",
        html_body=None,
    )

    assert result.success is False
    assert "Unsupported email provider" in (result.error or "")


def _configure_smtp_settings(monkeypatch: pytest.MonkeyPatch, *, port: int = 587) -> None:
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(settings, "SMTP_PORT", port)
    monkeypatch.setattr(settings, "SMTP_FROM_EMAIL", "noreply@example.com")
    monkeypatch.setattr(settings, "NOTIFICATION_FROM_EMAIL", None)
    monkeypatch.setattr(settings, "SMTP_USER", "smtp-user")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "smtp-pass")


@pytest.mark.unit
def test_send_via_smtp_starttls_success_and_login(monkeypatch):
    _configure_smtp_settings(monkeypatch, port=587)
    monkeypatch.setattr(settings, "APP_ENV", "development")

    calls = {"ehlo": 0, "starttls": 0, "login": 0, "send_message": 0}

    class _FakeSMTP:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def ehlo(self):
            calls["ehlo"] += 1

        def starttls(self, context=None):
            assert context is not None
            calls["starttls"] += 1

        def login(self, *_args, **_kwargs):
            calls["login"] += 1

        def send_message(self, _message):
            calls["send_message"] += 1

    monkeypatch.setattr(email_service_module.smtplib, "SMTP", _FakeSMTP)

    result = EmailService._send_via_smtp(
        recipient_email="advisor@example.com",
        subject="Subject",
        text_body="Body",
        html_body=None,
    )

    assert result.success is True
    assert calls["starttls"] == 1
    assert calls["login"] == 1
    assert calls["send_message"] == 1
    assert calls["ehlo"] == 2


@pytest.mark.unit
def test_send_via_smtp_ssl_success_for_port_465(monkeypatch):
    _configure_smtp_settings(monkeypatch, port=465)
    monkeypatch.setattr(settings, "APP_ENV", "development")

    calls = {"login": 0, "send_message": 0}

    class _FakeSMTPSSL:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def login(self, *_args, **_kwargs):
            calls["login"] += 1

        def send_message(self, _message):
            calls["send_message"] += 1

    monkeypatch.setattr(email_service_module.smtplib, "SMTP_SSL", _FakeSMTPSSL)

    result = EmailService._send_via_smtp(
        recipient_email="advisor@example.com",
        subject="Subject",
        text_body="Body",
        html_body=None,
    )

    assert result.success is True
    assert calls["login"] == 1
    assert calls["send_message"] == 1


@pytest.mark.unit
def test_send_via_smtp_fails_closed_when_starttls_unsupported_in_production(monkeypatch):
    _configure_smtp_settings(monkeypatch, port=587)
    monkeypatch.setattr(settings, "APP_ENV", "production")

    calls = {"send_message": 0}

    class _FakeSMTP:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def ehlo(self):
            return None

        def starttls(self, context=None):
            raise smtplib.SMTPNotSupportedError("STARTTLS unavailable")

        def login(self, *_args, **_kwargs):
            return None

        def send_message(self, _message):
            calls["send_message"] += 1

    monkeypatch.setattr(email_service_module.smtplib, "SMTP", _FakeSMTP)

    result = EmailService._send_via_smtp(
        recipient_email="advisor@example.com",
        subject="Subject",
        text_body="Body",
        html_body=None,
    )

    assert result.success is False
    assert result.error == "SMTP TLS is required in production"
    assert calls["send_message"] == 0


@pytest.mark.unit
def test_send_via_smtp_allows_plaintext_fallback_when_not_production(monkeypatch):
    _configure_smtp_settings(monkeypatch, port=587)
    monkeypatch.setattr(settings, "APP_ENV", "development")

    calls = {"send_message": 0}

    class _FakeSMTP:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def ehlo(self):
            return None

        def starttls(self, context=None):
            raise smtplib.SMTPNotSupportedError("STARTTLS unavailable")

        def login(self, *_args, **_kwargs):
            return None

        def send_message(self, _message):
            calls["send_message"] += 1

    monkeypatch.setattr(email_service_module.smtplib, "SMTP", _FakeSMTP)

    result = EmailService._send_via_smtp(
        recipient_email="advisor@example.com",
        subject="Subject",
        text_body="Body",
        html_body=None,
    )

    assert result.success is True
    assert calls["send_message"] == 1


@pytest.mark.unit
def test_send_via_smtp_maps_auth_failure(monkeypatch):
    _configure_smtp_settings(monkeypatch, port=587)
    monkeypatch.setattr(settings, "APP_ENV", "development")

    class _FakeSMTP:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def ehlo(self):
            return None

        def starttls(self, context=None):
            return None

        def login(self, *_args, **_kwargs):
            raise smtplib.SMTPAuthenticationError(535, b"invalid creds")

        def send_message(self, _message):
            return None

    monkeypatch.setattr(email_service_module.smtplib, "SMTP", _FakeSMTP)

    result = EmailService._send_via_smtp(
        recipient_email="advisor@example.com",
        subject="Subject",
        text_body="Body",
        html_body=None,
    )

    assert result.success is False
    assert result.error == "SMTP dispatch failed"


@pytest.mark.unit
def test_send_via_smtp_maps_timeout_failure(monkeypatch):
    _configure_smtp_settings(monkeypatch, port=587)
    monkeypatch.setattr(settings, "APP_ENV", "development")

    class _FakeSMTP:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def ehlo(self):
            return None

        def starttls(self, context=None):
            return None

        def login(self, *_args, **_kwargs):
            return None

        def send_message(self, _message):
            raise TimeoutError("smtp timeout")

    monkeypatch.setattr(email_service_module.smtplib, "SMTP", _FakeSMTP)

    result = EmailService._send_via_smtp(
        recipient_email="advisor@example.com",
        subject="Subject",
        text_body="Body",
        html_body=None,
    )

    assert result.success is False
    assert result.error == "SMTP dispatch failed"
