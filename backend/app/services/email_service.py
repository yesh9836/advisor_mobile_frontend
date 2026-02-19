import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Small SMTP helper for transactional outbound emails."""

    @staticmethod
    def _is_configured() -> bool:
        return bool(settings.SMTP_HOST and settings.SMTP_PORT and settings.SMTP_FROM_EMAIL)

    @staticmethod
    def send_password_reset_email(
        *,
        recipient_email: str,
        recipient_name: str | None,
        reset_url: str,
        expires_minutes: int,
    ) -> bool:
        if not EmailService._is_configured():
            logger.warning("SMTP is not configured; password reset email was skipped")
            return False

        message = EmailMessage()
        message["Subject"] = f"{settings.APP_NAME}: Reset your password"
        message["From"] = formataddr(
            (
                settings.SMTP_FROM_NAME or settings.APP_NAME,
                settings.SMTP_FROM_EMAIL or "",
            )
        )
        message["To"] = recipient_email
        display_name = recipient_name or "there"
        message.set_content(
            (
                f"Hi {display_name},\n\n"
                "We received a request to reset your password.\n\n"
                f"Reset your password: {reset_url}\n\n"
                f"This link expires in {expires_minutes} minutes and can be used once.\n"
                "If you did not request this, you can ignore this email.\n"
            )
        )

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
                return True

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
            return True
        except Exception:
            logger.exception("Failed to send password reset email")
            return False
