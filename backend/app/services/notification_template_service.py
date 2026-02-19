from dataclasses import dataclass
from typing import Optional


@dataclass
class EmailTemplate:
    subject: str
    text_body: str
    html_body: Optional[str] = None


@dataclass
class SmsTemplate:
    body: str


class NotificationTemplateService:
    @staticmethod
    def render_password_reset_email(
        *,
        app_name: str,
        recipient_name: Optional[str],
        reset_url: str,
        expires_minutes: int,
    ) -> EmailTemplate:
        display_name = (recipient_name or "").strip() or "there"
        subject = f"{app_name}: Reset your password"
        text_body = (
            f"Hi {display_name},\n\n"
            "We received a request to reset your password.\n\n"
            f"Reset your password: {reset_url}\n\n"
            f"This link expires in {expires_minutes} minutes and can be used once.\n"
            "If you did not request this, you can ignore this email.\n"
        )
        html_body = (
            f"<p>Hi {display_name},</p>"
            "<p>We received a request to reset your password.</p>"
            f"<p><a href=\"{reset_url}\">Reset your password</a></p>"
            f"<p>This link expires in {expires_minutes} minutes and can be used once.</p>"
            "<p>If you did not request this, you can ignore this email.</p>"
        )
        return EmailTemplate(subject=subject, text_body=text_body, html_body=html_body)

    @staticmethod
    def render_lead_delivery_email(
        *,
        app_name: str,
        recipient_name: Optional[str],
        lead_display_name: str,
        state_code: str,
        inbox_url: str,
    ) -> EmailTemplate:
        display_name = (recipient_name or "").strip() or "Advisor"
        subject = f"{app_name}: New lead delivered ({state_code})"
        text_body = (
            f"Hi {display_name},\n\n"
            f"A new lead was delivered to your inbox: {lead_display_name} ({state_code}).\n\n"
            f"Open your lead inbox: {inbox_url}\n"
        )
        html_body = (
            f"<p>Hi {display_name},</p>"
            f"<p>A new lead was delivered to your inbox: <strong>{lead_display_name} ({state_code})</strong>.</p>"
            f"<p><a href=\"{inbox_url}\">Open your lead inbox</a></p>"
        )
        return EmailTemplate(subject=subject, text_body=text_body, html_body=html_body)

    @staticmethod
    def render_lead_delivery_sms(
        *,
        app_name: str,
        lead_display_name: str,
        state_code: str,
        inbox_url: str,
    ) -> SmsTemplate:
        return SmsTemplate(
            body=(
                f"{app_name}: New lead delivered ({state_code}) - "
                f"{lead_display_name}. Inbox: {inbox_url}"
            )
        )
