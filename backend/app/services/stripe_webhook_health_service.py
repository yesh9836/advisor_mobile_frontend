from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.timezone import ensure_utc, utcnow
from app.models.purchase import (
    StripePlanCleanupOutbox,
    StripeWebhookInbox,
    StripeWebhookWorkerHeartbeat,
)


class StripeWebhookHealthService:
    INBOX_WORKER_HEARTBEAT_SOURCE = "stripe_webhook_inbox_worker"
    CLEANUP_WORKER_HEARTBEAT_SOURCE = "stripe_plan_cleanup_outbox_worker"

    @staticmethod
    def _isoformat_or_none(value: Optional[datetime]) -> Optional[str]:
        normalized = ensure_utc(value)
        return normalized.isoformat() if normalized else None

    @staticmethod
    def _get_or_create_heartbeat_row(db: Session, *, source: str) -> StripeWebhookWorkerHeartbeat:
        row = (
            db.query(StripeWebhookWorkerHeartbeat)
            .filter(StripeWebhookWorkerHeartbeat.source == source)
            .first()
        )
        if row is not None:
            return row

        row = StripeWebhookWorkerHeartbeat(source=source)
        db.add(row)
        try:
            db.flush()
            return row
        except IntegrityError:
            db.rollback()
            existing = (
                db.query(StripeWebhookWorkerHeartbeat)
                .filter(StripeWebhookWorkerHeartbeat.source == source)
                .first()
            )
            if existing is None:
                raise
            return existing

    @staticmethod
    def record_worker_started(
        db: Session,
        *,
        source: str = INBOX_WORKER_HEARTBEAT_SOURCE,
        started_at: Optional[datetime] = None,
    ) -> None:
        started = ensure_utc(started_at) or utcnow()
        row = StripeWebhookHealthService._get_or_create_heartbeat_row(db, source=source)
        row.last_started_at = started
        db.add(row)
        db.commit()

    @staticmethod
    def record_worker_finished(
        db: Session,
        *,
        source: str = INBOX_WORKER_HEARTBEAT_SOURCE,
        completed_at: Optional[datetime] = None,
        summary: Optional[Dict[str, int]] = None,
        error: Optional[str] = None,
    ) -> None:
        completed = ensure_utc(completed_at) or utcnow()
        row = StripeWebhookHealthService._get_or_create_heartbeat_row(db, source=source)
        row.last_completed_at = completed
        row.last_summary = summary
        if error:
            row.last_error = error[:2000]
        else:
            row.last_error = None
            row.last_success_at = completed
        db.add(row)
        db.commit()

    @staticmethod
    def get_pipeline_health_snapshot(
        db: Session,
        *,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        return StripeWebhookHealthService._get_pipeline_health_snapshot(
            db,
            queue_model=StripeWebhookInbox,
            heartbeat_source=StripeWebhookHealthService.INBOX_WORKER_HEARTBEAT_SOURCE,
            heartbeat_max_age_seconds=settings.STRIPE_WEBHOOK_HEALTH_HEARTBEAT_MAX_AGE_SECONDS,
            max_due_pending_count=settings.STRIPE_WEBHOOK_HEALTH_MAX_DUE_PENDING_COUNT,
            max_oldest_due_pending_seconds=settings.STRIPE_WEBHOOK_HEALTH_MAX_OLDEST_DUE_PENDING_SECONDS,
            max_failed_count=settings.STRIPE_WEBHOOK_HEALTH_MAX_FAILED_COUNT,
            stale_lock_seconds=settings.STRIPE_WEBHOOK_HEALTH_STALE_LOCK_SECONDS,
            max_stale_lock_count=settings.STRIPE_WEBHOOK_HEALTH_MAX_STALE_LOCK_COUNT,
            now=now,
        )

    @staticmethod
    def get_cleanup_pipeline_health_snapshot(
        db: Session,
        *,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        return StripeWebhookHealthService._get_pipeline_health_snapshot(
            db,
            queue_model=StripePlanCleanupOutbox,
            heartbeat_source=StripeWebhookHealthService.CLEANUP_WORKER_HEARTBEAT_SOURCE,
            heartbeat_max_age_seconds=settings.STRIPE_PLAN_CLEANUP_HEALTH_HEARTBEAT_MAX_AGE_SECONDS,
            max_due_pending_count=settings.STRIPE_PLAN_CLEANUP_HEALTH_MAX_DUE_PENDING_COUNT,
            max_oldest_due_pending_seconds=settings.STRIPE_PLAN_CLEANUP_HEALTH_MAX_OLDEST_DUE_PENDING_SECONDS,
            max_failed_count=settings.STRIPE_PLAN_CLEANUP_HEALTH_MAX_FAILED_COUNT,
            stale_lock_seconds=settings.STRIPE_PLAN_CLEANUP_STALE_LOCK_SECONDS,
            max_stale_lock_count=settings.STRIPE_PLAN_CLEANUP_HEALTH_MAX_STALE_LOCK_COUNT,
            now=now,
        )

    @staticmethod
    def _get_pipeline_health_snapshot(
        db: Session,
        *,
        queue_model: Any,
        heartbeat_source: str,
        heartbeat_max_age_seconds: int,
        max_due_pending_count: int,
        max_oldest_due_pending_seconds: int,
        max_failed_count: int,
        stale_lock_seconds: int,
        max_stale_lock_count: int,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        current = ensure_utc(now) or utcnow()
        heartbeat_row = (
            db.query(StripeWebhookWorkerHeartbeat)
            .filter(
                StripeWebhookWorkerHeartbeat.source
                == heartbeat_source
            )
            .first()
        )

        heartbeat_reference = None
        if heartbeat_row is not None:
            heartbeat_reference = ensure_utc(heartbeat_row.last_completed_at) or ensure_utc(
                heartbeat_row.last_started_at
            )

        heartbeat_age_seconds = None
        if heartbeat_reference is not None:
            heartbeat_age_seconds = max((current - heartbeat_reference).total_seconds(), 0.0)

        due_pending_count, oldest_due_retry_at = (
            db.query(
                func.count(queue_model.id),
                func.min(queue_model.next_retry_at),
            )
            .filter(
                queue_model.status == "pending",
                queue_model.next_retry_at <= current,
            )
            .one()
        )
        total_pending_count = (
            db.query(func.count(queue_model.id))
            .filter(queue_model.status == "pending")
            .scalar()
            or 0
        )
        failed_count = (
            db.query(func.count(queue_model.id))
            .filter(queue_model.status == "failed")
            .scalar()
            or 0
        )
        stale_lock_cutoff = current - timedelta(seconds=stale_lock_seconds)
        stale_processing_count = (
            db.query(func.count(queue_model.id))
            .filter(
                queue_model.status == "processing",
                queue_model.locked_at.is_not(None),
                queue_model.locked_at <= stale_lock_cutoff,
            )
            .scalar()
            or 0
        )

        oldest_due_pending_age_seconds = None
        oldest_due_retry_at_utc = ensure_utc(oldest_due_retry_at)
        if oldest_due_retry_at_utc is not None:
            oldest_due_pending_age_seconds = max(
                (current - oldest_due_retry_at_utc).total_seconds(),
                0.0,
            )

        breaches: list[str] = []
        heartbeat_stale = (
            heartbeat_age_seconds is None
            or heartbeat_age_seconds > heartbeat_max_age_seconds
        )
        if heartbeat_stale:
            breaches.append("worker_heartbeat_stale")
        if int(due_pending_count or 0) > max_due_pending_count:
            breaches.append("due_pending_count_exceeded")
        if (
            oldest_due_pending_age_seconds is not None
            and oldest_due_pending_age_seconds > max_oldest_due_pending_seconds
        ):
            breaches.append("oldest_due_pending_age_exceeded")
        if int(failed_count or 0) > max_failed_count:
            breaches.append("failed_count_exceeded")
        if int(stale_processing_count or 0) > max_stale_lock_count:
            breaches.append("stale_processing_locks_exceeded")

        status = "healthy" if not breaches else "unhealthy"
        return {
            "status": status,
            "breaches": breaches,
            "heartbeat": {
                "source": heartbeat_source,
                "missing": heartbeat_row is None,
                "stale": heartbeat_stale,
                "age_seconds": heartbeat_age_seconds,
                "last_started_at": (
                    StripeWebhookHealthService._isoformat_or_none(heartbeat_row.last_started_at)
                    if heartbeat_row
                    else None
                ),
                "last_completed_at": (
                    StripeWebhookHealthService._isoformat_or_none(heartbeat_row.last_completed_at)
                    if heartbeat_row
                    else None
                ),
                "last_success_at": (
                    StripeWebhookHealthService._isoformat_or_none(heartbeat_row.last_success_at)
                    if heartbeat_row
                    else None
                ),
                "last_error": heartbeat_row.last_error if heartbeat_row else None,
            },
            "queue": {
                "pending_count": int(total_pending_count or 0),
                "due_pending_count": int(due_pending_count or 0),
                "failed_count": int(failed_count or 0),
                "stale_processing_count": int(stale_processing_count or 0),
                "oldest_due_retry_at": StripeWebhookHealthService._isoformat_or_none(
                    oldest_due_retry_at_utc
                ),
                "oldest_due_pending_age_seconds": oldest_due_pending_age_seconds,
            },
            "thresholds": {
                "heartbeat_max_age_seconds": heartbeat_max_age_seconds,
                "max_due_pending_count": max_due_pending_count,
                "max_oldest_due_pending_seconds": max_oldest_due_pending_seconds,
                "max_failed_count": max_failed_count,
                "stale_lock_seconds": stale_lock_seconds,
                "max_stale_processing_count": max_stale_lock_count,
            },
        }
