import logging
from datetime import timedelta
from time import perf_counter
from typing import Any, Dict, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.db.timezone import utcnow
from app.models.purchase import StripeWebhookInbox
from app.services.metrics_service import MetricsService
from app.services.subscription_service import (
    StripeWebhookNonRetryableError,
    StripeWebhookProcessingError,
    SubscriptionService,
)

logger = logging.getLogger(__name__)


class StripeWebhookInboxService:
    @staticmethod
    def _extract_event_identity(event: Dict[str, Any]) -> tuple[str, str]:
        event_id = str(event.get("id") or "").strip()
        if not event_id:
            raise StripeWebhookProcessingError("Stripe webhook missing event ID")
        return event_id, str(event.get("type") or "unknown")

    @staticmethod
    def enqueue_event(
        db: Session,
        *,
        event: Dict[str, Any],
    ) -> bool:
        event_id, event_type = StripeWebhookInboxService._extract_event_identity(event)

        db.add(
            StripeWebhookInbox(
                stripe_event_id=event_id,
                event_type=event_type,
                payload=event,
                status="pending",
                attempt_count=0,
                max_attempts=int(settings.STRIPE_WEBHOOK_INBOX_MAX_ATTEMPTS),
                next_retry_at=utcnow(),
            )
        )
        try:
            db.commit()
            return True
        except IntegrityError:
            db.rollback()
            duplicate = (
                db.query(StripeWebhookInbox.id)
                .filter(StripeWebhookInbox.stripe_event_id == event_id)
                .first()
            )
            if duplicate:
                return False
            raise

    @staticmethod
    def enqueue_event_threadsafe(event: Dict[str, Any]) -> bool:
        db = SessionLocal()
        try:
            return StripeWebhookInboxService.enqueue_event(db=db, event=event)
        finally:
            db.close()

    @staticmethod
    def _compute_retry_delay_seconds(attempt_count: int) -> int:
        base = max(int(settings.STRIPE_WEBHOOK_INBOX_RETRY_BASE_SECONDS), 1)
        cap = max(int(settings.STRIPE_WEBHOOK_INBOX_RETRY_MAX_SECONDS), base)
        exponent = max(int(attempt_count) - 1, 0)
        return min(base * (2 ** exponent), cap)

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
            stale_after_seconds = int(settings.STRIPE_WEBHOOK_HEALTH_STALE_LOCK_SECONDS)
        stale_after_seconds = max(int(stale_after_seconds), 1)
        stale_cutoff = current - timedelta(seconds=stale_after_seconds)

        stale_rows = (
            db.query(StripeWebhookInbox)
            .filter(
                StripeWebhookInbox.status == "processing",
                StripeWebhookInbox.locked_at.is_not(None),
                StripeWebhookInbox.locked_at <= stale_cutoff,
            )
            .order_by(StripeWebhookInbox.id.asc())
            .all()
        )
        if not stale_rows:
            return {"stale_selected": 0, "reclaimed_pending": 0, "reclaimed_failed": 0}

        reclaimed_pending = 0
        reclaimed_failed = 0
        for row in stale_rows:
            attempts = int(row.attempt_count or 0)
            max_attempts = int(row.max_attempts or settings.STRIPE_WEBHOOK_INBOX_MAX_ATTEMPTS)
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
    def process_inbox_batch(
        db: Session,
        *,
        batch_size: Optional[int] = None,
    ) -> Dict[str, int]:
        now = utcnow()
        max_batch_size = batch_size or settings.STRIPE_WEBHOOK_INBOX_BATCH_SIZE
        max_batch_size = max(1, int(max_batch_size))

        eligible_query = (
            db.query(StripeWebhookInbox)
            .filter(
                StripeWebhookInbox.status == "pending",
                StripeWebhookInbox.next_retry_at <= now,
            )
            .order_by(StripeWebhookInbox.id.asc())
        )
        bind = db.get_bind()
        if bind is not None and bind.dialect.name == "mysql":
            eligible_query = eligible_query.with_for_update(skip_locked=True)

        rows = eligible_query.limit(max_batch_size).all()
        if not rows:
            return {
                "selected": 0,
                "processed": 0,
                "retried": 0,
                "failed": 0,
                "non_retryable": 0,
            }

        for row in rows:
            row.status = "processing"
            row.locked_at = now
            row.attempt_count = int(row.attempt_count or 0) + 1
            db.add(row)
        db.flush()

        processed_count = 0
        retried_count = 0
        failed_count = 0
        non_retryable_count = 0

        for row in rows:
            event_payload = row.payload if isinstance(row.payload, dict) else {}
            event_type = str(row.event_type or "unknown")
            started_at = perf_counter()

            try:
                SubscriptionService.handle_webhook_event_threadsafe(event_payload)
            except StripeWebhookNonRetryableError as exc:
                row.status = "processed"
                row.processed_at = utcnow()
                row.locked_at = None
                row.last_error = f"non_retryable:{exc.reason}"[:2000]
                non_retryable_count += 1
                MetricsService.increment(
                    "purchase_webhook_acknowledged_non_retryable_total",
                    tags={
                        "event_type": event_type,
                        "reason": exc.reason,
                    },
                )
            except StripeWebhookProcessingError as exc:
                row.locked_at = None
                row.last_error = str(exc)[:2000]
                if int(row.attempt_count or 0) >= int(row.max_attempts or 1):
                    row.status = "failed"
                    row.next_retry_at = now
                    failed_count += 1
                    MetricsService.increment(
                        "purchase_webhook_failed_total",
                        tags={"event_type": event_type},
                    )
                else:
                    row.status = "pending"
                    delay_seconds = StripeWebhookInboxService._compute_retry_delay_seconds(
                        int(row.attempt_count or 0)
                    )
                    row.next_retry_at = now + timedelta(seconds=delay_seconds)
                    retried_count += 1
                    MetricsService.increment(
                        "purchase_webhook_retry_total",
                        tags={"event_type": event_type},
                    )
            except Exception as exc:
                logger.exception("Unexpected Stripe webhook worker failure for inbox_id=%s", row.id)
                row.locked_at = None
                row.last_error = str(exc)[:2000]
                if int(row.attempt_count or 0) >= int(row.max_attempts or 1):
                    row.status = "failed"
                    row.next_retry_at = now
                    failed_count += 1
                    MetricsService.increment(
                        "purchase_webhook_failed_total",
                        tags={"event_type": event_type},
                    )
                else:
                    row.status = "pending"
                    delay_seconds = StripeWebhookInboxService._compute_retry_delay_seconds(
                        int(row.attempt_count or 0)
                    )
                    row.next_retry_at = now + timedelta(seconds=delay_seconds)
                    retried_count += 1
                    MetricsService.increment(
                        "purchase_webhook_retry_total",
                        tags={"event_type": event_type},
                    )
            else:
                row.status = "processed"
                row.processed_at = utcnow()
                row.locked_at = None
                row.last_error = None
                processed_count += 1
                MetricsService.increment(
                    "purchase_webhook_processed_total",
                    tags={"event_type": event_type},
                )
            finally:
                elapsed_ms = (perf_counter() - started_at) * 1000.0
                MetricsService.histogram(
                    "purchase_webhook_processing_latency_ms",
                    elapsed_ms,
                    tags={
                        "event_type": event_type,
                        "processing_mode": "worker",
                    },
                )
                db.add(row)

        db.commit()
        return {
            "selected": len(rows),
            "processed": processed_count,
            "retried": retried_count,
            "failed": failed_count,
            "non_retryable": non_retryable_count,
        }
