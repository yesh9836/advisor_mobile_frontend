import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Dict, List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.timezone import utcnow
from app.models.delivery_settings import AdvisorDeliverySettings
from app.models.lead import Lead
from app.models.purchase import LeadPurchase
from app.models.notification import NotificationOutbox
from app.models.user import User
from app.services.email_service import EmailService
from app.services.metrics_service import MetricsService
from app.services.notification_template_service import NotificationTemplateService
from app.services.sms_service import SmsService

logger = logging.getLogger(__name__)


@dataclass
class NotificationDispatchResult:
    success: bool
    provider_message_id: str | None = None
    error: str | None = None


class NotificationService:
    LEAD_DELIVERED_EVENT = "lead_delivered"

    @staticmethod
    def _build_inbox_url() -> str:
        return f"{settings.FRONTEND_URL.rstrip('/')}/leads"

    @staticmethod
    def _normalize_lead_ids(lead_ids: List[int]) -> List[int]:
        normalized = {
            int(lead_id)
            for lead_id in lead_ids
            if int(lead_id) > 0
        }
        return sorted(normalized)

    @staticmethod
    def _build_idempotency_key(
        *,
        channel: str,
        user_id: int,
        lead_id: int,
        purchase_id: Optional[int],
        event_type: str,
    ) -> str:
        purchase_part = int(purchase_id) if purchase_id is not None else 0
        return f"{event_type}:{channel}:u{int(user_id)}:l{int(lead_id)}:p{purchase_part}"

    @staticmethod
    def _build_delivery_progress_idempotency_key(
        *,
        channel: str,
        user_id: int,
        purchase_id: Optional[int],
        event_type: str,
        delivered_count: int,
        total_count: int,
    ) -> str:
        purchase_part = int(purchase_id) if purchase_id is not None else 0
        return (
            f"{event_type}:{channel}:u{int(user_id)}:p{purchase_part}:"
            f"d{int(delivered_count)}:t{int(total_count)}"
        )

    @staticmethod
    def _resolve_delivery_progress_counts(
        db: Session,
        *,
        user_id: int,
        purchase_id: Optional[int],
        lead_ids: List[int],
        purchase_total_leads: Optional[int],
        delivered_leads_count: Optional[int],
    ) -> tuple[int, int]:
        total_count = max(int(purchase_total_leads or 0), 0)
        delivered_count = max(int(delivered_leads_count or 0), 0)

        if purchase_id is not None and (purchase_total_leads is None or delivered_leads_count is None):
            purchase = (
                db.query(LeadPurchase)
                .filter(LeadPurchase.id == int(purchase_id), LeadPurchase.user_id == int(user_id))
                .first()
            )
            if purchase is not None:
                total_count = max(int(purchase.credits_total or 0), 0)
                delivered_count = max(total_count - max(int(purchase.credits_remaining or 0), 0), 0)

        if total_count <= 0:
            total_count = max(len(lead_ids), delivered_count)
        if delivered_count <= 0:
            delivered_count = min(len(lead_ids), total_count) if total_count > 0 else len(lead_ids)
        if total_count > 0:
            delivered_count = min(delivered_count, total_count)

        return delivered_count, total_count

    @staticmethod
    def _is_duplicate_outbox_idempotency_integrity_error(exc: IntegrityError) -> bool:
        details = " ".join(
            [
                str(exc).lower(),
                str(getattr(exc, "orig", "")).lower(),
                str(getattr(exc, "statement", "")).lower(),
                str(getattr(exc, "params", "")).lower(),
            ]
        )
        has_duplicate_marker = any(
            marker in details
            for marker in (
                "duplicate",
                "duplicate entry",
                "duplicate key value",
                "unique constraint",
                "unique constraint failed",
            )
        )
        has_idempotency_marker = "idempotency" in details
        return has_duplicate_marker and has_idempotency_marker

    @staticmethod
    def enqueue_lead_delivery_notifications(
        db: Session,
        *,
        user_id: int,
        lead_ids: List[int],
        purchase_id: Optional[int],
        source_event: str,
        purchase_total_leads: Optional[int] = None,
        delivered_leads_count: Optional[int] = None,
    ) -> Dict[str, int]:
        if not settings.NOTIFICATIONS_ENABLED:
            return {"enqueued_total": 0, "enqueued_email": 0, "enqueued_sms": 0}

        normalized_lead_ids = NotificationService._normalize_lead_ids(lead_ids)
        if not normalized_lead_ids:
            return {"enqueued_total": 0, "enqueued_email": 0, "enqueued_sms": 0}

        user = db.query(User).filter(User.id == user_id).first()
        if not user or user.role != "advisor" or not user.is_active:
            return {"enqueued_total": 0, "enqueued_email": 0, "enqueued_sms": 0}

        delivery_settings = (
            db.query(AdvisorDeliverySettings)
            .filter(AdvisorDeliverySettings.user_id == user_id)
            .first()
        )
        email_opt_in = bool(delivery_settings and delivery_settings.email_alerts_enabled)
        sms_opt_in = bool(delivery_settings and delivery_settings.sms_alerts_enabled)
        enable_email = settings.NOTIFICATION_EMAIL_ENABLED and email_opt_in and bool(user.email)
        enable_sms = settings.NOTIFICATION_SMS_ENABLED and sms_opt_in and bool((user.phone or "").strip())

        if not enable_email and not enable_sms:
            return {"enqueued_total": 0, "enqueued_email": 0, "enqueued_sms": 0}

        existing_lead_ids = [
            int(lead_id)
            for (lead_id,) in (
                db.query(Lead.id)
                .filter(Lead.id.in_(normalized_lead_ids))
                .all()
            )
        ]
        if not existing_lead_ids:
            return {"enqueued_total": 0, "enqueued_email": 0, "enqueued_sms": 0}

        delivered_count, total_count = NotificationService._resolve_delivery_progress_counts(
            db,
            user_id=user.id,
            purchase_id=purchase_id,
            lead_ids=existing_lead_ids,
            purchase_total_leads=purchase_total_leads,
            delivered_leads_count=delivered_leads_count,
        )

        inbox_url = NotificationService._build_inbox_url()
        pending_rows: List[NotificationOutbox] = []
        now = utcnow()
        primary_lead_id = min(existing_lead_ids)

        if enable_email:
            email_template = NotificationTemplateService.render_lead_delivery_email(
                app_name=settings.APP_NAME,
                recipient_name=user.name,
                delivered_count=delivered_count,
                total_count=total_count,
                inbox_url=inbox_url,
            )
            pending_rows.append(
                NotificationOutbox(
                    user_id=user.id,
                    lead_id=primary_lead_id,
                    purchase_id=purchase_id,
                    channel="email",
                    event_type=NotificationService.LEAD_DELIVERED_EVENT,
                    recipient=user.email,
                    subject=email_template.subject,
                    message_body=email_template.text_body,
                    payload={
                        "html_body": email_template.html_body,
                        "source_event": source_event,
                        "lead_ids": existing_lead_ids,
                        "delivered_count": delivered_count,
                        "total_count": total_count,
                    },
                    idempotency_key=NotificationService._build_delivery_progress_idempotency_key(
                        channel="email",
                        user_id=user.id,
                        purchase_id=purchase_id,
                        event_type=NotificationService.LEAD_DELIVERED_EVENT,
                        delivered_count=delivered_count,
                        total_count=total_count,
                    ),
                    status="pending",
                    attempt_count=0,
                    max_attempts=settings.NOTIFICATION_OUTBOX_MAX_ATTEMPTS,
                    next_retry_at=now,
                )
            )
        if enable_sms:
            sms_template = NotificationTemplateService.render_lead_delivery_sms(
                recipient_name=user.name,
                delivered_count=delivered_count,
                total_count=total_count,
            )
            pending_rows.append(
                NotificationOutbox(
                    user_id=user.id,
                    lead_id=primary_lead_id,
                    purchase_id=purchase_id,
                    channel="sms",
                    event_type=NotificationService.LEAD_DELIVERED_EVENT,
                    recipient=(user.phone or "").strip(),
                    subject=None,
                    message_body=sms_template.body,
                    payload={
                        "source_event": source_event,
                        "lead_ids": existing_lead_ids,
                        "delivered_count": delivered_count,
                        "total_count": total_count,
                    },
                    idempotency_key=NotificationService._build_delivery_progress_idempotency_key(
                        channel="sms",
                        user_id=user.id,
                        purchase_id=purchase_id,
                        event_type=NotificationService.LEAD_DELIVERED_EVENT,
                        delivered_count=delivered_count,
                        total_count=total_count,
                    ),
                    status="pending",
                    attempt_count=0,
                    max_attempts=settings.NOTIFICATION_OUTBOX_MAX_ATTEMPTS,
                    next_retry_at=now,
                )
            )

        if not pending_rows:
            return {"enqueued_total": 0, "enqueued_email": 0, "enqueued_sms": 0}

        enqueued_email = 0
        enqueued_sms = 0
        for row in pending_rows:
            try:
                # Savepoint keeps parent transaction alive if this row collides concurrently.
                with db.begin_nested():
                    db.add(row)
                    db.flush()
            except IntegrityError as exc:
                if NotificationService._is_duplicate_outbox_idempotency_integrity_error(exc):
                    logger.info(
                        "Skipping duplicate notification enqueue idempotency_key=%s",
                        row.idempotency_key,
                    )
                    continue
                raise
            if row.channel == "email":
                enqueued_email += 1
            elif row.channel == "sms":
                enqueued_sms += 1

        enqueued_total = enqueued_email + enqueued_sms
        if enqueued_total > 0:
            MetricsService.increment(
                "notification_outbox_enqueued_total",
                value=enqueued_total,
                tags={"event_type": NotificationService.LEAD_DELIVERED_EVENT},
            )
        return {
            "enqueued_total": enqueued_total,
            "enqueued_email": enqueued_email,
            "enqueued_sms": enqueued_sms,
        }

    @staticmethod
    def _compute_retry_delay_seconds(attempt_count: int) -> int:
        base = max(int(settings.NOTIFICATION_RETRY_BASE_SECONDS), 1)
        cap = max(int(settings.NOTIFICATION_RETRY_MAX_SECONDS), base)
        exponent = max(int(attempt_count) - 1, 0)
        return min(base * (2 ** exponent), cap)

    @staticmethod
    def _dispatch_row(row: NotificationOutbox) -> NotificationDispatchResult:
        if row.channel == "email":
            payload = row.payload or {}
            result = EmailService.send_transactional_email(
                recipient_email=row.recipient,
                subject=row.subject or f"{settings.APP_NAME}: Notification",
                text_body=row.message_body,
                html_body=payload.get("html_body"),
            )
            return NotificationDispatchResult(
                success=result.success,
                provider_message_id=result.provider_message_id,
                error=result.error,
            )

        if row.channel == "sms":
            result = SmsService.send_sms(
                recipient_phone=row.recipient,
                body=row.message_body,
            )
            return NotificationDispatchResult(
                success=result.success,
                provider_message_id=result.provider_message_id,
                error=result.error,
            )

        return NotificationDispatchResult(
            success=False,
            error=f"Unsupported channel '{row.channel}'",
        )

    @staticmethod
    def reclaim_stale_processing_rows(
        db: Session,
        *,
        now=None,
        stale_lock_seconds: Optional[int] = None,
    ) -> Dict[str, int]:
        current = now or utcnow()
        stale_after_seconds = stale_lock_seconds
        if stale_after_seconds is None:
            stale_after_seconds = int(settings.NOTIFICATION_OUTBOX_HEALTH_STALE_LOCK_SECONDS)
        stale_after_seconds = max(int(stale_after_seconds), 1)
        stale_cutoff = current - timedelta(seconds=stale_after_seconds)

        stale_rows = (
            db.query(NotificationOutbox)
            .filter(
                NotificationOutbox.status == "processing",
                NotificationOutbox.locked_at.is_not(None),
                NotificationOutbox.locked_at <= stale_cutoff,
            )
            .order_by(NotificationOutbox.id.asc())
            .all()
        )
        if not stale_rows:
            return {"stale_selected": 0, "reclaimed_pending": 0, "reclaimed_failed": 0}

        reclaimed_pending = 0
        reclaimed_failed = 0
        for row in stale_rows:
            attempts = int(row.attempt_count or 0)
            max_attempts = int(row.max_attempts or settings.NOTIFICATION_OUTBOX_MAX_ATTEMPTS)
            row.locked_at = None
            row.next_retry_at = current
            if attempts >= max_attempts:
                row.status = "failed"
                reclaimed_failed += 1
            else:
                row.status = "pending"
                reclaimed_pending += 1
            if not row.last_error:
                row.last_error = "stale processing lock reclaimed"
            db.add(row)

        db.commit()
        return {
            "stale_selected": len(stale_rows),
            "reclaimed_pending": reclaimed_pending,
            "reclaimed_failed": reclaimed_failed,
        }

    @staticmethod
    def process_outbox_batch(
        db: Session,
        *,
        batch_size: Optional[int] = None,
    ) -> Dict[str, int]:
        now = utcnow()
        max_batch_size = batch_size or settings.NOTIFICATION_OUTBOX_BATCH_SIZE
        max_batch_size = max(1, int(max_batch_size))

        eligible_query = (
            db.query(NotificationOutbox)
            .filter(
                NotificationOutbox.status == "pending",
                NotificationOutbox.next_retry_at <= now,
            )
            .order_by(NotificationOutbox.id.asc())
        )
        bind = db.get_bind()
        if bind is not None and bind.dialect.name == "mysql":
            eligible_query = eligible_query.with_for_update(skip_locked=True)

        rows = eligible_query.limit(max_batch_size).all()
        if not rows:
            return {"selected": 0, "sent": 0, "retried": 0, "failed": 0}

        for row in rows:
            row.status = "processing"
            row.locked_at = now
            row.attempt_count = int(row.attempt_count or 0) + 1
            db.add(row)
        db.flush()

        sent_count = 0
        retried_count = 0
        failed_count = 0

        for row in rows:
            try:
                result = NotificationService._dispatch_row(row)
            except Exception as exc:
                logger.exception("Unexpected notification dispatch error for outbox_id=%s", row.id)
                result = NotificationDispatchResult(success=False, error=str(exc))
            if result.success:
                row.status = "sent"
                row.sent_at = now
                row.last_error = None
                row.provider_message_id = result.provider_message_id
                row.locked_at = None
                sent_count += 1
            else:
                row.last_error = (result.error or "dispatch failed")[:2000]
                row.locked_at = None
                if int(row.attempt_count) >= int(row.max_attempts):
                    row.status = "failed"
                    row.next_retry_at = now
                    failed_count += 1
                else:
                    row.status = "pending"
                    delay_seconds = NotificationService._compute_retry_delay_seconds(row.attempt_count)
                    row.next_retry_at = now + timedelta(seconds=delay_seconds)
                    retried_count += 1
            db.add(row)

        db.commit()
        if sent_count > 0:
            MetricsService.increment("notification_outbox_sent_total", value=sent_count)
        if retried_count > 0:
            MetricsService.increment("notification_outbox_retried_total", value=retried_count)
        if failed_count > 0:
            MetricsService.increment("notification_outbox_failed_total", value=failed_count)

        return {
            "selected": len(rows),
            "sent": sent_count,
            "retried": retried_count,
            "failed": failed_count,
        }
