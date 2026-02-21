from typing import Any, Dict, Iterable, List

import pytest

from app.models.purchase import StripeReconciliationCheckpoint, StripeWebhookInbox
from app.services.stripe_reconciliation_service import StripeReconciliationService


def _build_event(event_id: str, *, created: int, event_type: str) -> Dict[str, Any]:
    return {
        "id": event_id,
        "type": event_type,
        "created": created,
        "data": {"object": {"id": f"obj_{event_id}"}},
    }


class _FakeStripeEventList:
    def __init__(self, rows: List[Dict[str, Any]]) -> None:
        self._rows = rows

    def auto_paging_iter(self) -> Iterable[Dict[str, Any]]:
        yield from self._rows


@pytest.mark.integration
def test_reconciliation_enqueues_new_events_and_updates_checkpoint(db, monkeypatch):
    stripe_events = [
        _build_event(
            "evt_reconcile_1",
            created=1700000000,
            event_type="checkout.session.completed",
        ),
        _build_event(
            "evt_reconcile_2",
            created=1700000010,
            event_type="charge.refunded",
        ),
    ]
    list_call = {}

    monkeypatch.setattr(
        "app.services.stripe_reconciliation_service.PaymentService._init_stripe",
        lambda: None,
    )
    monkeypatch.setattr(
        "app.services.stripe_reconciliation_service.settings.STRIPE_RECONCILIATION_LOOKBACK_SECONDS",
        9999999,
    )
    monkeypatch.setattr(
        "app.services.stripe_reconciliation_service.settings.STRIPE_RECONCILIATION_SAFETY_WINDOW_SECONDS",
        0,
    )
    monkeypatch.setattr(
        "app.services.stripe_reconciliation_service.settings.STRIPE_RECONCILIATION_PAGE_SIZE",
        50,
    )

    def _mock_event_list(**kwargs):
        list_call.update(kwargs)
        return _FakeStripeEventList(stripe_events)

    monkeypatch.setattr("app.services.stripe_reconciliation_service.stripe.Event.list", _mock_event_list)

    summary = StripeReconciliationService.run_once(db=db)

    assert summary["scanned"] == 2
    assert summary["considered"] == 2
    assert summary["enqueued"] == 2
    assert list_call["limit"] == 50
    assert set(list_call["types"]) == set(StripeReconciliationService.RELEVANT_EVENT_TYPES)
    assert "checkout.session.expired" in list_call["types"]

    inbox_rows = (
        db.query(StripeWebhookInbox)
        .order_by(StripeWebhookInbox.stripe_event_id.asc())
        .all()
    )
    assert [row.stripe_event_id for row in inbox_rows] == ["evt_reconcile_1", "evt_reconcile_2"]

    checkpoint = (
        db.query(StripeReconciliationCheckpoint)
        .filter(StripeReconciliationCheckpoint.source == StripeReconciliationService.CHECKPOINT_SOURCE)
        .first()
    )
    assert checkpoint is not None
    assert int(checkpoint.last_event_created) == 1700000010
    assert checkpoint.last_event_id == "evt_reconcile_2"


@pytest.mark.integration
def test_reconciliation_skips_events_at_or_before_checkpoint(db, monkeypatch):
    stripe_events = [
        _build_event(
            "evt_reconcile_skip_1",
            created=1700000100,
            event_type="checkout.session.completed",
        ),
        _build_event(
            "evt_reconcile_skip_2",
            created=1700000110,
            event_type="payment_intent.succeeded",
        ),
    ]
    monkeypatch.setattr(
        "app.services.stripe_reconciliation_service.PaymentService._init_stripe",
        lambda: None,
    )
    monkeypatch.setattr(
        "app.services.stripe_reconciliation_service.settings.STRIPE_RECONCILIATION_LOOKBACK_SECONDS",
        9999999,
    )
    monkeypatch.setattr(
        "app.services.stripe_reconciliation_service.settings.STRIPE_RECONCILIATION_SAFETY_WINDOW_SECONDS",
        0,
    )
    monkeypatch.setattr(
        "app.services.stripe_reconciliation_service.stripe.Event.list",
        lambda **kwargs: _FakeStripeEventList(stripe_events),
    )

    first = StripeReconciliationService.run_once(db=db)
    second = StripeReconciliationService.run_once(db=db)

    assert first["enqueued"] == 2
    assert second["enqueued"] == 0
    assert second["considered"] == 0
    assert second["skipped_before_checkpoint"] == 2
    assert (
        db.query(StripeWebhookInbox)
        .filter(StripeWebhookInbox.stripe_event_id.in_(["evt_reconcile_skip_1", "evt_reconcile_skip_2"]))
        .count()
        == 2
    )


@pytest.mark.integration
def test_reconciliation_skips_livemode_mismatch_events(db, monkeypatch):
    stripe_events = [
        {
            "id": "evt_reconcile_livemode_skip",
            "type": "charge.refunded",
            "created": 1700000200,
            "livemode": True,
            "data": {"object": {"id": "obj_skip"}},
        },
        {
            "id": "evt_reconcile_livemode_ok",
            "type": "payment_intent.succeeded",
            "created": 1700000210,
            "livemode": False,
            "data": {"object": {"id": "obj_ok"}},
        },
    ]

    monkeypatch.setattr(
        "app.services.stripe_reconciliation_service.PaymentService._init_stripe",
        lambda: None,
    )
    monkeypatch.setattr(
        "app.services.stripe_reconciliation_service.settings.STRIPE_WEBHOOK_EXPECT_LIVEMODE",
        False,
    )
    monkeypatch.setattr(
        "app.services.stripe_reconciliation_service.settings.STRIPE_RECONCILIATION_LOOKBACK_SECONDS",
        9999999,
    )
    monkeypatch.setattr(
        "app.services.stripe_reconciliation_service.settings.STRIPE_RECONCILIATION_SAFETY_WINDOW_SECONDS",
        0,
    )
    monkeypatch.setattr(
        "app.services.stripe_reconciliation_service.stripe.Event.list",
        lambda **kwargs: _FakeStripeEventList(stripe_events),
    )

    summary = StripeReconciliationService.run_once(db=db)

    assert summary["scanned"] == 2
    assert summary["considered"] == 2
    assert summary["enqueued"] == 1
    assert summary["duplicates"] == 0
    assert summary["skipped_livemode"] == 1
    inbox_rows = (
        db.query(StripeWebhookInbox)
        .order_by(StripeWebhookInbox.stripe_event_id.asc())
        .all()
    )
    assert [row.stripe_event_id for row in inbox_rows] == ["evt_reconcile_livemode_ok"]
