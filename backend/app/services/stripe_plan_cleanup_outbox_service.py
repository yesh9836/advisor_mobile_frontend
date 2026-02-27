import hashlib
import logging
from datetime import timedelta
from typing import Any, Dict, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.timezone import utcnow
from app.models.purchase import StripePlanCleanupOutbox
from app.services.metrics_service import MetricsService
from app.services.payment_service import PaymentService

logger = logging.getLogger(__name__)


class StripePlanCleanupOutboxService:
    WORKER_HEARTBEAT_SOURCE = "stripe_plan_cleanup_outbox_worker"

    @staticmethod
    def _normalize_artifact_id(value: Optional[str]) -> Optional[str]:
        normalized = str(value or "").strip()
        return normalized or None

    @staticmethod
    def _build_idempotency_key(
        *,
        source: str,
        stripe_price_id: Optional[str],
        stripe_product_id: Optional[str],
    ) -> str:
        material = f"{source}:{stripe_price_id or ''}:{stripe_product_id or ''}"
        digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:40]
        return f"stripe-plan-cleanup:{digest}:v1"

    @staticmethod
    def enqueue_cleanup(
        db: Session,
        *,
        source: str,
        stripe_price_id: Optional[str],
        stripe_product_id: Optional[str],
        payload: Optional[Dict[str, Any]] = None,
        max_attempts: Optional[int] = None,
    ) -> bool:
        normalized_source = str(source or "").strip() or "unknown"
        normalized_price_id = StripePlanCleanupOutboxService._normalize_artifact_id(stripe_price_id)
        normalized_product_id = StripePlanCleanupOutboxService._normalize_artifact_id(stripe_product_id)
        if normalized_price_id is None and normalized_product_id is None:
            return False

        idempotency_key = StripePlanCleanupOutboxService._build_idempotency_key(
            source=normalized_source,
            stripe_price_id=normalized_price_id,
            stripe_product_id=normalized_product_id,
        )

        db.add(
            StripePlanCleanupOutbox(
                source=normalized_source,
                stripe_price_id=normalized_price_id,
                stripe_product_id=normalized_product_id,
                status="pending",
                attempt_count=0,
                max_attempts=max(
                    1,
                    int(max_attempts or settings.STRIPE_PLAN_CLEANUP_OUTBOX_MAX_ATTEMPTS),
                ),
                next_retry_at=utcnow(),
                idempotency_key=idempotency_key,
                payload=payload or None,
            )
        )
        try:
            db.commit()
            return True
        except IntegrityError:
            db.rollback()
            duplicate = (
                db.query(StripePlanCleanupOutbox.id)
                .filter(StripePlanCleanupOutbox.idempotency_key == idempotency_key)
                .first()
            )
            if duplicate is not None:
                return False
            raise

    @staticmethod
    def _compute_retry_delay_seconds(attempt_count: int) -> int:
        base = max(int(settings.STRIPE_PLAN_CLEANUP_RETRY_BASE_SECONDS), 1)
        cap = max(int(settings.STRIPE_PLAN_CLEANUP_RETRY_MAX_SECONDS), base)
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
            stale_after_seconds = int(settings.STRIPE_PLAN_CLEANUP_STALE_LOCK_SECONDS)
        stale_after_seconds = max(int(stale_after_seconds), 1)
        stale_cutoff = current - timedelta(seconds=stale_after_seconds)

        stale_rows = (
            db.query(StripePlanCleanupOutbox)
            .filter(
                StripePlanCleanupOutbox.status == "processing",
                StripePlanCleanupOutbox.locked_at.is_not(None),
                StripePlanCleanupOutbox.locked_at <= stale_cutoff,
            )
            .order_by(StripePlanCleanupOutbox.id.asc())
            .all()
        )
        if not stale_rows:
            return {"stale_selected": 0, "reclaimed_pending": 0, "reclaimed_failed": 0}

        reclaimed_pending = 0
        reclaimed_failed = 0
        for row in stale_rows:
            attempts = int(row.attempt_count or 0)
            max_attempts = int(row.max_attempts or settings.STRIPE_PLAN_CLEANUP_OUTBOX_MAX_ATTEMPTS)
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
        max_batch_size = batch_size or settings.STRIPE_PLAN_CLEANUP_OUTBOX_BATCH_SIZE
        max_batch_size = max(1, int(max_batch_size))

        eligible_query = (
            db.query(StripePlanCleanupOutbox)
            .filter(
                StripePlanCleanupOutbox.status == "pending",
                StripePlanCleanupOutbox.next_retry_at <= now,
            )
            .order_by(StripePlanCleanupOutbox.id.asc())
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

        for row in rows:
            source_tag = str(row.source or "unknown")
            try:
                PaymentService.deactivate_stripe_plan_artifacts(
                    stripe_price_id=row.stripe_price_id,
                    stripe_product_id=row.stripe_product_id,
                )
            except Exception as exc:
                row.locked_at = None
                row.last_error = str(exc)[:2000]
                if int(row.attempt_count or 0) >= int(row.max_attempts or 1):
                    row.status = "failed"
                    row.next_retry_at = now
                    failed_count += 1
                    MetricsService.increment(
                        "stripe_plan_cleanup_failed_total",
                        tags={"source": source_tag},
                    )
                else:
                    row.status = "pending"
                    delay_seconds = StripePlanCleanupOutboxService._compute_retry_delay_seconds(
                        int(row.attempt_count or 0)
                    )
                    row.next_retry_at = now + timedelta(seconds=delay_seconds)
                    retried_count += 1
                    MetricsService.increment(
                        "stripe_plan_cleanup_retry_total",
                        tags={"source": source_tag},
                    )
            else:
                row.status = "processed"
                row.processed_at = utcnow()
                row.locked_at = None
                row.last_error = None
                processed_count += 1
                MetricsService.increment(
                    "stripe_plan_cleanup_processed_total",
                    tags={"source": source_tag},
                )
            finally:
                db.add(row)

        db.commit()
        return {
            "selected": len(rows),
            "processed": processed_count,
            "retried": retried_count,
            "failed": failed_count,
        }
