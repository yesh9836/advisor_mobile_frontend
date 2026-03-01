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
        delivered_count: int,
        total_count: int,
        inbox_url: str,
    ) -> EmailTemplate:
        display_name = (recipient_name or "").strip() or "Advisor"
        normalized_total = max(int(total_count), 0)
        normalized_delivered = max(int(delivered_count), 0)
        if normalized_total > 0:
            normalized_delivered = min(normalized_delivered, normalized_total)
            progress_text = f"{normalized_delivered}/{normalized_total}"
        else:
            progress_text = str(normalized_delivered)

        subject = f"{app_name}: Lead delivery update ({progress_text})"
        text_body = (
            f"Hi {display_name},\n\n"
            "You have a lead delivery update.\n\n"
            f"Leads delivered: {progress_text}\n\n"
            f"Open your lead inbox: {inbox_url}\n"
        )
        html_body = (
            f"<p>Hi {display_name},</p>"
            "<p>You have a lead delivery update.</p>"
            f"<p><strong>Leads delivered: {progress_text}</strong></p>"
            f"<p><a href=\"{inbox_url}\">Open your lead inbox</a></p>"
        )
        return EmailTemplate(subject=subject, text_body=text_body, html_body=html_body)

    @staticmethod
    def render_lead_delivery_sms(
        *,
        recipient_name: Optional[str],
        delivered_count: int,
        total_count: int,
    ) -> SmsTemplate:
        display_name = (recipient_name or "").strip() or "Advisor"
        normalized_total = max(int(total_count), 0)
        normalized_delivered = max(int(delivered_count), 0)
        if normalized_total > 0:
            normalized_delivered = min(normalized_delivered, normalized_total)
            progress_text = f"{normalized_delivered}/{normalized_total}"
        else:
            progress_text = str(normalized_delivered)
        return SmsTemplate(
            body=(
                f"{display_name}, {normalized_total} leads purchased "
                f"({progress_text}) delivered. Check your account for details"
            )
        )
