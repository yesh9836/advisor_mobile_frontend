from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier
from typing import Any, Dict

import pytest

from app.models.purchase import LeadCreditLedger, LeadPurchase, ProcessedStripeEvent
from app.services.subscription_service import SubscriptionService


def _build_checkout_event(
    *,
    event_id: str,
    session_id: str,
    payment_intent_id: str,
    user_id: int,
    package_id: int,
    amount_cents: int,
) -> Dict[str, Any]:
    return {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": session_id,
                "mode": "payment",
                "payment_status": "paid",
                "payment_intent": payment_intent_id,
                "amount_total": amount_cents,
                "currency": "usd",
                "created": int(datetime.now(timezone.utc).timestamp()),
                "metadata": {
                    "user_id": str(user_id),
                    "package_id": str(package_id),
                },
            }
        },
    }


def _run_webhook_in_thread(session_factory, event: Dict[str, Any], start_barrier: Barrier):
    db = session_factory()
    try:
        start_barrier.wait(timeout=5)
        SubscriptionService.handle_webhook_event(db=db, event=event)
        return None
    except Exception as exc:  # pragma: no cover - assertion reports exception details.
        return exc
    finally:
        db.close()


@pytest.mark.mysql
@pytest.mark.integration
def test_mysql_webhook_duplicate_delivery_same_event_id_is_single_effect(
    db,
    session_factory,
    user_factory,
    plan_factory,
):
    advisor = user_factory(
        role="advisor",
        password="AdvisorMysqlDup123!",
        email="advisor.mysql.duplicate@example.com",
        name="MySQL Duplicate Advisor",
    )
    plan = plan_factory(
        stripe_price_id="price_mysql_duplicate",
        daily_download_limit=3,
    )
    event = _build_checkout_event(
        event_id="evt_mysql_same_event",
        session_id="cs_mysql_same_event",
        payment_intent_id="pi_mysql_same_event",
        user_id=advisor.id,
        package_id=plan.id,
        amount_cents=plan.price_cents,
    )
    start_barrier = Barrier(2)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(_run_webhook_in_thread, session_factory, event, start_barrier)
            for _ in range(2)
        ]
    results = [future.result(timeout=30) for future in futures]
    failures = [result for result in results if result is not None]
    assert failures == []

    assert (
        db.query(ProcessedStripeEvent)
        .filter(ProcessedStripeEvent.stripe_event_id == "evt_mysql_same_event")
        .count()
        == 1
    )
    purchases = (
        db.query(LeadPurchase)
        .filter(LeadPurchase.stripe_checkout_session_id == "cs_mysql_same_event")
        .all()
    )
    assert len(purchases) == 1
    purchase = purchases[0]
    assert purchase.status == "completed"
    assert (
        db.query(LeadCreditLedger)
        .filter(
            LeadCreditLedger.purchase_id == purchase.id,
            LeadCreditLedger.movement_type == "purchase_grant",
        )
        .count()
        == 1
    )


@pytest.mark.mysql
@pytest.mark.integration
def test_mysql_webhook_replay_mutation_concurrency_preserves_completed_state(
    db,
    session_factory,
    user_factory,
    plan_factory,
    purchase_factory,
):
    advisor = user_factory(
        role="advisor",
        password="AdvisorMysqlReplay123!",
        email="advisor.mysql.replay@example.com",
        name="MySQL Replay Advisor",
    )
    plan = plan_factory(
        stripe_price_id="price_mysql_replay",
        daily_download_limit=12,
    )
    purchase = purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        credits_total=12,
        credits_remaining=5,
        status="completed",
        stripe_checkout_session_id="cs_mysql_replay",
        stripe_payment_intent_id="pi_mysql_replay",
    )
    db.add(
        LeadCreditLedger(
            user_id=advisor.id,
            purchase_id=purchase.id,
            movement_type="purchase_grant",
            credits_delta=12,
            note="Seeded grant for mysql replay concurrency test",
            idempotency_key=f"purchase_grant:{purchase.id}",
        )
    )
    db.commit()

    checkout_replay = _build_checkout_event(
        event_id="evt_mysql_replay_checkout",
        session_id="cs_mysql_replay",
        payment_intent_id="pi_mysql_replay",
        user_id=advisor.id,
        package_id=plan.id,
        amount_cents=plan.price_cents,
    )
    payment_intent_replay = {
        "id": "evt_mysql_replay_pi",
        "type": "payment_intent.succeeded",
        "data": {"object": {"id": "pi_mysql_replay"}},
    }
    start_barrier = Barrier(2)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(_run_webhook_in_thread, session_factory, checkout_replay, start_barrier),
            executor.submit(_run_webhook_in_thread, session_factory, payment_intent_replay, start_barrier),
        ]
    results = [future.result(timeout=30) for future in futures]
    failures = [result for result in results if result is not None]
    assert failures == []

    assert (
        db.query(ProcessedStripeEvent)
        .filter(
            ProcessedStripeEvent.stripe_event_id.in_(
                ["evt_mysql_replay_checkout", "evt_mysql_replay_pi"]
            )
        )
        .count()
        == 2
    )
    refreshed = (
        db.query(LeadPurchase)
        .filter(LeadPurchase.id == purchase.id)
        .first()
    )
    assert refreshed is not None
    assert refreshed.status == "completed"
    assert refreshed.credits_remaining == 5
    assert (
        db.query(LeadCreditLedger)
        .filter(
            LeadCreditLedger.purchase_id == purchase.id,
            LeadCreditLedger.movement_type == "purchase_grant",
        )
        .count()
        == 1
    )
