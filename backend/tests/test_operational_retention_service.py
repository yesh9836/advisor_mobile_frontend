from datetime import timedelta

import pytest

from app.core.config import settings
from app.core.security import get_password_hash
from app.db.timezone import utcnow
from app.models.notification import NotificationOutbox
from app.models.password_reset import PasswordResetRequestAttempt, PasswordResetToken
from app.models.purchase import ProcessedStripeEvent
from app.models.user import User
from app.services.operational_retention_service import OperationalRetentionService


@pytest.mark.integration
def test_operational_retention_deletes_only_expired_terminal_rows(db, monkeypatch):
    now = utcnow()
    monkeypatch.setattr(settings, "OPERATIONAL_RETENTION_BATCH_SIZE", 100)
    monkeypatch.setattr(settings, "PASSWORD_RESET_REQUEST_ATTEMPT_RETENTION_DAYS", 30)
    monkeypatch.setattr(settings, "PASSWORD_RESET_TOKEN_RETENTION_DAYS", 30)
    monkeypatch.setattr(settings, "NOTIFICATION_OUTBOX_RETENTION_DAYS", 90)
    monkeypatch.setattr(settings, "PROCESSED_STRIPE_EVENT_RETENTION_DAYS", 90)

    user = User(
        email="retention-advisor@example.com",
        name="Retention Advisor",
        phone="+15555550100",
        password_hash=get_password_hash("StrongPass123!"),
        role="advisor",
    )
    db.add(user)
    db.commit()

    db.add_all(
        [
            PasswordResetRequestAttempt(
                subject_hash="a" * 64,
                created_at=now - timedelta(days=31),
            ),
            PasswordResetRequestAttempt(
                subject_hash="b" * 64,
                created_at=now - timedelta(days=5),
            ),
            PasswordResetToken(
                user_id=user.id,
                token_hash="expired_token_hash",
                expires_at=now - timedelta(days=31),
                used_at=None,
                created_at=now - timedelta(days=31),
            ),
            PasswordResetToken(
                user_id=user.id,
                token_hash="used_token_hash",
                expires_at=now + timedelta(days=5),
                used_at=now - timedelta(days=31),
                created_at=now - timedelta(days=31),
            ),
            PasswordResetToken(
                user_id=user.id,
                token_hash="active_token_hash",
                expires_at=now + timedelta(days=2),
                used_at=None,
                created_at=now - timedelta(days=2),
            ),
            NotificationOutbox(
                user_id=user.id,
                lead_id=None,
                purchase_id=None,
                channel="email",
                event_type="retention_old_sent",
                recipient="advisor@example.com",
                subject="sent old",
                message_body="sent old",
                payload=None,
                idempotency_key="retention-sent-old",
                status="sent",
                attempt_count=1,
                max_attempts=5,
                next_retry_at=now - timedelta(days=95),
                sent_at=now - timedelta(days=95),
                created_at=now - timedelta(days=95),
            ),
            NotificationOutbox(
                user_id=user.id,
                lead_id=None,
                purchase_id=None,
                channel="email",
                event_type="retention_old_failed",
                recipient="advisor@example.com",
                subject="failed old",
                message_body="failed old",
                payload=None,
                idempotency_key="retention-failed-old",
                status="failed",
                attempt_count=5,
                max_attempts=5,
                next_retry_at=now - timedelta(days=95),
                created_at=now - timedelta(days=95),
            ),
            NotificationOutbox(
                user_id=user.id,
                lead_id=None,
                purchase_id=None,
                channel="email",
                event_type="retention_old_pending",
                recipient="advisor@example.com",
                subject="pending old",
                message_body="pending old",
                payload=None,
                idempotency_key="retention-pending-old",
                status="pending",
                attempt_count=0,
                max_attempts=5,
                next_retry_at=now - timedelta(days=95),
                created_at=now - timedelta(days=95),
            ),
            ProcessedStripeEvent(
                stripe_event_id="evt_retention_old",
                event_type="checkout.session.completed",
                processed_at=now - timedelta(days=95),
            ),
            ProcessedStripeEvent(
                stripe_event_id="evt_retention_recent",
                event_type="checkout.session.completed",
                processed_at=now - timedelta(days=2),
            ),
        ]
    )
    db.commit()

    summary = OperationalRetentionService.purge_expired_operational_rows(db, now=now)

    assert summary["password_reset_request_attempts_deleted"] == 1
    assert summary["password_reset_tokens_deleted"] == 2
    assert summary["notification_outbox_deleted"] == 2
    assert summary["processed_stripe_events_deleted"] == 1
    assert summary["total_deleted"] == 6

    assert db.query(PasswordResetRequestAttempt).count() == 1
    assert db.query(PasswordResetToken).count() == 1
    remaining_outbox_statuses = sorted(row.status for row in db.query(NotificationOutbox).all())
    assert remaining_outbox_statuses == ["pending"]
    remaining_event_ids = sorted(row.stripe_event_id for row in db.query(ProcessedStripeEvent).all())
    assert remaining_event_ids == ["evt_retention_recent"]


@pytest.mark.integration
def test_operational_retention_enforces_batch_size_per_table(db, monkeypatch):
    now = utcnow()
    monkeypatch.setattr(settings, "OPERATIONAL_RETENTION_BATCH_SIZE", 2)
    monkeypatch.setattr(settings, "PASSWORD_RESET_REQUEST_ATTEMPT_RETENTION_DAYS", 30)
    monkeypatch.setattr(settings, "PASSWORD_RESET_TOKEN_RETENTION_DAYS", 30)
    monkeypatch.setattr(settings, "NOTIFICATION_OUTBOX_RETENTION_DAYS", 90)
    monkeypatch.setattr(settings, "PROCESSED_STRIPE_EVENT_RETENTION_DAYS", 90)

    for idx in range(3):
        db.add(
            PasswordResetRequestAttempt(
                subject_hash=f"{idx:064d}",
                created_at=now - timedelta(days=31),
            )
        )
        db.add(
            ProcessedStripeEvent(
                stripe_event_id=f"evt_retention_batch_{idx}",
                event_type="checkout.session.completed",
                processed_at=now - timedelta(days=91),
            )
        )
    db.commit()

    summary = OperationalRetentionService.purge_expired_operational_rows(db, now=now)

    assert summary["batch_size"] == 2
    assert summary["password_reset_request_attempts_deleted"] == 2
    assert summary["processed_stripe_events_deleted"] == 2
    assert db.query(PasswordResetRequestAttempt).count() == 1
    assert db.query(ProcessedStripeEvent).count() == 1
