import io
from urllib import error as urlerror

import pytest

import app.services.sms_service as sms_service_module
from app.core.config import settings
from app.services.sms_service import SmsService


def _configure_twilio_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "NOTIFICATION_SMS_PROVIDER", "twilio")
    monkeypatch.setattr(settings, "TWILIO_ACCOUNT_SID", "AC123456789")
    monkeypatch.setattr(settings, "TWILIO_AUTH_TOKEN", "test-auth-token")
    monkeypatch.setattr(settings, "TWILIO_MESSAGING_SERVICE_SID", "MG123456789")
    monkeypatch.setattr(settings, "TWILIO_FROM_NUMBER", None)


class _FakeHTTPResponse:
    def __init__(self, *, status: int, body: str):
        self.status = status
        self._body = body.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def read(self):
        return self._body


@pytest.mark.unit
def test_send_via_twilio_success_extracts_sid(monkeypatch):
    _configure_twilio_settings(monkeypatch)
    monkeypatch.setattr(
        sms_service_module.urlrequest,
        "urlopen",
        lambda _request, timeout=15: _FakeHTTPResponse(status=201, body='{"sid":"SM123"}'),
    )

    result = SmsService._send_via_twilio(
        recipient_phone="+15551234567",
        body="hello",
    )

    assert result.success is True
    assert result.provider_message_id == "SM123"


@pytest.mark.unit
def test_send_via_twilio_maps_http_error(monkeypatch):
    _configure_twilio_settings(monkeypatch)

    def _raise_http_error(_request, timeout=15):
        raise urlerror.HTTPError(
            url="https://api.twilio.com",
            code=401,
            msg="unauthorized",
            hdrs=None,
            fp=io.BytesIO(b'{"message":"bad auth"}'),
        )

    monkeypatch.setattr(sms_service_module.urlrequest, "urlopen", _raise_http_error)

    result = SmsService._send_via_twilio(
        recipient_phone="+15551234567",
        body="hello",
    )

    assert result.success is False
    assert result.error == "Twilio HTTP 401"


@pytest.mark.unit
def test_send_via_twilio_maps_non_http_exception(monkeypatch):
    _configure_twilio_settings(monkeypatch)

    def _raise_timeout(_request, timeout=15):
        raise TimeoutError("timed out")

    monkeypatch.setattr(sms_service_module.urlrequest, "urlopen", _raise_timeout)

    result = SmsService._send_via_twilio(
        recipient_phone="+15551234567",
        body="hello",
    )

    assert result.success is False
    assert result.error == "Twilio dispatch failed"


@pytest.mark.unit
def test_send_via_twilio_handles_non_2xx_response(monkeypatch):
    _configure_twilio_settings(monkeypatch)
    monkeypatch.setattr(
        sms_service_module.urlrequest,
        "urlopen",
        lambda _request, timeout=15: _FakeHTTPResponse(status=500, body="{}"),
    )

    result = SmsService._send_via_twilio(
        recipient_phone="+15551234567",
        body="hello",
    )

    assert result.success is False
    assert result.error == "Twilio returned status 500"


@pytest.mark.unit
def test_send_via_twilio_handles_malformed_success_payload(monkeypatch):
    _configure_twilio_settings(monkeypatch)
    monkeypatch.setattr(
        sms_service_module.urlrequest,
        "urlopen",
        lambda _request, timeout=15: _FakeHTTPResponse(status=201, body="not-json"),
    )

    result = SmsService._send_via_twilio(
        recipient_phone="+15551234567",
        body="hello",
    )

    assert result.success is False
    assert result.error == "Twilio dispatch failed"
