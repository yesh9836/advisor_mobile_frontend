import pytest

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
