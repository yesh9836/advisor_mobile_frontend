from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Sequence

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.timezone import utcnow
from app.models.notification import NotificationOutbox
from app.models.password_reset import PasswordResetRequestAttempt, PasswordResetToken
from app.models.purchase import ProcessedStripeEvent


class OperationalRetentionService:
    """Batched retention cleanup for high-growth operational tables."""

    TERMINAL_NOTIFICATION_STATUSES: Sequence[str] = ("sent", "failed")

    @staticmethod
    def _delete_rows_by_id_batch(
        db: Session,
        *,
        id_query,
        model: Any,
        batch_size: int,
    ) -> int:
        row_ids = [row[0] for row in id_query.limit(batch_size).all()]
        if not row_ids:
            return 0
        deleted_count = (
            db.query(model)
            .filter(model.id.in_(row_ids))
            .delete(synchronize_session=False)
        )
        return int(deleted_count or 0)

    @staticmethod
    def purge_expired_operational_rows(
        db: Session,
        *,
        now: datetime | None = None,
        batch_size: int | None = None,
    ) -> Dict[str, int]:
        current = now or utcnow()
        max_batch_size = max(int(batch_size or settings.OPERATIONAL_RETENTION_BATCH_SIZE), 1)

        attempts_cutoff = current - timedelta(days=settings.PASSWORD_RESET_REQUEST_ATTEMPT_RETENTION_DAYS)
        tokens_cutoff = current - timedelta(days=settings.PASSWORD_RESET_TOKEN_RETENTION_DAYS)
        outbox_cutoff = current - timedelta(days=settings.NOTIFICATION_OUTBOX_RETENTION_DAYS)
        stripe_events_cutoff = current - timedelta(days=settings.PROCESSED_STRIPE_EVENT_RETENTION_DAYS)

        attempts_deleted = OperationalRetentionService._delete_rows_by_id_batch(
            db,
            id_query=(
                db.query(PasswordResetRequestAttempt.id)
                .filter(PasswordResetRequestAttempt.created_at < attempts_cutoff)
                .order_by(PasswordResetRequestAttempt.id.asc())
            ),
            model=PasswordResetRequestAttempt,
            batch_size=max_batch_size,
        )

        tokens_deleted = OperationalRetentionService._delete_rows_by_id_batch(
            db,
            id_query=(
                db.query(PasswordResetToken.id)
                .filter(
                    or_(
                        PasswordResetToken.expires_at < tokens_cutoff,
                        and_(
                            PasswordResetToken.used_at.is_not(None),
                            PasswordResetToken.used_at < tokens_cutoff,
                        ),
                    )
                )
                .order_by(PasswordResetToken.id.asc())
            ),
            model=PasswordResetToken,
            batch_size=max_batch_size,
        )

        outbox_deleted = OperationalRetentionService._delete_rows_by_id_batch(
            db,
            id_query=(
                db.query(NotificationOutbox.id)
                .filter(
                    NotificationOutbox.status.in_(OperationalRetentionService.TERMINAL_NOTIFICATION_STATUSES),
                    NotificationOutbox.created_at < outbox_cutoff,
                )
                .order_by(NotificationOutbox.id.asc())
            ),
            model=NotificationOutbox,
            batch_size=max_batch_size,
        )

        stripe_events_deleted = OperationalRetentionService._delete_rows_by_id_batch(
            db,
            id_query=(
                db.query(ProcessedStripeEvent.id)
                .filter(ProcessedStripeEvent.processed_at < stripe_events_cutoff)
                .order_by(ProcessedStripeEvent.id.asc())
            ),
            model=ProcessedStripeEvent,
            batch_size=max_batch_size,
        )

        db.commit()
        return {
            "batch_size": max_batch_size,
            "password_reset_request_attempts_deleted": attempts_deleted,
            "password_reset_tokens_deleted": tokens_deleted,
            "notification_outbox_deleted": outbox_deleted,
            "processed_stripe_events_deleted": stripe_events_deleted,
            "total_deleted": (
                attempts_deleted + tokens_deleted + outbox_deleted + stripe_events_deleted
            ),
        }
