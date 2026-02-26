from datetime import timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.db.timezone import utcnow
from app.models.delivery_settings import AdvisorDeliverySettings
from app.models.notification import NotificationOutbox
from app.services.lead_service import LeadService
from app.services.notification_service import NotificationDispatchResult, NotificationService


def _enable_notifications(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "NOTIFICATIONS_ENABLED", True)
    monkeypatch.setattr(settings, "NOTIFICATION_EMAIL_ENABLED", True)
    monkeypatch.setattr(settings, "NOTIFICATION_SMS_ENABLED", True)
    monkeypatch.setattr(settings, "NOTIFICATION_OUTBOX_MAX_ATTEMPTS", 3)


@pytest.mark.integration
def test_enqueue_lead_delivery_notifications_is_idempotent_and_channel_scoped(
    db,
    monkeypatch,
    user_factory,
    lead_factory,
):
    _enable_notifications(monkeypatch)
    advisor = user_factory(
        role="advisor",
        email="notify.enqueue@example.com",
        password="NotifyEnqueue123!",
    )
    db.add(
        AdvisorDeliverySettings(
            user_id=advisor.id,
            email_alerts_enabled=True,
            sms_alerts_enabled=True,
            version=1,
        )
    )
    db.commit()

    lead = lead_factory(state_code="CA", first_name="Jordan", last_name="Miles")
    first = NotificationService.enqueue_lead_delivery_notifications(
        db=db,
        user_id=advisor.id,
        lead_ids=[lead.id],
        purchase_id=None,
        source_event="test_enqueue",
    )
    db.flush()
    assert first == {"enqueued_total": 2, "enqueued_email": 1, "enqueued_sms": 1}

    second = NotificationService.enqueue_lead_delivery_notifications(
        db=db,
        user_id=advisor.id,
        lead_ids=[lead.id],
        purchase_id=None,
        source_event="test_enqueue",
    )
    assert second == {"enqueued_total": 0, "enqueued_email": 0, "enqueued_sms": 0}

    rows = (
        db.query(NotificationOutbox)
        .filter(NotificationOutbox.user_id == advisor.id, NotificationOutbox.lead_id == lead.id)
        .order_by(NotificationOutbox.channel.asc())
        .all()
    )
    assert [row.channel for row in rows] == ["email", "sms"]
    assert all(row.status == "pending" for row in rows)


@pytest.mark.integration
def test_enqueue_lead_delivery_notifications_respects_advisor_opt_out(
    db,
    monkeypatch,
    user_factory,
    lead_factory,
):
    _enable_notifications(monkeypatch)
    advisor = user_factory(
        role="advisor",
        email="notify.optout@example.com",
        password="NotifyOptOut123!",
    )
    db.add(
        AdvisorDeliverySettings(
            user_id=advisor.id,
            email_alerts_enabled=False,
            sms_alerts_enabled=False,
            version=1,
        )
    )
    db.commit()

    lead = lead_factory(state_code="CA", first_name="Alex", last_name="NoAlerts")
    summary = NotificationService.enqueue_lead_delivery_notifications(
        db=db,
        user_id=advisor.id,
        lead_ids=[lead.id],
        purchase_id=None,
        source_event="test_opt_out",
    )
    assert summary == {"enqueued_total": 0, "enqueued_email": 0, "enqueued_sms": 0}

    rows = (
        db.query(NotificationOutbox)
        .filter(NotificationOutbox.user_id == advisor.id, NotificationOutbox.lead_id == lead.id)
        .all()
    )
    assert rows == []


@pytest.mark.integration
def test_enqueue_lead_delivery_notifications_handles_duplicate_conflict_without_rolling_back_outer_tx(
    db,
    monkeypatch,
    user_factory,
    lead_factory,
):
    _enable_notifications(monkeypatch)
    advisor = user_factory(
        role="advisor",
        email="notify.enqueue.duplicate@example.com",
        password="NotifyEnqueueDuplicate123!",
    )
    db.add(
        AdvisorDeliverySettings(
            user_id=advisor.id,
            email_alerts_enabled=True,
            sms_alerts_enabled=True,
            version=1,
        )
    )
    db.commit()

    lead = lead_factory(state_code="CA", first_name="Morgan", last_name="Reed")
    purchase_id = 42
    email_key = NotificationService._build_idempotency_key(
        channel="email",
        user_id=advisor.id,
        lead_id=lead.id,
        purchase_id=purchase_id,
        event_type=NotificationService.LEAD_DELIVERED_EVENT,
    )
    db.add(
        NotificationOutbox(
            user_id=advisor.id,
            lead_id=lead.id,
            purchase_id=purchase_id,
            channel="email",
            event_type=NotificationService.LEAD_DELIVERED_EVENT,
            recipient=advisor.email,
            subject="Existing duplicate row",
            message_body="seeded",
            payload={"source_event": "seed"},
            idempotency_key=email_key,
            status="pending",
            attempt_count=0,
            max_attempts=3,
            next_retry_at=utcnow(),
        )
    )
    db.commit()

    summary = NotificationService.enqueue_lead_delivery_notifications(
        db=db,
        user_id=advisor.id,
        lead_ids=[lead.id],
        purchase_id=purchase_id,
        source_event="test_duplicate_conflict",
    )
    assert summary == {"enqueued_total": 1, "enqueued_email": 0, "enqueued_sms": 1}

    advisor.name = "Outer Transaction Survived"
    db.add(advisor)
    db.commit()
    db.refresh(advisor)
    assert advisor.name == "Outer Transaction Survived"

    rows = (
        db.query(NotificationOutbox)
        .filter(
            NotificationOutbox.user_id == advisor.id,
            NotificationOutbox.lead_id == lead.id,
            NotificationOutbox.purchase_id == purchase_id,
        )
        .order_by(NotificationOutbox.channel.asc())
        .all()
    )
    assert [row.channel for row in rows] == ["email", "sms"]


@pytest.mark.integration
def test_enqueue_lead_delivery_notifications_reraises_non_duplicate_integrity_error(
    db,
    monkeypatch,
    user_factory,
    lead_factory,
):
    _enable_notifications(monkeypatch)
    advisor = user_factory(
        role="advisor",
        email="notify.enqueue.integrity@example.com",
        password="NotifyEnqueueIntegrity123!",
    )
    db.add(
        AdvisorDeliverySettings(
            user_id=advisor.id,
            email_alerts_enabled=True,
            sms_alerts_enabled=False,
            version=1,
        )
    )
    db.commit()
    lead = lead_factory(state_code="CA", first_name="Jamie", last_name="Miles")

    original_flush = db.flush

    def _raise_integrity_error(*args, **kwargs):
        raise IntegrityError(
            statement="insert into notification_outbox (...)",
            params={},
            orig=Exception("foreign key constraint failed"),
        )

    monkeypatch.setattr(db, "flush", _raise_integrity_error)
    with pytest.raises(IntegrityError):
        NotificationService.enqueue_lead_delivery_notifications(
            db=db,
            user_id=advisor.id,
            lead_ids=[lead.id],
            purchase_id=None,
            source_event="test_non_duplicate_integrity",
        )

    monkeypatch.setattr(db, "flush", original_flush)


@pytest.mark.integration
def test_reconcile_pending_purchase_assignments_enqueues_lead_notifications(
    db,
    monkeypatch,
    user_factory,
    license_factory,
    plan_factory,
    purchase_factory,
    lead_factory,
):
    _enable_notifications(monkeypatch)
    advisor = user_factory(
        role="advisor",
        email="notify.reconcile@example.com",
        password="NotifyReconcile123!",
    )
    db.add(
        AdvisorDeliverySettings(
            user_id=advisor.id,
            email_alerts_enabled=True,
            sms_alerts_enabled=False,
            version=1,
        )
    )
    db.commit()

    license_factory(user_id=advisor.id, state="CA", status="verified")
    package = plan_factory(name="Notify Reconcile Package", state_limit=1, daily_download_limit=1)
    purchase = purchase_factory(
        user_id=advisor.id,
        package_id=package.id,
        credits_total=1,
        credits_remaining=1,
        status="completed",
    )
    lead = lead_factory(state_code="CA", first_name="Taylor", last_name="Lead")

    summary = LeadService.reconcile_pending_purchase_assignments(
        db=db,
        state_codes=["CA"],
        source_event="test_reconcile",
        max_purchases=25,
    )
    assert summary["newly_assigned_count"] == 1

    rows = (
        db.query(NotificationOutbox)
        .filter(
            NotificationOutbox.user_id == advisor.id,
            NotificationOutbox.purchase_id == purchase.id,
            NotificationOutbox.lead_id == lead.id,
        )
        .all()
    )
    assert len(rows) == 1
    assert rows[0].channel == "email"
    assert rows[0].event_type == NotificationService.LEAD_DELIVERED_EVENT


@pytest.mark.integration
def test_process_outbox_batch_marks_rows_sent_on_success(db, monkeypatch, user_factory):
    _enable_notifications(monkeypatch)
    advisor = user_factory(
        role="advisor",
        email="notify.worker.success@example.com",
        password="NotifyWorkerSuccess123!",
    )
    row = NotificationOutbox(
        user_id=advisor.id,
        channel="email",
        event_type="lead_delivered",
        recipient=advisor.email,
        subject="Lead delivered",
        message_body="You have a new lead",
        payload=None,
        idempotency_key="lead_delivered:email:u1:l1:p1",
        status="pending",
        attempt_count=0,
        max_attempts=3,
        next_retry_at=utcnow() - timedelta(seconds=1),
    )
    db.add(row)
    db.commit()

    monkeypatch.setattr(
        NotificationService,
        "_dispatch_row",
        staticmethod(lambda _row: NotificationDispatchResult(success=True, provider_message_id="msg-123")),
    )

    summary = NotificationService.process_outbox_batch(db=db, batch_size=10)
    assert summary == {"selected": 1, "sent": 1, "retried": 0, "failed": 0}

    db.refresh(row)
    assert row.status == "sent"
    assert row.attempt_count == 1
    assert row.provider_message_id == "msg-123"


@pytest.mark.integration
def test_process_outbox_batch_retries_and_then_fails_after_max_attempts(db, monkeypatch, user_factory):
    _enable_notifications(monkeypatch)
    advisor = user_factory(
        role="advisor",
        email="notify.worker.fail@example.com",
        password="NotifyWorkerFail123!",
    )
    row = NotificationOutbox(
        user_id=advisor.id,
        channel="sms",
        event_type="lead_delivered",
        recipient=advisor.phone or "+15550000000",
        subject=None,
        message_body="New lead delivered",
        payload=None,
        idempotency_key="lead_delivered:sms:u2:l2:p2",
        status="pending",
        attempt_count=0,
        max_attempts=2,
        next_retry_at=utcnow() - timedelta(seconds=1),
    )
    db.add(row)
    db.commit()

    monkeypatch.setattr(
        NotificationService,
        "_dispatch_row",
        staticmethod(lambda _row: NotificationDispatchResult(success=False, error="provider outage")),
    )

    first = NotificationService.process_outbox_batch(db=db, batch_size=10)
    assert first == {"selected": 1, "sent": 0, "retried": 1, "failed": 0}
    db.refresh(row)
    assert row.status == "pending"
    assert row.attempt_count == 1

    row.next_retry_at = utcnow() - timedelta(seconds=1)
    db.add(row)
    db.commit()

    second = NotificationService.process_outbox_batch(db=db, batch_size=10)
    assert second == {"selected": 1, "sent": 0, "retried": 0, "failed": 1}
    db.refresh(row)
    assert row.status == "failed"
    assert row.attempt_count == 2
    assert row.last_error == "provider outage"


@pytest.mark.integration
def test_reclaim_stale_processing_rows_requeues_or_fails_based_on_attempts(db, user_factory):
    advisor = user_factory(
        role="advisor",
        email="notify.worker.reclaim@example.com",
        password="NotifyWorkerReclaim123!",
    )
    now = utcnow()
    requeue_row = NotificationOutbox(
        user_id=advisor.id,
        channel="email",
        event_type="lead_delivered",
        recipient=advisor.email,
        subject="Lead delivered",
        message_body="You have a new lead",
        payload=None,
        idempotency_key="reclaim-notification-pending",
        status="processing",
        attempt_count=1,
        max_attempts=3,
        next_retry_at=now + timedelta(minutes=5),
        locked_at=now - timedelta(minutes=10),
    )
    fail_row = NotificationOutbox(
        user_id=advisor.id,
        channel="sms",
        event_type="lead_delivered",
        recipient=advisor.phone or "+15550000001",
        subject=None,
        message_body="You have a new lead",
        payload=None,
        idempotency_key="reclaim-notification-failed",
        status="processing",
        attempt_count=3,
        max_attempts=3,
        next_retry_at=now + timedelta(minutes=5),
        locked_at=now - timedelta(minutes=10),
    )
    db.add_all([requeue_row, fail_row])
    db.commit()

    summary = NotificationService.reclaim_stale_processing_rows(
        db,
        now=now,
        stale_lock_seconds=60,
    )
    assert summary == {"stale_selected": 2, "reclaimed_pending": 1, "reclaimed_failed": 1}

    db.refresh(requeue_row)
    db.refresh(fail_row)
    assert requeue_row.status == "pending"
    assert requeue_row.locked_at is None
    assert requeue_row.next_retry_at == now
    assert requeue_row.last_error == "stale processing lock reclaimed"
    assert fail_row.status == "failed"
    assert fail_row.locked_at is None
    assert fail_row.next_retry_at == now
    assert fail_row.last_error == "stale processing lock reclaimed"


@pytest.mark.integration
def test_process_notification_outbox_script_reclaims_stale_rows_before_processing(session_factory, monkeypatch):
    from scripts import process_notification_outbox as worker_script

    call_order = []
    monkeypatch.setattr(worker_script, "SessionLocal", session_factory)
    monkeypatch.setattr(
        worker_script.NotificationService,
        "reclaim_stale_processing_rows",
        lambda db: call_order.append("reclaim") or {"stale_selected": 0, "reclaimed_pending": 0, "reclaimed_failed": 0},
    )
    monkeypatch.setattr(
        worker_script.NotificationService,
        "process_outbox_batch",
        lambda db: call_order.append("process") or {"selected": 0, "sent": 0, "retried": 0, "failed": 0},
    )

    exit_code = worker_script.main()

    assert exit_code == 0
    assert call_order == ["reclaim", "process"]
