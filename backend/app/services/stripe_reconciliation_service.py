import logging
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

import stripe
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.purchase import StripeReconciliationCheckpoint
from app.services.metrics_service import MetricsService
from app.services.payment_service import PaymentService
from app.services.stripe_webhook_inbox_service import StripeWebhookInboxService
from app.services.subscription_service import StripeWebhookProcessingError

logger = logging.getLogger(__name__)


class StripeReconciliationService:
    """Periodic Stripe event scan to backfill missed webhook deliveries."""

    CHECKPOINT_SOURCE = "stripe_events"
    RELEVANT_EVENT_TYPES = (
        "checkout.session.completed",
        "checkout.session.async_payment_succeeded",
        "checkout.session.async_payment_failed",
        "payment_intent.succeeded",
        "payment_intent.payment_failed",
        "charge.refunded",
    )

    @staticmethod
    def _to_event_payload(event: Any) -> Dict[str, Any]:
        if isinstance(event, dict):
            return event
        to_dict_recursive = getattr(event, "to_dict_recursive", None)
        if callable(to_dict_recursive):
            payload = to_dict_recursive()
            if isinstance(payload, dict):
                return payload
        to_dict = getattr(event, "to_dict", None)
        if callable(to_dict):
            payload = to_dict()
            if isinstance(payload, dict):
                return payload
        return {}

    @staticmethod
    def _iter_events(event_list: Any) -> Iterable[Any]:
        auto_paging_iter = getattr(event_list, "auto_paging_iter", None)
        if callable(auto_paging_iter):
            yield from auto_paging_iter()
            return
        if isinstance(event_list, dict):
            for row in event_list.get("data") or []:
                yield row
            return
        if isinstance(event_list, list):
            yield from event_list

    @staticmethod
    def _is_newer_event(
        *,
        candidate_created: int,
        candidate_id: str,
        current_created: int,
        current_id: Optional[str],
    ) -> bool:
        if candidate_created > current_created:
            return True
        if candidate_created < current_created:
            return False
        return candidate_id > str(current_id or "")

    @staticmethod
    def _get_or_create_checkpoint(db: Session) -> StripeReconciliationCheckpoint:
        checkpoint = (
            db.query(StripeReconciliationCheckpoint)
            .filter(StripeReconciliationCheckpoint.source == StripeReconciliationService.CHECKPOINT_SOURCE)
            .first()
        )
        if checkpoint:
            return checkpoint
        checkpoint = StripeReconciliationCheckpoint(
            source=StripeReconciliationService.CHECKPOINT_SOURCE,
            last_event_created=0,
            last_event_id=None,
        )
        db.add(checkpoint)
        db.commit()
        db.refresh(checkpoint)
        return checkpoint

    @staticmethod
    def run_once(
        db: Session,
        *,
        page_size: Optional[int] = None,
    ) -> Dict[str, int]:
        PaymentService._init_stripe()
        checkpoint = StripeReconciliationService._get_or_create_checkpoint(db)

        now_epoch = int(datetime.now(timezone.utc).timestamp())
        lookback_seconds = max(int(settings.STRIPE_RECONCILIATION_LOOKBACK_SECONDS or 0), 60)
        safety_window_seconds = max(int(settings.STRIPE_RECONCILIATION_SAFETY_WINDOW_SECONDS or 0), 0)
        checkpoint_created = int(checkpoint.last_event_created or 0)
        if checkpoint_created > 0:
            start_created = max(checkpoint_created - safety_window_seconds, 0)
        else:
            start_created = max(now_epoch - lookback_seconds, 0)
        effective_page_size = max(1, min(int(page_size or settings.STRIPE_RECONCILIATION_PAGE_SIZE or 100), 100))

        try:
            event_list = stripe.Event.list(
                limit=effective_page_size,
                types=list(StripeReconciliationService.RELEVANT_EVENT_TYPES),
                created={"gte": start_created},
            )
        except stripe.error.StripeError as exc:
            MetricsService.increment(
                "purchase_webhook_reconciliation_runs_total",
                tags={"status": "failure", "error_type": type(exc).__name__},
            )
            raise StripeWebhookProcessingError(f"Stripe reconciliation list failure: {exc}") from exc

        scanned = 0
        considered = 0
        enqueued = 0
        duplicates = 0
        skipped_before_checkpoint = 0

        high_water_created = int(checkpoint.last_event_created or 0)
        high_water_id = str(checkpoint.last_event_id or "")
        checkpoint_created = high_water_created
        checkpoint_id = high_water_id

        for raw_event in StripeReconciliationService._iter_events(event_list):
            payload = StripeReconciliationService._to_event_payload(raw_event)
            event_id = str(payload.get("id") or "").strip()
            if not event_id:
                continue

            scanned += 1
            event_created = max(int(payload.get("created") or 0), 0)
            if not StripeReconciliationService._is_newer_event(
                candidate_created=event_created,
                candidate_id=event_id,
                current_created=checkpoint_created,
                current_id=checkpoint_id,
            ):
                skipped_before_checkpoint += 1
                continue

            considered += 1
            if StripeWebhookInboxService.enqueue_event(db=db, event=payload):
                enqueued += 1
            else:
                duplicates += 1

            if StripeReconciliationService._is_newer_event(
                candidate_created=event_created,
                candidate_id=event_id,
                current_created=high_water_created,
                current_id=high_water_id,
            ):
                high_water_created = event_created
                high_water_id = event_id

        if (high_water_created, high_water_id) != (
            int(checkpoint.last_event_created or 0),
            str(checkpoint.last_event_id or ""),
        ):
            checkpoint.last_event_created = high_water_created
            checkpoint.last_event_id = high_water_id or None
            db.add(checkpoint)
            db.commit()

        MetricsService.increment(
            "purchase_webhook_reconciliation_runs_total",
            tags={"status": "success"},
        )
        MetricsService.increment(
            "purchase_webhook_reconciliation_events_total",
            value=scanned,
            tags={"outcome": "scanned"},
        )
        MetricsService.increment(
            "purchase_webhook_reconciliation_events_total",
            value=considered,
            tags={"outcome": "considered"},
        )
        MetricsService.increment(
            "purchase_webhook_reconciliation_events_total",
            value=enqueued,
            tags={"outcome": "enqueued"},
        )
        MetricsService.increment(
            "purchase_webhook_reconciliation_events_total",
            value=duplicates,
            tags={"outcome": "duplicate"},
        )
        MetricsService.increment(
            "purchase_webhook_reconciliation_events_total",
            value=skipped_before_checkpoint,
            tags={"outcome": "skipped_before_checkpoint"},
        )
        logger.info(
            (
                "Stripe reconciliation run complete: scanned=%s considered=%s "
                "enqueued=%s duplicates=%s skipped_before_checkpoint=%s high_watermark=(%s,%s)"
            ),
            scanned,
            considered,
            enqueued,
            duplicates,
            skipped_before_checkpoint,
            high_water_created,
            high_water_id,
        )
        return {
            "scanned": scanned,
            "considered": considered,
            "enqueued": enqueued,
            "duplicates": duplicates,
            "skipped_before_checkpoint": skipped_before_checkpoint,
            "start_created": start_created,
            "high_water_created": high_water_created,
        }

    @staticmethod
    def run_once_threadsafe(*, page_size: Optional[int] = None) -> Dict[str, int]:
        db = SessionLocal()
        try:
            return StripeReconciliationService.run_once(db=db, page_size=page_size)
        finally:
            db.close()
