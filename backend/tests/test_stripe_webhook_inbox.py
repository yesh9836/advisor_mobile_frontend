from datetime import datetime, timezone

import pytest

from app.models.purchase import LeadCreditLedger, StripeWebhookInbox, StripeWebhookWorkerHeartbeat
from app.services.stripe_webhook_inbox_service import StripeWebhookInboxService
from app.services.stripe_webhook_health_service import StripeWebhookHealthService
from app.services.subscription_service import StripeWebhookProcessingError, SubscriptionService


def _build_event(event_id: str, event_type: str = "checkout.session.completed") -> dict:
    return {
        "id": event_id,
        "type": event_type,
        "data": {"object": {"id": f"cs_{event_id}"}},
    }


@pytest.mark.integration
def test_enqueue_event_dedupes_by_stripe_event_id(db):
    first = StripeWebhookInboxService.enqueue_event(db=db, event=_build_event("evt_inbox_dup"))
    second = StripeWebhookInboxService.enqueue_event(db=db, event=_build_event("evt_inbox_dup"))

    assert first is True
    assert second is False
    assert (
        db.query(StripeWebhookInbox)
        .filter(StripeWebhookInbox.stripe_event_id == "evt_inbox_dup")
        .count()
        == 1
    )


@pytest.mark.integration
def test_process_inbox_batch_marks_rows_processed(db, monkeypatch):
    StripeWebhookInboxService.enqueue_event(db=db, event=_build_event("evt_inbox_success"))

    seen = {}
    monkeypatch.setattr(
        "app.services.stripe_webhook_inbox_service.SubscriptionService.handle_webhook_event_threadsafe",
        lambda event: seen.setdefault("event_id", event["id"]),
    )

    summary = StripeWebhookInboxService.process_inbox_batch(db=db, batch_size=10)
    assert summary["selected"] == 1
    assert summary["processed"] == 1
    assert summary["retried"] == 0
    assert summary["failed"] == 0
    assert seen.get("event_id") == "evt_inbox_success"

    row = (
        db.query(StripeWebhookInbox)
        .filter(StripeWebhookInbox.stripe_event_id == "evt_inbox_success")
        .first()
    )
    assert row is not None
    assert row.status == "processed"
    assert row.processed_at is not None
    assert row.locked_at is None


@pytest.mark.integration
def test_process_inbox_batch_retries_then_fails_after_max_attempts(db, monkeypatch):
    StripeWebhookInboxService.enqueue_event(db=db, event=_build_event("evt_inbox_retry"))
    row = (
        db.query(StripeWebhookInbox)
        .filter(StripeWebhookInbox.stripe_event_id == "evt_inbox_retry")
        .first()
    )
    assert row is not None
    row.max_attempts = 2
    db.add(row)
    db.commit()

    monkeypatch.setattr(
        "app.services.stripe_webhook_inbox_service.SubscriptionService.handle_webhook_event_threadsafe",
        lambda event: (_ for _ in ()).throw(StripeWebhookProcessingError("worker retry")),
    )

    first = StripeWebhookInboxService.process_inbox_batch(db=db, batch_size=10)
    assert first["selected"] == 1
    assert first["processed"] == 0
    assert first["retried"] == 1
    assert first["failed"] == 0

    retried_row = (
        db.query(StripeWebhookInbox)
        .filter(StripeWebhookInbox.stripe_event_id == "evt_inbox_retry")
        .first()
    )
    assert retried_row is not None
    retried_row.next_retry_at = datetime.now(timezone.utc)
    db.add(retried_row)
    db.commit()

    second = StripeWebhookInboxService.process_inbox_batch(db=db, batch_size=10)
    assert second["selected"] == 1
    assert second["processed"] == 0
    assert second["retried"] == 0
    assert second["failed"] == 1

    refreshed = (
        db.query(StripeWebhookInbox)
        .filter(StripeWebhookInbox.stripe_event_id == "evt_inbox_retry")
        .first()
    )
    assert refreshed is not None
    assert refreshed.status == "failed"
    assert int(refreshed.attempt_count or 0) == 2
    assert refreshed.last_error == "worker retry"


@pytest.mark.integration
def test_process_inbox_batch_ignores_livemode_mismatch_in_core_processor(
    db,
    monkeypatch,
    user_factory,
    plan_factory,
    purchase_factory,
):
    advisor = user_factory(
        role="advisor",
        email="inbox.livemode.guard@example.com",
        password="InboxLivemodeGuard123!",
    )
    package = plan_factory(
        name="Inbox Livemode Guard Package",
        state_limit=1,
        daily_download_limit=4,
        stripe_price_id="price_inbox_livemode_guard",
    )
    purchase = purchase_factory(
        user_id=advisor.id,
        package_id=package.id,
        credits_total=4,
        credits_remaining=4,
        status="completed",
        stripe_checkout_session_id="cs_inbox_livemode_guard",
        stripe_payment_intent_id="pi_inbox_livemode_guard",
    )

    metric_counters = []
    monkeypatch.setattr("app.services.subscription_service.PaymentService._init_stripe", lambda: None)
    monkeypatch.setattr("app.services.subscription_service.settings.STRIPE_WEBHOOK_EXPECT_LIVEMODE", False)
    monkeypatch.setattr(
        "app.services.subscription_service.MetricsService.increment",
        lambda name, value=1, tags=None: metric_counters.append((name, value, tags or {})),
    )
    monkeypatch.setattr(
        "app.services.stripe_webhook_inbox_service.SubscriptionService.handle_webhook_event_threadsafe",
        lambda event: SubscriptionService.handle_webhook_event(db=db, event=event),
    )

    StripeWebhookInboxService.enqueue_event(
        db=db,
        event={
            "id": "evt_inbox_livemode_mismatch",
            "type": "charge.refunded",
            "livemode": True,
            "data": {
                "object": {
                    "id": "ch_inbox_livemode_mismatch",
                    "payment_intent": "pi_inbox_livemode_guard",
                    "amount_refunded": purchase.amount_cents,
                    "reason": "requested_by_customer",
                }
            },
        },
    )

    summary = StripeWebhookInboxService.process_inbox_batch(db=db, batch_size=10)
    assert summary["selected"] == 1
    assert summary["processed"] == 1
    assert summary["retried"] == 0
    assert summary["failed"] == 0
    assert summary["non_retryable"] == 0

    db.refresh(purchase)
    assert purchase.status == "completed"
    assert purchase.credits_remaining == 4
    assert (
        db.query(LeadCreditLedger)
        .filter(
            LeadCreditLedger.purchase_id == purchase.id,
            LeadCreditLedger.movement_type == "refund_adjustment",
        )
        .count()
        == 0
    )
    assert any(
        name == "purchase_webhook_ignored_total"
        and tags.get("reason") == "livemode_mismatch"
        and tags.get("source") == "core_processor"
        for name, _, tags in metric_counters
    )


@pytest.mark.integration
def test_process_stripe_webhook_inbox_script_records_worker_heartbeat(session_factory, monkeypatch):
    from scripts import process_stripe_webhook_inbox as worker_script

    monkeypatch.setattr(worker_script, "SessionLocal", session_factory)
    monkeypatch.setattr(
        worker_script.StripeWebhookInboxService,
        "process_inbox_batch",
        lambda db: {"selected": 0, "processed": 0, "retried": 0, "failed": 0, "non_retryable": 0},
    )

    exit_code = worker_script.main()

    assert exit_code == 0
    db = session_factory()
    try:
        heartbeat = (
            db.query(StripeWebhookWorkerHeartbeat)
            .filter(
                StripeWebhookWorkerHeartbeat.source
                == StripeWebhookHealthService.INBOX_WORKER_HEARTBEAT_SOURCE
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
            "non_retryable": 0,
        }
    finally:
        db.close()
