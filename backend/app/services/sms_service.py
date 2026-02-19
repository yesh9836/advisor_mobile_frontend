import base64
from dataclasses import dataclass
import json
import logging
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class SmsSendResult:
    success: bool
    provider_message_id: str | None = None
    error: str | None = None


class SmsService:
    """Transactional SMS helper with pluggable providers."""

    @staticmethod
    def send_sms(*, recipient_phone: str, body: str) -> SmsSendResult:
        provider = settings.NOTIFICATION_SMS_PROVIDER.strip().lower()
        if provider == "noop":
            logger.info("NOOP SMS dispatch: to=%s", recipient_phone)
            return SmsSendResult(success=True, provider_message_id="noop-sms")
        if provider == "twilio":
            return SmsService._send_via_twilio(recipient_phone=recipient_phone, body=body)
        return SmsSendResult(
            success=False,
            error=f"Unsupported SMS provider '{provider}'",
        )

    @staticmethod
    def _send_via_twilio(*, recipient_phone: str, body: str) -> SmsSendResult:
        account_sid = settings.TWILIO_ACCOUNT_SID
        auth_token = settings.TWILIO_AUTH_TOKEN
        messaging_service_sid = settings.TWILIO_MESSAGING_SERVICE_SID
        from_number = settings.TWILIO_FROM_NUMBER

        if not account_sid or not auth_token:
            return SmsSendResult(success=False, error="Twilio credentials are not configured")
        if not messaging_service_sid and not from_number:
            return SmsSendResult(
                success=False,
                error="TWILIO_MESSAGING_SERVICE_SID or TWILIO_FROM_NUMBER is required",
            )

        payload = {
            "To": recipient_phone,
            "Body": body,
        }
        if messaging_service_sid:
            payload["MessagingServiceSid"] = messaging_service_sid
        elif from_number:
            payload["From"] = from_number

        token_bytes = f"{account_sid}:{auth_token}".encode("utf-8")
        auth_header = base64.b64encode(token_bytes).decode("utf-8")

        request = urlrequest.Request(
            url=(
                "https://api.twilio.com/2010-04-01/Accounts/"
                f"{urlparse.quote(account_sid)}/Messages.json"
            ),
            data=urlparse.urlencode(payload).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Basic {auth_header}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )

        try:
            with urlrequest.urlopen(request, timeout=15) as response:
                status_code = int(getattr(response, "status", 0) or 0)
                body_text = response.read().decode("utf-8")
                response_data = json.loads(body_text) if body_text else {}
                if 200 <= status_code < 300:
                    return SmsSendResult(
                        success=True,
                        provider_message_id=response_data.get("sid"),
                    )
                return SmsSendResult(
                    success=False,
                    error=f"Twilio returned status {status_code}",
                )
        except urlerror.HTTPError as exc:
            body_text = ""
            try:
                body_text = exc.read().decode("utf-8")
            except Exception:
                body_text = ""
            logger.error("Twilio HTTP error: status=%s body=%s", exc.code, body_text)
            return SmsSendResult(success=False, error=f"Twilio HTTP {exc.code}")
        except Exception:
            logger.exception("Failed to send Twilio SMS")
            return SmsSendResult(success=False, error="Twilio dispatch failed")
