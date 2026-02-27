from datetime import datetime, timedelta, timezone

import pytest

from app.models.purchase import StripePlanCleanupOutbox, StripeWebhookWorkerHeartbeat
from app.services.stripe_plan_cleanup_outbox_service import StripePlanCleanupOutboxService
from app.services.stripe_webhook_health_service import StripeWebhookHealthService


@pytest.mark.integration
def test_enqueue_cleanup_dedupes_by_idempotency_key(db):
    first = StripePlanCleanupOutboxService.enqueue_cleanup(
        db=db,
        source="admin_plan_update",
        stripe_price_id="price_cleanup_dup",
        stripe_product_id="prod_cleanup_dup",
    )
    second = StripePlanCleanupOutboxService.enqueue_cleanup(
        db=db,
        source="admin_plan_update",
        stripe_price_id="price_cleanup_dup",
        stripe_product_id="prod_cleanup_dup",
    )

    assert first is True
    assert second is False
    assert (
        db.query(StripePlanCleanupOutbox)
        .filter(StripePlanCleanupOutbox.source == "admin_plan_update")
        .count()
        == 1
    )


@pytest.mark.integration
def test_process_outbox_batch_marks_rows_processed(db, monkeypatch):
    StripePlanCleanupOutboxService.enqueue_cleanup(
        db=db,
        source="admin_plan_create",
        stripe_price_id="price_cleanup_success",
        stripe_product_id="prod_cleanup_success",
    )

    seen = {}
    monkeypatch.setattr(
        "app.services.stripe_plan_cleanup_outbox_service.PaymentService.deactivate_stripe_plan_artifacts",
        lambda stripe_price_id, stripe_product_id: seen.setdefault(
            "ids", (stripe_price_id, stripe_product_id)
        )
        or {"price_deactivated": True, "product_deactivated": True},
    )

    summary = StripePlanCleanupOutboxService.process_outbox_batch(db=db, batch_size=10)
    assert summary == {"selected": 1, "processed": 1, "retried": 0, "failed": 0}
    assert seen.get("ids") == ("price_cleanup_success", "prod_cleanup_success")

    row = (
        db.query(StripePlanCleanupOutbox)
        .filter(StripePlanCleanupOutbox.source == "admin_plan_create")
        .first()
    )
    assert row is not None
    assert row.status == "processed"
    assert row.processed_at is not None
    assert row.locked_at is None


@pytest.mark.integration
def test_process_outbox_batch_retries_then_fails_after_max_attempts(db, monkeypatch):
    StripePlanCleanupOutboxService.enqueue_cleanup(
        db=db,
        source="admin_plan_update",
        stripe_price_id="price_cleanup_retry",
        stripe_product_id="prod_cleanup_retry",
    )
    row = (
        db.query(StripePlanCleanupOutbox)
        .filter(StripePlanCleanupOutbox.stripe_price_id == "price_cleanup_retry")
        .first()
    )
    assert row is not None
    row.max_attempts = 2
    db.add(row)
    db.commit()

    monkeypatch.setattr(
        "app.services.stripe_plan_cleanup_outbox_service.PaymentService.deactivate_stripe_plan_artifacts",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("cleanup transient failure")),
    )

    first = StripePlanCleanupOutboxService.process_outbox_batch(db=db, batch_size=10)
    assert first == {"selected": 1, "processed": 0, "retried": 1, "failed": 0}

    retried_row = (
        db.query(StripePlanCleanupOutbox)
        .filter(StripePlanCleanupOutbox.stripe_price_id == "price_cleanup_retry")
        .first()
    )
    assert retried_row is not None
    retried_row.next_retry_at = datetime.now(timezone.utc)
    db.add(retried_row)
    db.commit()

    second = StripePlanCleanupOutboxService.process_outbox_batch(db=db, batch_size=10)
    assert second == {"selected": 1, "processed": 0, "retried": 0, "failed": 1}

    refreshed = (
        db.query(StripePlanCleanupOutbox)
        .filter(StripePlanCleanupOutbox.stripe_price_id == "price_cleanup_retry")
        .first()
    )
    assert refreshed is not None
    assert refreshed.status == "failed"
    assert int(refreshed.attempt_count or 0) == 2
    assert refreshed.last_error == "cleanup transient failure"


@pytest.mark.integration
def test_reclaim_stale_processing_rows_requeues_or_fails_based_on_attempts(db):
    now = datetime.now(timezone.utc)
    requeue_row = StripePlanCleanupOutbox(
        source="admin_plan_update",
        stripe_price_id="price_reclaim_pending",
        stripe_product_id="prod_reclaim_pending",
        status="processing",
        attempt_count=1,
        max_attempts=3,
        next_retry_at=now,
        locked_at=now - timedelta(minutes=10),
        idempotency_key="stripe-plan-cleanup-reclaim-pending",
    )
    fail_row = StripePlanCleanupOutbox(
        source="admin_plan_update",
        stripe_price_id="price_reclaim_failed",
        stripe_product_id="prod_reclaim_failed",
        status="processing",
        attempt_count=3,
        max_attempts=3,
        next_retry_at=now,
        locked_at=now - timedelta(minutes=10),
        idempotency_key="stripe-plan-cleanup-reclaim-failed",
    )
    db.add_all([requeue_row, fail_row])
    db.commit()

    summary = StripePlanCleanupOutboxService.reclaim_stale_processing_rows(
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
def test_process_stripe_plan_cleanup_outbox_script_records_worker_heartbeat(session_factory, monkeypatch):
    from scripts import process_stripe_plan_cleanup_outbox as worker_script

    call_order = []
    monkeypatch.setattr(worker_script, "SessionLocal", session_factory)
    monkeypatch.setattr(
        worker_script.StripePlanCleanupOutboxService,
        "reclaim_stale_processing_rows",
        lambda db: call_order.append("reclaim")
        or {"stale_selected": 0, "reclaimed_pending": 0, "reclaimed_failed": 0},
    )
    monkeypatch.setattr(
        worker_script.StripePlanCleanupOutboxService,
        "process_outbox_batch",
        lambda db: call_order.append("process")
        or {"selected": 0, "processed": 0, "retried": 0, "failed": 0},
    )

    exit_code = worker_script.main()

    assert exit_code == 0
    assert call_order == ["reclaim", "process"]
    db = session_factory()
    try:
        heartbeat = (
            db.query(StripeWebhookWorkerHeartbeat)
            .filter(
                StripeWebhookWorkerHeartbeat.source
                == StripePlanCleanupOutboxService.WORKER_HEARTBEAT_SOURCE
            )
            .first()
        )
        assert heartbeat is not None
        assert heartbeat.last_started_at is not None
        assert heartbeat.last_completed_at is not None
        assert heartbeat.last_success_at is not None
        assert heartbeat.last_error is None
        assert heartbeat.last_summary == {
            "selected": 0,
            "processed": 0,
            "retried": 0,
            "failed": 0,
        }
    finally:
        db.close()
