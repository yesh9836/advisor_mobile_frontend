import logging
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr
import json
from urllib import error as urlerror
from urllib import request as urlrequest

from app.core.config import settings
from app.services.notification_template_service import NotificationTemplateService

logger = logging.getLogger(__name__)


@dataclass
class EmailSendResult:
    success: bool
    provider_message_id: str | None = None
    error: str | None = None


class EmailService:
    """Transactional outbound email helper with pluggable providers."""

    @staticmethod
    def _is_smtp_configured() -> bool:
        return bool(
            settings.SMTP_HOST
            and settings.SMTP_PORT
            and (settings.NOTIFICATION_FROM_EMAIL or settings.SMTP_FROM_EMAIL)
        )

    @staticmethod
    def _get_from_address() -> tuple[str, str]:
        sender_email = settings.NOTIFICATION_FROM_EMAIL or settings.SMTP_FROM_EMAIL or ""
        sender_name = settings.NOTIFICATION_FROM_NAME or settings.SMTP_FROM_NAME or settings.APP_NAME
        return sender_name, sender_email

    @staticmethod
    def send_transactional_email(
        *,
        recipient_email: str,
        subject: str,
        text_body: str,
        html_body: str | None = None,
    ) -> EmailSendResult:
        provider = settings.NOTIFICATION_EMAIL_PROVIDER.strip().lower()
        if provider == "noop":
            logger.info(
                "NOOP email dispatch: to=%s subject=%s",
                recipient_email,
                subject,
            )
            return EmailSendResult(success=True, provider_message_id="noop-email")
        if provider == "sendgrid":
            return EmailService._send_via_sendgrid(
                recipient_email=recipient_email,
                subject=subject,
                text_body=text_body,
                html_body=html_body,
            )
        if provider not in {"smtp", "smtp2go"}:
            return EmailSendResult(
                success=False,
                error=f"Unsupported email provider '{provider}'",
            )
        return EmailService._send_via_smtp(
            recipient_email=recipient_email,
            subject=subject,
            text_body=text_body,
            html_body=html_body,
        )

    @staticmethod
    def _send_via_smtp(
        *,
        recipient_email: str,
        subject: str,
        text_body: str,
        html_body: str | None = None,
    ) -> EmailSendResult:
        if not EmailService._is_smtp_configured():
            logger.warning("SMTP is not configured; transactional email was skipped")
            return EmailSendResult(success=False, error="SMTP is not configured")

        from_name, from_email = EmailService._get_from_address()
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = formataddr((from_name, from_email))
        message["To"] = recipient_email
        message.set_content(text_body)
        if html_body:
            message.add_alternative(html_body, subtype="html")

        try:
            if settings.SMTP_PORT == 465:
                with smtplib.SMTP_SSL(
                    settings.SMTP_HOST,
                    settings.SMTP_PORT,
                    timeout=15,
                ) as smtp:
                    if settings.SMTP_USER and settings.SMTP_PASSWORD:
                        smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                    smtp.send_message(message)
                return EmailSendResult(success=True)

            with smtplib.SMTP(
                settings.SMTP_HOST,
                settings.SMTP_PORT,
                timeout=15,
            ) as smtp:
                smtp.ehlo()
                try:
                    smtp.starttls(context=ssl.create_default_context())
                    smtp.ehlo()
                except smtplib.SMTPNotSupportedError:
                    logger.warning("SMTP server does not support STARTTLS; sending without TLS")
                if settings.SMTP_USER and settings.SMTP_PASSWORD:
                    smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                smtp.send_message(message)
            return EmailSendResult(success=True)
        except Exception:
            logger.exception("Failed to send SMTP email")
            return EmailSendResult(success=False, error="SMTP dispatch failed")

    @staticmethod
    def _send_via_sendgrid(
        *,
        recipient_email: str,
        subject: str,
        text_body: str,
        html_body: str | None = None,
    ) -> EmailSendResult:
        api_key = settings.SENDGRID_API_KEY
        from_name, from_email = EmailService._get_from_address()
        if not api_key:
            return EmailSendResult(success=False, error="SENDGRID_API_KEY is not configured")
        if not from_email:
            return EmailSendResult(success=False, error="From email is not configured")

        content = [{"type": "text/plain", "value": text_body}]
        if html_body:
            content.append({"type": "text/html", "value": html_body})

        payload = {
            "personalizations": [{"to": [{"email": recipient_email}]}],
            "from": {"email": from_email, "name": from_name},
            "subject": subject,
            "content": content,
        }
        request = urlrequest.Request(
            url="https://api.sendgrid.com/v3/mail/send",
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urlrequest.urlopen(request, timeout=15) as response:
                status_code = int(getattr(response, "status", 0) or 0)
                if 200 <= status_code < 300:
                    return EmailSendResult(
                        success=True,
                        provider_message_id=response.headers.get("X-Message-Id"),
                    )
                return EmailSendResult(
                    success=False,
                    error=f"SendGrid returned status {status_code}",
                )
        except urlerror.HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8")
            except Exception:
                body = ""
            logger.error("SendGrid HTTP error: status=%s body=%s", exc.code, body)
            return EmailSendResult(success=False, error=f"SendGrid HTTP {exc.code}")
        except Exception:
            logger.exception("Failed to send SendGrid email")
            return EmailSendResult(success=False, error="SendGrid dispatch failed")

    @staticmethod
    def send_password_reset_email(
        *,
        recipient_email: str,
        recipient_name: str | None,
        reset_url: str,
        expires_minutes: int,
    ) -> bool:
        template = NotificationTemplateService.render_password_reset_email(
            app_name=settings.APP_NAME,
            recipient_name=recipient_name,
            reset_url=reset_url,
            expires_minutes=expires_minutes,
        )
        result = EmailService.send_transactional_email(
            recipient_email=recipient_email,
            subject=template.subject,
            text_body=template.text_body,
            html_body=template.html_body,
        )
        if not result.success:
            logger.warning(
                "Password reset email dispatch failed for recipient=%s error=%s",
                recipient_email,
                result.error,
            )
        return result.success
