from datetime import datetime, timezone

import pytest

from app.models.purchase import StripeWebhookInbox
from app.services.stripe_webhook_inbox_service import StripeWebhookInboxService
from app.services.subscription_service import StripeWebhookProcessingError


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
