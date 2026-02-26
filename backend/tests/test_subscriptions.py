from datetime import datetime, timezone
import time

import pytest
import stripe

from app.core.config import settings
from app.models.audit_log import AuditLog
from app.models.lead import LeadOwnership
from app.models.purchase import LeadCreditLedger, LeadPurchase, ProcessedStripeEvent, StripePoisonEvent
from app.services.subscription_service import StripeWebhookProcessingError


def _create_advisor_with_verified_license(user_factory, license_factory, auth_headers):
    advisor = user_factory(
        role="advisor",
        password="AdvisorSub123!",
        email="advisor.subscriptions@example.com",
        name="Advisor Sub",
    )
    license_factory(
        user_id=advisor.id,
        state="CA",
        status="verified",
        license_number="CA-SUB-001",
    )
    headers = auth_headers(advisor.email, "AdvisorSub123!")
    return advisor, headers


def _build_purchase_webhook_event(
    *,
    event_id: str,
    event_type: str,
    session_id: str,
    payment_intent_id: str,
    user_id: int,
    package_id: int,
    amount_cents: int,
    payment_status: str = "paid",
    snapshot_amount_cents: int | None = None,
    snapshot_currency: str | None = None,
    snapshot_credits_total: int | None = None,
    invoice_id: str | None = None,
):
    metadata = {"user_id": str(user_id), "package_id": str(package_id)}
    if snapshot_amount_cents is not None:
        metadata["purchase_amount_cents"] = str(snapshot_amount_cents)
    if snapshot_currency is not None:
        metadata["purchase_currency"] = str(snapshot_currency).upper()
    if snapshot_credits_total is not None:
        metadata["purchase_credits_total"] = str(snapshot_credits_total)
    return {
        "id": event_id,
        "type": event_type,
        "data": {
            "object": {
                "id": session_id,
                "mode": "payment",
                "payment_status": payment_status,
                "payment_intent": payment_intent_id,
                "invoice": invoice_id,
                "amount_total": amount_cents,
                "currency": "usd",
                "created": int(datetime.now(timezone.utc).timestamp()),
                "metadata": metadata,
            }
        },
    }


@pytest.mark.integration
def test_get_plans_sorted_by_price(client, plan_factory):
    plan_factory(name="Premium", price_cents=120000, stripe_price_id="price_premium")
    plan_factory(name="Basic", price_cents=40000, stripe_price_id="price_basic")

    response = client.get("/api/v1/purchases/packages")
    assert response.status_code == 200, response.text
    plans = response.json()
    assert len(plans) == 2
    assert plans[0]["price_cents"] <= plans[1]["price_cents"]


@pytest.mark.integration
def test_checkout_requires_verified_license(
    client,
    user_factory,
    plan_factory,
    auth_headers,
    monkeypatch,
):
    advisor = user_factory(
        role="advisor",
        password="AdvisorNoLic123!",
        email="advisor.no.license@example.com",
        name="Advisor No License",
    )
    headers = auth_headers(advisor.email, "AdvisorNoLic123!")
    plan = plan_factory(stripe_price_id="price_checkout_require_license")

    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.create_or_get_stripe_customer",
        lambda db, user: "cus_no_license",
    )

    response = client.post(
        "/api/v1/purchases/checkout",
        headers=headers,
        json={"package_id": plan.id},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "At least one verified license is required"


@pytest.mark.integration
def test_checkout_success_returns_session(
    client,
    db,
    user_factory,
    license_factory,
    plan_factory,
    auth_headers,
    monkeypatch,
):
    advisor, headers = _create_advisor_with_verified_license(
        user_factory,
        license_factory,
        auth_headers,
    )
    _ = advisor
    plan = plan_factory(stripe_price_id="price_checkout_success")

    captured_checkout_kwargs = {}

    def _mock_checkout_create(**kwargs):
        captured_checkout_kwargs.update(kwargs)
        return {
            "id": "cs_test_checkout",
            "invoice": "in_test_checkout",
            "url": "https://checkout.stripe.test/session",
        }

    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.create_or_get_stripe_customer",
        lambda db, user: "cus_checkout_success",
    )
    monkeypatch.setattr(
        "app.services.subscription_service.stripe.checkout.Session.create",
        _mock_checkout_create,
    )

    response = client.post(
        "/api/v1/purchases/checkout",
        headers=headers,
        json={"package_id": plan.id},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["session_id"] == "cs_test_checkout"
    assert body["url"].startswith("https://checkout.stripe.test/")
    assert captured_checkout_kwargs["success_url"].endswith(
        "/subscription?checkout=success&session_id={CHECKOUT_SESSION_ID}"
    )
    assert captured_checkout_kwargs["cancel_url"].endswith(
        "/subscription?checkout=cancel"
    )
    assert "/advisor/subscription/" not in captured_checkout_kwargs["success_url"]
    assert "/advisor/subscription/" not in captured_checkout_kwargs["cancel_url"]
    assert captured_checkout_kwargs["mode"] == "payment"
    assert captured_checkout_kwargs["automatic_tax"] == {"enabled": False}
    expected_expiration_seconds = int(settings.STRIPE_CHECKOUT_SESSION_EXPIRES_MINUTES) * 60
    expires_at = int(captured_checkout_kwargs["expires_at"])
    now_ts = int(time.time())
    assert expires_at >= now_ts + expected_expiration_seconds - 10
    assert expires_at <= now_ts + expected_expiration_seconds + 10
    checkout_metadata = captured_checkout_kwargs["metadata"]
    assert checkout_metadata["user_id"] == str(advisor.id)
    assert checkout_metadata["package_id"] == str(plan.id)
    assert checkout_metadata["purchase_amount_cents"] == str(int(plan.price_cents or 0))
    assert checkout_metadata["purchase_currency"] == str((plan.currency or "USD")).upper()
    assert checkout_metadata["purchase_credits_total"] == str(int(plan.daily_download_limit or 0))
    assert captured_checkout_kwargs["payment_intent_data"]["metadata"] == checkout_metadata
    assert captured_checkout_kwargs["invoice_creation"]["enabled"] is True
    assert captured_checkout_kwargs["invoice_creation"]["invoice_data"]["metadata"] == checkout_metadata

    pending_purchase = (
        db.query(LeadPurchase)
        .filter(LeadPurchase.stripe_checkout_session_id == "cs_test_checkout")
        .first()
    )
    assert pending_purchase is not None
    assert pending_purchase.status == "pending"
    assert pending_purchase.user_id == advisor.id
    assert pending_purchase.package_id == plan.id
    assert pending_purchase.amount_cents == int(plan.price_cents or 0)
    assert pending_purchase.currency == str((plan.currency or "USD")).upper()
    assert pending_purchase.credits_total == int(plan.daily_download_limit or 0)
    assert pending_purchase.credits_remaining == 0
    assert pending_purchase.stripe_invoice_id == "in_test_checkout"


@pytest.mark.integration
def test_checkout_success_emits_metric_and_purchase_initiated_audit(
    client,
    db,
    user_factory,
    license_factory,
    plan_factory,
    auth_headers,
    monkeypatch,
):
    advisor, headers = _create_advisor_with_verified_license(
        user_factory,
        license_factory,
        auth_headers,
    )
    plan = plan_factory(stripe_price_id="price_checkout_metrics")
    metric_calls = []

    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.create_or_get_stripe_customer",
        lambda db, user: "cus_checkout_metrics",
    )
    monkeypatch.setattr(
        "app.services.subscription_service.stripe.checkout.Session.create",
        lambda **kwargs: {
            "id": "cs_checkout_metrics",
            "url": "https://checkout.stripe.test/metrics",
        },
    )
    monkeypatch.setattr(
        "app.services.subscription_service.MetricsService.increment",
        lambda name, value=1, tags=None: metric_calls.append((name, value, tags or {})),
    )

    response = client.post(
        "/api/v1/purchases/checkout",
        headers=headers,
        json={"package_id": plan.id},
    )
    assert response.status_code == 200, response.text
    assert any(name == "purchase_checkout_created_total" for name, _, _ in metric_calls)

    audit_event = (
        db.query(AuditLog)
        .filter(
            AuditLog.actor_user_id == advisor.id,
            AuditLog.action == "purchase_initiated",
            AuditLog.entity_type == "LeadPurchase",
        )
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert audit_event is not None
    assert audit_event.entity_id is not None
    assert (audit_event.meta_data or {}).get("package_id") == plan.id
    assert (audit_event.meta_data or {}).get("correlation_ids", {}).get("checkout_session_id") == "cs_checkout_metrics"


@pytest.mark.integration
def test_checkout_failure_emits_metric(
    client,
    user_factory,
    license_factory,
    plan_factory,
    auth_headers,
    monkeypatch,
):
    _advisor, headers = _create_advisor_with_verified_license(
        user_factory,
        license_factory,
        auth_headers,
    )
    plan = plan_factory(stripe_price_id="price_checkout_failure_metrics")
    metric_calls = []

    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.create_or_get_stripe_customer",
        lambda db, user: "cus_checkout_failure_metrics",
    )

    def _raise_checkout_error(**kwargs):
        raise stripe.error.StripeError("checkout down")

    monkeypatch.setattr(
        "app.services.subscription_service.stripe.checkout.Session.create",
        _raise_checkout_error,
    )
    monkeypatch.setattr(
        "app.services.subscription_service.MetricsService.increment",
        lambda name, value=1, tags=None: metric_calls.append((name, value, tags or {})),
    )

    response = client.post(
        "/api/v1/purchases/checkout",
        headers=headers,
        json={"package_id": plan.id},
    )
    assert response.status_code == 502
    assert any(name == "purchase_checkout_failed_total" for name, _, _ in metric_calls)


@pytest.mark.integration
def test_webhook_checkout_completed_creates_purchase_and_credit_grant(
    client,
    db,
    user_factory,
    license_factory,
    plan_factory,
    lead_factory,
    monkeypatch,
):
    advisor = user_factory(
        role="advisor",
        password="AdvisorWebhook123!",
        email="advisor.webhook@example.com",
        name="Webhook Advisor",
    )
    license_factory(user_id=advisor.id, state="CA", status="verified")
    plan = plan_factory(
        stripe_price_id="price_webhook_plan",
        state_limit=1,
        daily_download_limit=2,
    )
    ca_one = lead_factory(state_code="CA", mobile_phone="555-WEBHOOK-OWN-0001")
    ca_two = lead_factory(state_code="CA", mobile_phone="555-WEBHOOK-OWN-0002")
    lead_factory(state_code="TX", mobile_phone="555-WEBHOOK-OWN-0003")

    event = {
        "id": "evt_checkout_complete",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_evt_1",
                "mode": "payment",
                "payment_status": "paid",
                "payment_intent": "pi_evt_1",
                "invoice": "in_evt_1",
                "amount_total": plan.price_cents,
                "currency": "usd",
                "created": int(datetime.now(timezone.utc).timestamp()),
                "metadata": {"user_id": str(advisor.id), "package_id": str(plan.id)},
            }
        },
    }

    monkeypatch.setattr(
        "app.api.v1.webhooks.stripe.Webhook.construct_event",
        lambda payload, sig_header, secret: event,
    )

    response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ok"
    purchase = (
        db.query(LeadPurchase)
        .filter(LeadPurchase.stripe_checkout_session_id == "cs_evt_1")
        .first()
    )
    assert purchase is not None
    assert purchase.user_id == advisor.id
    assert purchase.package_id == plan.id
    assert purchase.status == "completed"
    assert purchase.credits_total == plan.daily_download_limit
    assert purchase.credits_remaining == 0
    assert purchase.stripe_invoice_id == "in_evt_1"

    ledger_entry = (
        db.query(LeadCreditLedger)
        .filter(
            LeadCreditLedger.purchase_id == purchase.id,
            LeadCreditLedger.movement_type == "purchase_grant",
        )
        .first()
    )
    assert ledger_entry is not None
    assert ledger_entry.credits_delta == plan.daily_download_limit
    ownership_rows = (
        db.query(LeadOwnership)
        .filter(LeadOwnership.purchase_id == purchase.id, LeadOwnership.user_id == advisor.id)
        .all()
    )
    assert len(ownership_rows) == 2
    assert {row.lead_id for row in ownership_rows} == {ca_one.id, ca_two.id}


@pytest.mark.integration
def test_webhook_checkout_completed_uses_pending_purchase_snapshot_when_package_mutates(
    client,
    db,
    user_factory,
    license_factory,
    plan_factory,
    auth_headers,
    monkeypatch,
):
    advisor, headers = _create_advisor_with_verified_license(
        user_factory,
        license_factory,
        auth_headers,
    )
    plan = plan_factory(
        stripe_price_id="price_webhook_snapshot_pending",
        price_cents=5000,
        daily_download_limit=3,
    )
    captured_checkout_kwargs = {}

    def _mock_checkout_create(**kwargs):
        captured_checkout_kwargs.update(kwargs)
        return {
            "id": "cs_snapshot_pending",
            "url": "https://checkout.stripe.test/snapshot-pending",
            "payment_intent": "pi_snapshot_pending",
        }

    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.create_or_get_stripe_customer",
        lambda db, user: "cus_snapshot_pending",
    )
    monkeypatch.setattr(
        "app.services.subscription_service.stripe.checkout.Session.create",
        _mock_checkout_create,
    )

    checkout_response = client.post(
        "/api/v1/purchases/checkout",
        headers=headers,
        json={"package_id": plan.id},
    )
    assert checkout_response.status_code == 200, checkout_response.text

    purchase = (
        db.query(LeadPurchase)
        .filter(LeadPurchase.stripe_checkout_session_id == "cs_snapshot_pending")
        .first()
    )
    assert purchase is not None
    assert purchase.status == "pending"
    original_amount = int(purchase.amount_cents)
    original_currency = str(purchase.currency)
    original_credits = int(purchase.credits_total)

    plan.price_cents = 9900
    plan.currency = "EUR"
    plan.daily_download_limit = 77
    plan.features = {"credits_total": 77}
    db.add(plan)
    db.commit()

    event = _build_purchase_webhook_event(
        event_id="evt_snapshot_pending",
        event_type="checkout.session.completed",
        session_id="cs_snapshot_pending",
        payment_intent_id="pi_snapshot_pending",
        user_id=advisor.id,
        package_id=plan.id,
        amount_cents=9999,
        snapshot_amount_cents=original_amount,
        snapshot_currency=original_currency,
        snapshot_credits_total=original_credits,
    )
    monkeypatch.setattr(
        "app.api.v1.webhooks.stripe.Webhook.construct_event",
        lambda payload, sig_header, secret: event,
    )

    response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert response.status_code == 200, response.text

    db.refresh(purchase)
    assert purchase.status == "completed"
    assert purchase.amount_cents == original_amount
    assert purchase.currency == original_currency
    assert purchase.credits_total == original_credits
    assert purchase.credits_remaining == original_credits

    grant_entry = (
        db.query(LeadCreditLedger)
        .filter(
            LeadCreditLedger.purchase_id == purchase.id,
            LeadCreditLedger.movement_type == "purchase_grant",
        )
        .first()
    )
    assert grant_entry is not None
    assert grant_entry.credits_delta == original_credits


@pytest.mark.integration
def test_webhook_checkout_completed_uses_metadata_snapshot_when_pending_row_missing(
    client,
    db,
    user_factory,
    license_factory,
    plan_factory,
    auth_headers,
    monkeypatch,
):
    advisor, _headers = _create_advisor_with_verified_license(
        user_factory,
        license_factory,
        auth_headers,
    )
    plan = plan_factory(
        stripe_price_id="price_webhook_snapshot_metadata",
        price_cents=4200,
        daily_download_limit=4,
    )

    original_amount = int(plan.price_cents or 0)
    original_currency = str((plan.currency or "USD")).upper()
    original_credits = int(plan.daily_download_limit or 0)

    plan.price_cents = 8400
    plan.currency = "CAD"
    plan.daily_download_limit = 40
    plan.features = {"credits_total": 40}
    db.add(plan)
    db.commit()

    event = _build_purchase_webhook_event(
        event_id="evt_snapshot_metadata",
        event_type="checkout.session.completed",
        session_id="cs_snapshot_metadata",
        payment_intent_id="pi_snapshot_metadata",
        user_id=advisor.id,
        package_id=plan.id,
        amount_cents=9999,
        snapshot_amount_cents=original_amount,
        snapshot_currency=original_currency,
        snapshot_credits_total=original_credits,
    )
    monkeypatch.setattr(
        "app.api.v1.webhooks.stripe.Webhook.construct_event",
        lambda payload, sig_header, secret: event,
    )

    response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert response.status_code == 200, response.text

    purchase = (
        db.query(LeadPurchase)
        .filter(LeadPurchase.stripe_checkout_session_id == "cs_snapshot_metadata")
        .first()
    )
    assert purchase is not None
    assert purchase.status == "completed"
    assert purchase.amount_cents == original_amount
    assert purchase.currency == original_currency
    assert purchase.credits_total == original_credits
    assert purchase.credits_remaining == original_credits


@pytest.mark.integration
def test_webhook_checkout_completed_assigns_leads_visible_in_advisor_inbox(
    client,
    db,
    user_factory,
    license_factory,
    plan_factory,
    lead_factory,
    auth_headers,
    monkeypatch,
):
    advisor = user_factory(
        role="advisor",
        password="AdvisorWebhookInbox123!",
        email="advisor.webhook.inbox@example.com",
        name="Webhook Inbox Advisor",
    )
    headers = auth_headers(advisor.email, "AdvisorWebhookInbox123!")
    license_factory(user_id=advisor.id, state="CA", status="verified")
    plan = plan_factory(
        stripe_price_id="price_webhook_inbox",
        state_limit=1,
        daily_download_limit=1,
    )
    owned_lead = lead_factory(state_code="CA", mobile_phone="555-888-1001")

    event = _build_purchase_webhook_event(
        event_id="evt_checkout_inbox",
        event_type="checkout.session.completed",
        session_id="cs_inbox",
        payment_intent_id="pi_inbox",
        user_id=advisor.id,
        package_id=plan.id,
        amount_cents=plan.price_cents,
    )

    monkeypatch.setattr(
        "app.api.v1.webhooks.stripe.Webhook.construct_event",
        lambda payload, sig_header, secret: event,
    )

    webhook_response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert webhook_response.status_code == 200, webhook_response.text

    inbox_response = client.get("/api/v1/leads/?delivery_status=all", headers=headers)
    assert inbox_response.status_code == 200, inbox_response.text
    payload = inbox_response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == owned_lead.id
    assert payload["items"][0]["is_downloaded"] is False


@pytest.mark.integration
def test_webhook_checkout_completed_emits_metrics_and_purchase_audit_events(
    client,
    db,
    user_factory,
    plan_factory,
    monkeypatch,
):
    advisor = user_factory(
        role="advisor",
        password="AdvisorWebhookMetrics123!",
        email="advisor.webhook.metrics@example.com",
        name="Webhook Metrics Advisor",
    )
    plan = plan_factory(stripe_price_id="price_webhook_metrics")
    event = _build_purchase_webhook_event(
        event_id="evt_webhook_metrics",
        event_type="checkout.session.completed",
        session_id="cs_webhook_metrics",
        payment_intent_id="pi_webhook_metrics",
        user_id=advisor.id,
        package_id=plan.id,
        amount_cents=plan.price_cents,
    )
    metric_counters = []
    metric_histograms = []

    monkeypatch.setattr(
        "app.api.v1.webhooks.stripe.Webhook.construct_event",
        lambda payload, sig_header, secret: event,
    )
    monkeypatch.setattr(
        "app.api.v1.webhooks.MetricsService.increment",
        lambda name, value=1, tags=None: metric_counters.append((name, value, tags or {})),
    )
    monkeypatch.setattr(
        "app.api.v1.webhooks.MetricsService.histogram",
        lambda name, value, tags=None: metric_histograms.append((name, value, tags or {})),
    )
    monkeypatch.setattr(
        "app.services.subscription_service.MetricsService.histogram",
        lambda name, value, tags=None: metric_histograms.append((name, value, tags or {})),
    )

    response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert response.status_code == 200, response.text
    assert any(name == "purchase_webhook_processed_total" for name, _, _ in metric_counters)
    assert any(name == "purchase_webhook_processing_latency_ms" for name, _, _ in metric_histograms)
    assert any(name == "credit_grant_latency_ms" for name, _, _ in metric_histograms)

    purchase = (
        db.query(LeadPurchase)
        .filter(LeadPurchase.stripe_checkout_session_id == "cs_webhook_metrics")
        .first()
    )
    assert purchase is not None

    confirmed_audit = (
        db.query(AuditLog)
        .filter(
            AuditLog.action == "purchase_confirmed",
            AuditLog.entity_id == purchase.id,
        )
        .first()
    )
    assert confirmed_audit is not None
    confirmed_meta = confirmed_audit.meta_data or {}
    assert confirmed_meta.get("correlation_ids", {}).get("stripe_event_id") == "evt_webhook_metrics"

    granted_audit = (
        db.query(AuditLog)
        .filter(
            AuditLog.action == "purchase_credits_granted",
            AuditLog.entity_id == purchase.id,
        )
        .first()
    )
    assert granted_audit is not None
    granted_meta = granted_audit.meta_data or {}
    assert granted_meta.get("credits_delta") == plan.daily_download_limit


@pytest.mark.integration
def test_webhook_fast_ack_enqueues_without_running_sync_processing(
    client,
    monkeypatch,
):
    event = {
        "id": "evt_fast_ack_enqueue",
        "type": "checkout.session.completed",
        "data": {"object": {"id": "cs_fast_ack"}},
    }
    seen = {}

    monkeypatch.setattr("app.api.v1.webhooks.settings.STRIPE_WEBHOOK_FAST_ACK_ENABLED", True)
    monkeypatch.setattr(
        "app.api.v1.webhooks.stripe.Webhook.construct_event",
        lambda payload, sig_header, secret: event,
    )
    monkeypatch.setattr(
        "app.api.v1.webhooks.StripeWebhookInboxService.enqueue_event_threadsafe",
        lambda event: seen.setdefault("event_id", event["id"]) is not None,
    )
    monkeypatch.setattr(
        "app.api.v1.webhooks.SubscriptionService.handle_webhook_event_threadsafe",
        lambda event: (_ for _ in ()).throw(AssertionError("sync processing should not run")),
    )

    response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert response.status_code == 200, response.text
    assert seen.get("event_id") == "evt_fast_ack_enqueue"


@pytest.mark.integration
def test_webhook_livemode_mismatch_is_ignored_before_processing(
    client,
    monkeypatch,
):
    event = {
        "id": "evt_live_mode_mismatch",
        "type": "checkout.session.completed",
        "livemode": True,
        "data": {"object": {"id": "cs_live_mode_mismatch"}},
    }
    metric_counters = []

    monkeypatch.setattr("app.api.v1.webhooks.settings.STRIPE_WEBHOOK_EXPECT_LIVEMODE", False)
    monkeypatch.setattr(
        "app.api.v1.webhooks.stripe.Webhook.construct_event",
        lambda payload, sig_header, secret: event,
    )
    monkeypatch.setattr(
        "app.api.v1.webhooks.StripeWebhookInboxService.enqueue_event_threadsafe",
        lambda event: (_ for _ in ()).throw(AssertionError("mismatched event should not enqueue")),
    )
    monkeypatch.setattr(
        "app.api.v1.webhooks.SubscriptionService.handle_webhook_event_threadsafe",
        lambda event: (_ for _ in ()).throw(AssertionError("mismatched event should not process")),
    )
    monkeypatch.setattr(
        "app.services.subscription_service.MetricsService.increment",
        lambda name, value=1, tags=None: metric_counters.append((name, value, tags or {})),
    )

    response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "ignored"}
    assert any(
        name == "purchase_webhook_ignored_total" and tags.get("reason") == "livemode_mismatch"
        for name, _, tags in metric_counters
    )


@pytest.mark.integration
def test_webhook_rejects_missing_signature_header(client):
    response = client.post(
        "/api/v1/webhooks/stripe",
        json={"mock": "payload"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Missing Stripe signature"


@pytest.mark.integration
def test_webhook_rejects_invalid_payload(client, monkeypatch):
    monkeypatch.setattr(
        "app.api.v1.webhooks.stripe.Webhook.construct_event",
        lambda payload, sig_header, secret: (_ for _ in ()).throw(ValueError("invalid payload")),
    )

    response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid payload"


@pytest.mark.integration
def test_webhook_rejects_invalid_signature(client, monkeypatch):
    monkeypatch.setattr(
        "app.api.v1.webhooks.stripe.Webhook.construct_event",
        lambda payload, sig_header, secret: (_ for _ in ()).throw(
            stripe.error.SignatureVerificationError("invalid signature")
        ),
    )

    response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid signature"


@pytest.mark.integration
def test_webhook_fast_ack_returns_500_when_enqueue_fails(
    client,
    monkeypatch,
):
    event = {
        "id": "evt_fast_ack_failure",
        "type": "checkout.session.completed",
        "data": {"object": {"id": "cs_fast_ack_failure"}},
    }

    monkeypatch.setattr("app.api.v1.webhooks.settings.STRIPE_WEBHOOK_FAST_ACK_ENABLED", True)
    monkeypatch.setattr(
        "app.api.v1.webhooks.stripe.Webhook.construct_event",
        lambda payload, sig_header, secret: event,
    )
    monkeypatch.setattr(
        "app.api.v1.webhooks.StripeWebhookInboxService.enqueue_event_threadsafe",
        lambda event: (_ for _ in ()).throw(StripeWebhookProcessingError("inbox down")),
    )

    response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert response.status_code == 500


@pytest.mark.integration
def test_webhook_retry_metric_emitted_on_retryable_processing_error(
    client,
    monkeypatch,
):
    event = {
        "id": "evt_retry_metric",
        "type": "checkout.session.completed",
        "data": {"object": {"id": "cs_retry_metric"}},
    }
    metric_counters = []

    monkeypatch.setattr(
        "app.api.v1.webhooks.stripe.Webhook.construct_event",
        lambda payload, sig_header, secret: event,
    )
    monkeypatch.setattr(
        "app.api.v1.webhooks.SubscriptionService.handle_webhook_event_threadsafe",
        lambda event: (_ for _ in ()).throw(StripeWebhookProcessingError("retryable")),
    )
    monkeypatch.setattr(
        "app.api.v1.webhooks.MetricsService.increment",
        lambda name, value=1, tags=None: metric_counters.append((name, value, tags or {})),
    )

    response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert response.status_code == 500
    assert any(name == "purchase_webhook_retry_total" for name, _, _ in metric_counters)


@pytest.mark.integration
def test_webhook_failure_metric_emitted_on_unexpected_processing_error(
    client,
    monkeypatch,
):
    event = {
        "id": "evt_fail_metric",
        "type": "checkout.session.completed",
        "data": {"object": {"id": "cs_fail_metric"}},
    }
    metric_counters = []

    monkeypatch.setattr(
        "app.api.v1.webhooks.stripe.Webhook.construct_event",
        lambda payload, sig_header, secret: event,
    )
    monkeypatch.setattr(
        "app.api.v1.webhooks.SubscriptionService.handle_webhook_event_threadsafe",
        lambda event: (_ for _ in ()).throw(RuntimeError("unexpected")),
    )
    monkeypatch.setattr(
        "app.api.v1.webhooks.MetricsService.increment",
        lambda name, value=1, tags=None: metric_counters.append((name, value, tags or {})),
    )

    response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert response.status_code == 500
    assert any(name == "purchase_webhook_failed_total" for name, _, _ in metric_counters)


@pytest.mark.integration
def test_webhook_duplicate_delivery_same_event_id_grants_credit_once(
    client,
    db,
    user_factory,
    license_factory,
    plan_factory,
    lead_factory,
    monkeypatch,
):
    advisor = user_factory(
        role="advisor",
        password="AdvisorWebhookSameEvent123!",
        email="advisor.webhook.same.event@example.com",
        name="Webhook Same Event Advisor",
    )
    license_factory(user_id=advisor.id, state="CA", status="verified")
    plan = plan_factory(
        stripe_price_id="price_webhook_same_event",
        state_limit=1,
        daily_download_limit=1,
    )
    first_candidate = lead_factory(state_code="CA", mobile_phone="555-WEBHOOK-DUP-0001")
    second_candidate = lead_factory(state_code="CA", mobile_phone="555-WEBHOOK-DUP-0002")
    event = _build_purchase_webhook_event(
        event_id="evt_same_event_replayed",
        event_type="checkout.session.completed",
        session_id="cs_same_event",
        payment_intent_id="pi_same_event",
        user_id=advisor.id,
        package_id=plan.id,
        amount_cents=plan.price_cents,
    )

    monkeypatch.setattr(
        "app.api.v1.webhooks.stripe.Webhook.construct_event",
        lambda payload, sig_header, secret: event,
    )

    first_response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert first_response.status_code == 200, first_response.text

    second_response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert second_response.status_code == 200, second_response.text
    assert (
        db.query(ProcessedStripeEvent)
        .filter(ProcessedStripeEvent.stripe_event_id == "evt_same_event_replayed")
        .count()
        == 1
    )

    purchases = (
        db.query(LeadPurchase)
        .filter(LeadPurchase.stripe_checkout_session_id == "cs_same_event")
        .all()
    )
    assert len(purchases) == 1
    purchase = purchases[0]
    assert purchase.status == "completed"
    assert purchase.credits_remaining == 0
    grant_rows = (
        db.query(LeadCreditLedger)
        .filter(
            LeadCreditLedger.purchase_id == purchase.id,
            LeadCreditLedger.movement_type == "purchase_grant",
        )
    )
    assert grant_rows.count() == 1
    grant = grant_rows.first()
    assert grant is not None
    assert grant.idempotency_key == f"purchase_grant:{purchase.id}"
    ownership_rows = (
        db.query(LeadOwnership)
        .filter(LeadOwnership.purchase_id == purchase.id, LeadOwnership.user_id == advisor.id)
        .all()
    )
    assert len(ownership_rows) == 1
    assert ownership_rows[0].lead_id in {first_candidate.id, second_candidate.id}


@pytest.mark.integration
def test_webhook_different_event_ids_same_payment_intent_grants_credit_once(
    client,
    db,
    user_factory,
    plan_factory,
    monkeypatch,
):
    advisor = user_factory(
        role="advisor",
        password="AdvisorWebhookSemanticDup123!",
        email="advisor.webhook.semantic.dup@example.com",
        name="Webhook Semantic Dup Advisor",
    )
    plan = plan_factory(stripe_price_id="price_webhook_semantic_dup")
    first_event = _build_purchase_webhook_event(
        event_id="evt_semantic_dup_1",
        event_type="checkout.session.completed",
        session_id="cs_semantic_dup_1",
        payment_intent_id="pi_semantic_dup_shared",
        user_id=advisor.id,
        package_id=plan.id,
        amount_cents=plan.price_cents,
    )
    second_event = _build_purchase_webhook_event(
        event_id="evt_semantic_dup_2",
        event_type="checkout.session.completed",
        session_id="cs_semantic_dup_2",
        payment_intent_id="pi_semantic_dup_shared",
        user_id=advisor.id,
        package_id=plan.id,
        amount_cents=plan.price_cents,
    )

    event_holder = {"value": first_event}
    monkeypatch.setattr(
        "app.api.v1.webhooks.stripe.Webhook.construct_event",
        lambda payload, sig_header, secret: event_holder["value"],
    )

    first_response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert first_response.status_code == 200, first_response.text

    event_holder["value"] = second_event
    second_response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert second_response.status_code == 200, second_response.text
    assert (
        db.query(ProcessedStripeEvent)
        .filter(ProcessedStripeEvent.stripe_event_id.in_(["evt_semantic_dup_1", "evt_semantic_dup_2"]))
        .count()
        == 2
    )

    purchases = (
        db.query(LeadPurchase)
        .filter(LeadPurchase.stripe_payment_intent_id == "pi_semantic_dup_shared")
        .all()
    )
    assert len(purchases) == 1
    purchase = purchases[0]
    assert purchase.stripe_checkout_session_id == "cs_semantic_dup_1"
    assert purchase.status == "completed"
    grant_rows = (
        db.query(LeadCreditLedger)
        .filter(
            LeadCreditLedger.purchase_id == purchase.id,
            LeadCreditLedger.movement_type == "purchase_grant",
        )
    )
    assert grant_rows.count() == 1
    grant = grant_rows.first()
    assert grant is not None
    assert grant.idempotency_key == f"purchase_grant:{purchase.id}"


@pytest.mark.integration
def test_webhook_out_of_order_and_retry_events_grant_credit_once(
    client,
    db,
    user_factory,
    plan_factory,
    monkeypatch,
):
    advisor = user_factory(
        role="advisor",
        password="AdvisorWebhookOutOfOrder123!",
        email="advisor.webhook.out.of.order@example.com",
        name="Webhook Out Of Order Advisor",
    )
    plan = plan_factory(stripe_price_id="price_webhook_out_of_order")

    failed_event = _build_purchase_webhook_event(
        event_id="evt_out_of_order_failed_first",
        event_type="checkout.session.async_payment_failed",
        session_id="cs_out_of_order",
        payment_intent_id="pi_out_of_order",
        user_id=advisor.id,
        package_id=plan.id,
        amount_cents=plan.price_cents,
        payment_status="unpaid",
    )
    completed_event = _build_purchase_webhook_event(
        event_id="evt_out_of_order_completed_second",
        event_type="checkout.session.completed",
        session_id="cs_out_of_order",
        payment_intent_id="pi_out_of_order",
        user_id=advisor.id,
        package_id=plan.id,
        amount_cents=plan.price_cents,
    )
    retry_failed_event = _build_purchase_webhook_event(
        event_id="evt_out_of_order_failed_retry",
        event_type="checkout.session.async_payment_failed",
        session_id="cs_out_of_order",
        payment_intent_id="pi_out_of_order",
        user_id=advisor.id,
        package_id=plan.id,
        amount_cents=plan.price_cents,
        payment_status="unpaid",
    )

    event_holder = {"value": failed_event}
    monkeypatch.setattr(
        "app.api.v1.webhooks.stripe.Webhook.construct_event",
        lambda payload, sig_header, secret: event_holder["value"],
    )

    failed_response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert failed_response.status_code == 200, failed_response.text

    event_holder["value"] = completed_event
    completed_response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert completed_response.status_code == 200, completed_response.text

    event_holder["value"] = retry_failed_event
    retry_response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert retry_response.status_code == 200, retry_response.text

    purchase = (
        db.query(LeadPurchase)
        .filter(LeadPurchase.stripe_checkout_session_id == "cs_out_of_order")
        .first()
    )
    assert purchase is not None
    assert purchase.status == "completed"
    assert purchase.credits_remaining == plan.daily_download_limit
    assert (
        db.query(LeadCreditLedger)
        .filter(
            LeadCreditLedger.purchase_id == purchase.id,
            LeadCreditLedger.movement_type == "purchase_grant",
        )
        .count()
        == 1
    )


@pytest.mark.integration
def test_webhook_checkout_session_async_payment_succeeded_creates_purchase_and_credit_grant(
    client,
    db,
    user_factory,
    plan_factory,
    monkeypatch,
):
    advisor = user_factory(
        role="advisor",
        password="AdvisorWebhookAsyncSuccess123!",
        email="advisor.webhook.async.success@example.com",
        name="Webhook Async Success Advisor",
    )
    plan = plan_factory(stripe_price_id="price_webhook_async_success")

    event = _build_purchase_webhook_event(
        event_id="evt_checkout_async_payment_succeeded_1",
        event_type="checkout.session.async_payment_succeeded",
        session_id="cs_async_payment_succeeded_1",
        payment_intent_id="pi_async_payment_succeeded_1",
        user_id=advisor.id,
        package_id=plan.id,
        amount_cents=plan.price_cents,
        payment_status="paid",
    )
    monkeypatch.setattr(
        "app.api.v1.webhooks.stripe.Webhook.construct_event",
        lambda payload, sig_header, secret: event,
    )

    response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "ok"}

    purchase = (
        db.query(LeadPurchase)
        .filter(LeadPurchase.stripe_checkout_session_id == "cs_async_payment_succeeded_1")
        .first()
    )
    assert purchase is not None
    assert purchase.status == "completed"
    assert purchase.stripe_payment_intent_id == "pi_async_payment_succeeded_1"
    assert purchase.credits_remaining == int(plan.daily_download_limit or 0)
    assert (
        db.query(ProcessedStripeEvent)
        .filter(ProcessedStripeEvent.stripe_event_id == "evt_checkout_async_payment_succeeded_1")
        .count()
        == 1
    )


@pytest.mark.integration
def test_webhook_checkout_session_expired_cancels_pending_purchase(
    client,
    db,
    user_factory,
    plan_factory,
    purchase_factory,
    monkeypatch,
):
    advisor = user_factory(
        role="advisor",
        password="AdvisorWebhookExpired123!",
        email="advisor.webhook.expired.pending@example.com",
        name="Webhook Expired Pending Advisor",
    )
    plan = plan_factory(stripe_price_id="price_checkout_expired_pending")
    purchase = purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        credits_total=4,
        credits_remaining=0,
        status="pending",
        stripe_checkout_session_id="cs_checkout_expired_pending_1",
        stripe_payment_intent_id="pi_checkout_expired_pending_1",
    )

    event = _build_purchase_webhook_event(
        event_id="evt_checkout_expired_pending_1",
        event_type="checkout.session.expired",
        session_id="cs_checkout_expired_pending_1",
        payment_intent_id="pi_checkout_expired_pending_1",
        user_id=advisor.id,
        package_id=plan.id,
        amount_cents=plan.price_cents,
        payment_status="unpaid",
    )
    monkeypatch.setattr(
        "app.api.v1.webhooks.stripe.Webhook.construct_event",
        lambda payload, sig_header, secret: event,
    )

    response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "ok"}

    db.refresh(purchase)
    assert purchase.status == "canceled"
    assert purchase.credits_remaining == 0
    assert (
        db.query(LeadCreditLedger)
        .filter(
            LeadCreditLedger.purchase_id == purchase.id,
            LeadCreditLedger.movement_type == "purchase_grant",
        )
        .count()
        == 0
    )


@pytest.mark.integration
def test_webhook_checkout_completed_defers_credit_grant_when_toggle_disabled(
    client,
    db,
    user_factory,
    plan_factory,
    monkeypatch,
):
    advisor = user_factory(
        role="advisor",
        password="AdvisorWebhookDeferred123!",
        email="advisor.webhook.deferred@example.com",
        name="Webhook Deferred Advisor",
    )
    plan = plan_factory(stripe_price_id="price_webhook_deferred")

    first_event = {
        "id": "evt_checkout_deferred_1",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_evt_deferred_1",
                "mode": "payment",
                "payment_status": "paid",
                "payment_intent": "pi_evt_deferred_1",
                "amount_total": plan.price_cents,
                "currency": "usd",
                "created": int(datetime.now(timezone.utc).timestamp()),
                "metadata": {"user_id": str(advisor.id), "package_id": str(plan.id)},
            }
        },
    }

    monkeypatch.setattr("app.services.subscription_service.settings.PURCHASE_WEBHOOK_CREDIT_GRANT_ENABLED", False)
    monkeypatch.setattr(
        "app.api.v1.webhooks.stripe.Webhook.construct_event",
        lambda payload, sig_header, secret: first_event,
    )
    first_response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert first_response.status_code == 200, first_response.text

    deferred_purchase = (
        db.query(LeadPurchase)
        .filter(LeadPurchase.stripe_checkout_session_id == "cs_evt_deferred_1")
        .first()
    )
    assert deferred_purchase is not None
    assert deferred_purchase.status == "pending"
    assert deferred_purchase.credits_remaining == 0

    deferred_ledger = (
        db.query(LeadCreditLedger)
        .filter(
            LeadCreditLedger.purchase_id == deferred_purchase.id,
            LeadCreditLedger.movement_type == "purchase_grant",
        )
        .all()
    )
    assert len(deferred_ledger) == 0

    replay_event = {
        "id": "evt_checkout_deferred_2",
        "type": "checkout.session.completed",
        "data": first_event["data"],
    }
    monkeypatch.setattr("app.services.subscription_service.settings.PURCHASE_WEBHOOK_CREDIT_GRANT_ENABLED", True)
    monkeypatch.setattr(
        "app.api.v1.webhooks.stripe.Webhook.construct_event",
        lambda payload, sig_header, secret: replay_event,
    )
    replay_response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert replay_response.status_code == 200, replay_response.text

    db.expire_all()
    fulfilled_purchase = (
        db.query(LeadPurchase)
        .filter(LeadPurchase.stripe_checkout_session_id == "cs_evt_deferred_1")
        .first()
    )
    assert fulfilled_purchase is not None
    assert fulfilled_purchase.status == "completed"
    assert fulfilled_purchase.credits_remaining == plan.daily_download_limit

    grant_entries = (
        db.query(LeadCreditLedger)
        .filter(
            LeadCreditLedger.purchase_id == fulfilled_purchase.id,
            LeadCreditLedger.movement_type == "purchase_grant",
        )
        .all()
    )
    assert len(grant_entries) == 1
    assert grant_entries[0].credits_delta == plan.daily_download_limit


@pytest.mark.integration
def test_webhook_checkout_and_payment_intent_completion_paths_emit_equivalent_fulfillment_audits(
    client,
    db,
    user_factory,
    license_factory,
    plan_factory,
    lead_factory,
    purchase_factory,
    monkeypatch,
):
    advisor = user_factory(
        role="advisor",
        password="AdvisorWebhookParity123!",
        email="advisor.webhook.parity@example.com",
        name="Webhook Parity Advisor",
    )
    license_factory(user_id=advisor.id, state="CA", status="verified")
    plan = plan_factory(
        stripe_price_id="price_webhook_parity",
        state_limit=1,
        daily_download_limit=1,
    )
    lead_factory(state_code="CA", mobile_phone="555-888-4001")
    lead_factory(state_code="CA", mobile_phone="555-888-4002")

    checkout_event = _build_purchase_webhook_event(
        event_id="evt_checkout_parity",
        event_type="checkout.session.completed",
        session_id="cs_parity_checkout",
        payment_intent_id="pi_parity_checkout",
        user_id=advisor.id,
        package_id=plan.id,
        amount_cents=plan.price_cents,
    )
    monkeypatch.setattr(
        "app.api.v1.webhooks.stripe.Webhook.construct_event",
        lambda payload, sig_header, secret: checkout_event,
    )
    checkout_response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert checkout_response.status_code == 200, checkout_response.text

    pending_pi_purchase = purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        stripe_checkout_session_id="cs_parity_pi",
        stripe_payment_intent_id="pi_parity_succeeded",
        credits_total=plan.daily_download_limit,
        credits_remaining=0,
        status="pending",
    )
    db.commit()

    payment_intent_event = {
        "id": "evt_pi_parity",
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": "pi_parity_succeeded",
            }
        },
    }
    monkeypatch.setattr(
        "app.api.v1.webhooks.stripe.Webhook.construct_event",
        lambda payload, sig_header, secret: payment_intent_event,
    )
    pi_response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert pi_response.status_code == 200, pi_response.text

    checkout_purchase = (
        db.query(LeadPurchase)
        .filter(LeadPurchase.stripe_checkout_session_id == "cs_parity_checkout")
        .first()
    )
    assert checkout_purchase is not None
    pi_purchase = db.query(LeadPurchase).filter(LeadPurchase.id == pending_pi_purchase.id).first()
    assert pi_purchase is not None

    def _audit_meta(purchase_id: int, action: str):
        row = (
            db.query(AuditLog)
            .filter(
                AuditLog.action == action,
                AuditLog.entity_id == purchase_id,
            )
            .first()
        )
        assert row is not None
        return row.meta_data or {}

    checkout_confirmed = _audit_meta(checkout_purchase.id, "purchase_confirmed")
    pi_confirmed = _audit_meta(pi_purchase.id, "purchase_confirmed")
    assert checkout_confirmed.get("correlation_ids", {}).get("stripe_event_id") == "evt_checkout_parity"
    assert pi_confirmed.get("correlation_ids", {}).get("stripe_event_id") == "evt_pi_parity"

    checkout_granted = _audit_meta(checkout_purchase.id, "purchase_credits_granted")
    pi_granted = _audit_meta(pi_purchase.id, "purchase_credits_granted")
    assert checkout_granted.get("credits_delta") == plan.daily_download_limit
    assert pi_granted.get("credits_delta") == plan.daily_download_limit
    assert checkout_granted.get("grant_note") == "Checkout session cs_parity_checkout"
    assert pi_granted.get("grant_note") == "Payment intent pi_parity_succeeded"

    checkout_allocated = _audit_meta(checkout_purchase.id, "purchase_leads_allocated")
    pi_allocated = _audit_meta(pi_purchase.id, "purchase_leads_allocated")
    assert checkout_allocated.get("requested_count") == pi_allocated.get("requested_count")
    assert checkout_allocated.get("assigned_count") == pi_allocated.get("assigned_count")
    assert checkout_allocated.get("unfulfilled_count") == pi_allocated.get("unfulfilled_count")
    assert checkout_allocated.get("notification_enqueued_total") == pi_allocated.get(
        "notification_enqueued_total"
    )
    assert checkout_allocated.get("notification_enqueued_email") == pi_allocated.get(
        "notification_enqueued_email"
    )
    assert checkout_allocated.get("notification_enqueued_sms") == pi_allocated.get(
        "notification_enqueued_sms"
    )
    assert len(checkout_allocated.get("newly_assigned_lead_ids") or []) == int(
        checkout_allocated.get("assigned_count") or 0
    )
    assert len(pi_allocated.get("newly_assigned_lead_ids") or []) == int(
        pi_allocated.get("assigned_count") or 0
    )


@pytest.mark.integration
def test_webhook_payment_intent_succeeded_defers_credit_grant_when_toggle_disabled(
    client,
    db,
    user_factory,
    plan_factory,
    purchase_factory,
    monkeypatch,
):
    advisor = user_factory(
        role="advisor",
        password="AdvisorWebhookPI123!",
        email="advisor.webhook.pi@example.com",
        name="Webhook PI Advisor",
    )
    plan = plan_factory(stripe_price_id="price_webhook_pi_deferred")
    purchase = purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        stripe_checkout_session_id="cs_pi_deferred",
        stripe_payment_intent_id="pi_deferred_toggle",
        credits_total=plan.daily_download_limit,
        credits_remaining=0,
        status="pending",
    )

    deferred_event = {
        "id": "evt_pi_succeeded_deferred",
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": "pi_deferred_toggle",
            }
        },
    }

    monkeypatch.setattr("app.services.subscription_service.settings.PURCHASE_WEBHOOK_CREDIT_GRANT_ENABLED", False)
    monkeypatch.setattr(
        "app.api.v1.webhooks.stripe.Webhook.construct_event",
        lambda payload, sig_header, secret: deferred_event,
    )
    deferred_response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert deferred_response.status_code == 200, deferred_response.text

    db.expire_all()
    deferred_purchase = db.query(LeadPurchase).filter(LeadPurchase.id == purchase.id).first()
    assert deferred_purchase is not None
    assert deferred_purchase.status == "pending"
    assert deferred_purchase.credits_remaining == 0
    assert (
        db.query(LeadCreditLedger)
        .filter(
            LeadCreditLedger.purchase_id == purchase.id,
            LeadCreditLedger.movement_type == "purchase_grant",
        )
        .count()
        == 0
    )

    fulfilled_event = {
        "id": "evt_pi_succeeded_deferred_retry",
        "type": "payment_intent.succeeded",
        "data": deferred_event["data"],
    }
    monkeypatch.setattr("app.services.subscription_service.settings.PURCHASE_WEBHOOK_CREDIT_GRANT_ENABLED", True)
    monkeypatch.setattr(
        "app.api.v1.webhooks.stripe.Webhook.construct_event",
        lambda payload, sig_header, secret: fulfilled_event,
    )
    fulfilled_response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert fulfilled_response.status_code == 200, fulfilled_response.text

    db.expire_all()
    fulfilled_purchase = db.query(LeadPurchase).filter(LeadPurchase.id == purchase.id).first()
    assert fulfilled_purchase is not None
    assert fulfilled_purchase.status == "completed"
    assert fulfilled_purchase.credits_remaining == plan.daily_download_limit
    assert (
        db.query(LeadCreditLedger)
        .filter(
            LeadCreditLedger.purchase_id == purchase.id,
            LeadCreditLedger.movement_type == "purchase_grant",
        )
        .count()
        == 1
    )


@pytest.mark.integration
def test_webhook_payment_intent_succeeded_missing_payment_intent_id_is_ignored(
    client,
    db,
    monkeypatch,
):
    event = {
        "id": "evt_pi_succeeded_missing_id_1",
        "type": "payment_intent.succeeded",
        "data": {"object": {}},
    }
    monkeypatch.setattr(
        "app.api.v1.webhooks.stripe.Webhook.construct_event",
        lambda payload, sig_header, secret: event,
    )

    response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "ok"}
    assert db.query(LeadPurchase).count() == 0
    assert (
        db.query(ProcessedStripeEvent)
        .filter(ProcessedStripeEvent.stripe_event_id == "evt_pi_succeeded_missing_id_1")
        .count()
        == 1
    )


@pytest.mark.integration
def test_webhook_payment_intent_failed_does_not_downgrade_completed_purchase(
    client,
    db,
    user_factory,
    plan_factory,
    purchase_factory,
    monkeypatch,
):
    advisor = user_factory(
        role="advisor",
        password="AdvisorWebhookPIFailedCompleted123!",
        email="advisor.webhook.pi.failed.completed@example.com",
        name="Webhook PI Failed Completed Advisor",
    )
    plan = plan_factory(stripe_price_id="price_webhook_pi_failed_completed_guard")
    purchase = purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        stripe_checkout_session_id="cs_pi_failed_completed_guard_1",
        stripe_payment_intent_id="pi_failed_completed_guard_1",
        credits_total=4,
        credits_remaining=1,
        status="completed",
    )
    event = {
        "id": "evt_pi_failed_completed_guard_1",
        "type": "payment_intent.payment_failed",
        "data": {
            "object": {
                "id": "pi_failed_completed_guard_1",
            }
        },
    }
    monkeypatch.setattr(
        "app.api.v1.webhooks.stripe.Webhook.construct_event",
        lambda payload, sig_header, secret: event,
    )

    response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert response.status_code == 200, response.text

    db.refresh(purchase)
    assert purchase.status == "completed"
    assert purchase.credits_remaining == 1
    assert (
        db.query(ProcessedStripeEvent)
        .filter(ProcessedStripeEvent.stripe_event_id == "evt_pi_failed_completed_guard_1")
        .count()
        == 1
    )


@pytest.mark.integration
def test_webhook_payment_intent_failed_marks_pending_purchase_failed(
    client,
    db,
    user_factory,
    plan_factory,
    purchase_factory,
    monkeypatch,
):
    advisor = user_factory(
        role="advisor",
        password="AdvisorWebhookPIFailedPending123!",
        email="advisor.webhook.pi.failed.pending@example.com",
        name="Webhook PI Failed Pending Advisor",
    )
    plan = plan_factory(stripe_price_id="price_webhook_pi_failed_pending")
    purchase = purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        stripe_checkout_session_id="cs_pi_failed_pending_1",
        stripe_payment_intent_id="pi_failed_pending_1",
        credits_total=4,
        credits_remaining=0,
        status="pending",
    )
    event = {
        "id": "evt_pi_failed_pending_1",
        "type": "payment_intent.payment_failed",
        "data": {
            "object": {
                "id": "pi_failed_pending_1",
            }
        },
    }
    monkeypatch.setattr(
        "app.api.v1.webhooks.stripe.Webhook.construct_event",
        lambda payload, sig_header, secret: event,
    )

    response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert response.status_code == 200, response.text

    db.refresh(purchase)
    assert purchase.status == "failed"
    assert purchase.credits_remaining == 0
    assert (
        db.query(ProcessedStripeEvent)
        .filter(ProcessedStripeEvent.stripe_event_id == "evt_pi_failed_pending_1")
        .count()
        == 1
    )


@pytest.mark.integration
def test_webhook_payment_intent_failed_missing_payment_intent_id_is_ignored(
    client,
    db,
    user_factory,
    plan_factory,
    purchase_factory,
    monkeypatch,
):
    advisor = user_factory(
        role="advisor",
        password="AdvisorWebhookPIFailedMissingID123!",
        email="advisor.webhook.pi.failed.missing.id@example.com",
        name="Webhook PI Failed Missing ID Advisor",
    )
    plan = plan_factory(stripe_price_id="price_webhook_pi_failed_missing_id")
    purchase = purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        stripe_checkout_session_id="cs_pi_failed_missing_id_1",
        stripe_payment_intent_id="pi_pi_failed_missing_id_1",
        credits_total=4,
        credits_remaining=0,
        status="pending",
    )
    event = {
        "id": "evt_pi_failed_missing_id_1",
        "type": "payment_intent.payment_failed",
        "data": {"object": {}},
    }
    monkeypatch.setattr(
        "app.api.v1.webhooks.stripe.Webhook.construct_event",
        lambda payload, sig_header, secret: event,
    )

    response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "ok"}

    db.refresh(purchase)
    assert purchase.status == "pending"
    assert purchase.credits_remaining == 0
    assert (
        db.query(ProcessedStripeEvent)
        .filter(ProcessedStripeEvent.stripe_event_id == "evt_pi_failed_missing_id_1")
        .count()
        == 1
    )


@pytest.mark.integration
@pytest.mark.parametrize(
    ("status", "credits_remaining", "event_id", "payment_intent_id"),
    [
        ("refunded", 0, "evt_pi_failed_refunded_noop_1", "pi_failed_refunded_noop_1"),
        ("canceled", 2, "evt_pi_failed_canceled_noop_1", "pi_failed_canceled_noop_1"),
    ],
)
def test_webhook_payment_intent_failed_does_not_change_immutable_statuses(
    client,
    db,
    user_factory,
    plan_factory,
    purchase_factory,
    monkeypatch,
    status,
    credits_remaining,
    event_id,
    payment_intent_id,
):
    advisor = user_factory(
        role="advisor",
        password=f"AdvisorWebhookPIFailedImmutable123!{status}",
        email=f"advisor.webhook.pi.failed.immutable.{status}@example.com",
        name=f"Webhook PI Failed Immutable {status}",
    )
    plan = plan_factory(stripe_price_id=f"price_webhook_pi_failed_{status}_noop")
    purchase = purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        stripe_checkout_session_id=f"cs_{payment_intent_id}",
        stripe_payment_intent_id=payment_intent_id,
        credits_total=4,
        credits_remaining=credits_remaining,
        status=status,
    )
    event = {
        "id": event_id,
        "type": "payment_intent.payment_failed",
        "data": {
            "object": {
                "id": payment_intent_id,
            }
        },
    }
    monkeypatch.setattr(
        "app.api.v1.webhooks.stripe.Webhook.construct_event",
        lambda payload, sig_header, secret: event,
    )

    response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert response.status_code == 200, response.text

    db.refresh(purchase)
    assert purchase.status == status
    assert purchase.credits_remaining == credits_remaining
    assert (
        db.query(ProcessedStripeEvent)
        .filter(ProcessedStripeEvent.stripe_event_id == event_id)
        .count()
        == 1
    )


@pytest.mark.integration
def test_webhook_charge_refunded_applies_single_refund_adjustment_and_audit(
    client,
    db,
    user_factory,
    plan_factory,
    purchase_factory,
    monkeypatch,
):
    advisor = user_factory(
        role="advisor",
        password="AdvisorWebhookRefund123!",
        email="advisor.webhook.refund@example.com",
        name="Webhook Refund Advisor",
    )
    plan = plan_factory(stripe_price_id="price_webhook_refund")
    purchase = purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        credits_total=4,
        credits_remaining=4,
        status="completed",
        stripe_checkout_session_id="cs_refund_1",
        stripe_payment_intent_id="pi_refund_1",
    )
    refund_event = {
        "id": "evt_charge_refunded_1",
        "type": "charge.refunded",
        "data": {
            "object": {
                "id": "ch_refund_1",
                "payment_intent": "pi_refund_1",
                "amount_refunded": purchase.amount_cents,
                "reason": "requested_by_customer",
            }
        },
    }
    event_holder = {"value": refund_event}

    monkeypatch.setattr(
        "app.api.v1.webhooks.stripe.Webhook.construct_event",
        lambda payload, sig_header, secret: event_holder["value"],
    )

    first_response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert first_response.status_code == 200, first_response.text

    event_holder["value"] = {
        **refund_event,
        "id": "evt_charge_refunded_2",
    }
    second_response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert second_response.status_code == 200, second_response.text

    db.refresh(purchase)
    assert purchase.status == "refunded"
    assert purchase.credits_remaining == 0
    refund_ledger = (
        db.query(LeadCreditLedger)
        .filter(
            LeadCreditLedger.purchase_id == purchase.id,
            LeadCreditLedger.movement_type == "refund_adjustment",
        )
        .all()
    )
    assert len(refund_ledger) == 1
    assert refund_ledger[0].credits_delta == -4

    refund_audits = (
        db.query(AuditLog)
        .filter(
            AuditLog.action == "purchase_refund_adjusted",
            AuditLog.entity_id == purchase.id,
        )
        .all()
    )
    assert len(refund_audits) == 1
    refund_meta = refund_audits[0].meta_data or {}
    assert refund_meta.get("correlation_ids", {}).get("payment_intent_id") == "pi_refund_1"


@pytest.mark.integration
def test_webhook_charge_refunded_partial_then_full_adjusts_incrementally(
    client,
    db,
    user_factory,
    plan_factory,
    purchase_factory,
    monkeypatch,
):
    advisor = user_factory(
        role="advisor",
        password="AdvisorWebhookPartialRefund123!",
        email="advisor.webhook.partial.refund@example.com",
        name="Webhook Partial Refund Advisor",
    )
    plan = plan_factory(stripe_price_id="price_webhook_partial_refund")
    purchase = purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        credits_total=4,
        credits_remaining=4,
        status="completed",
        stripe_checkout_session_id="cs_partial_refund_1",
        stripe_payment_intent_id="pi_partial_refund_1",
    )
    event_holder = {
        "value": {
            "id": "evt_charge_partial_refund_1",
            "type": "charge.refunded",
            "data": {
                "object": {
                    "id": "ch_partial_refund_1",
                    "payment_intent": "pi_partial_refund_1",
                    "amount_refunded": 2500,
                    "reason": "requested_by_customer",
                }
            },
        }
    }
    monkeypatch.setattr(
        "app.api.v1.webhooks.stripe.Webhook.construct_event",
        lambda payload, sig_header, secret: event_holder["value"],
    )

    partial_response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert partial_response.status_code == 200, partial_response.text

    db.refresh(purchase)
    assert purchase.status == "completed"
    assert purchase.credits_remaining == 3
    partial_adjustments = (
        db.query(LeadCreditLedger)
        .filter(
            LeadCreditLedger.purchase_id == purchase.id,
            LeadCreditLedger.movement_type == "refund_adjustment",
        )
        .all()
    )
    assert len(partial_adjustments) == 1
    assert partial_adjustments[0].credits_delta == -1

    event_holder["value"] = {
        "id": "evt_charge_partial_refund_2",
        "type": "charge.refunded",
        "data": {
            "object": {
                "id": "ch_partial_refund_1",
                "payment_intent": "pi_partial_refund_1",
                "amount_refunded": purchase.amount_cents,
                "reason": "requested_by_customer",
            }
        },
    }
    full_response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert full_response.status_code == 200, full_response.text

    db.refresh(purchase)
    assert purchase.status == "refunded"
    assert purchase.credits_remaining == 0
    adjustments = (
        db.query(LeadCreditLedger)
        .filter(
            LeadCreditLedger.purchase_id == purchase.id,
            LeadCreditLedger.movement_type == "refund_adjustment",
        )
        .all()
    )
    assert len(adjustments) == 2
    assert sum(entry.credits_delta for entry in adjustments) == -4


@pytest.mark.integration
def test_webhook_charge_refunded_duplicate_cumulative_amount_is_idempotent(
    client,
    db,
    user_factory,
    plan_factory,
    purchase_factory,
    monkeypatch,
):
    advisor = user_factory(
        role="advisor",
        password="AdvisorWebhookPartialDuplicate123!",
        email="advisor.webhook.partial.duplicate@example.com",
        name="Webhook Partial Duplicate Advisor",
    )
    plan = plan_factory(stripe_price_id="price_webhook_partial_duplicate")
    purchase = purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        credits_total=4,
        credits_remaining=4,
        status="completed",
        stripe_checkout_session_id="cs_partial_duplicate_1",
        stripe_payment_intent_id="pi_partial_duplicate_1",
    )
    event_holder = {
        "value": {
            "id": "evt_charge_partial_duplicate_1",
            "type": "charge.refunded",
            "data": {
                "object": {
                    "id": "ch_partial_duplicate_1",
                    "payment_intent": "pi_partial_duplicate_1",
                    "amount_refunded": 5000,
                    "reason": "requested_by_customer",
                }
            },
        }
    }
    monkeypatch.setattr(
        "app.api.v1.webhooks.stripe.Webhook.construct_event",
        lambda payload, sig_header, secret: event_holder["value"],
    )

    first = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert first.status_code == 200, first.text

    event_holder["value"] = {
        "id": "evt_charge_partial_duplicate_2",
        "type": "charge.refunded",
        "data": {
            "object": {
                "id": "ch_partial_duplicate_1",
                "payment_intent": "pi_partial_duplicate_1",
                "amount_refunded": 5000,
                "reason": "requested_by_customer",
            }
        },
    }
    second = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert second.status_code == 200, second.text

    db.refresh(purchase)
    assert purchase.status == "completed"
    assert purchase.credits_remaining == 2
    adjustments = (
        db.query(LeadCreditLedger)
        .filter(
            LeadCreditLedger.purchase_id == purchase.id,
            LeadCreditLedger.movement_type == "refund_adjustment",
        )
        .all()
    )
    assert len(adjustments) == 1
    assert adjustments[0].credits_delta == -2


@pytest.mark.integration
def test_webhook_charge_refunded_missing_payment_intent_id_is_ignored(
    client,
    db,
    user_factory,
    plan_factory,
    purchase_factory,
    monkeypatch,
):
    advisor = user_factory(
        role="advisor",
        password="AdvisorWebhookRefundMissingPI123!",
        email="advisor.webhook.refund.missing.pi@example.com",
        name="Webhook Refund Missing PI Advisor",
    )
    plan = plan_factory(stripe_price_id="price_webhook_refund_missing_pi")
    purchase = purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        credits_total=4,
        credits_remaining=4,
        status="completed",
        stripe_checkout_session_id="cs_refund_missing_pi_1",
        stripe_payment_intent_id="pi_refund_missing_pi_1",
    )
    event = {
        "id": "evt_charge_refunded_missing_pi_1",
        "type": "charge.refunded",
        "data": {
            "object": {
                "id": "ch_refund_missing_pi_1",
                "amount_refunded": purchase.amount_cents,
                "reason": "requested_by_customer",
            }
        },
    }
    monkeypatch.setattr(
        "app.api.v1.webhooks.stripe.Webhook.construct_event",
        lambda payload, sig_header, secret: event,
    )

    response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "ok"}

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
    assert (
        db.query(ProcessedStripeEvent)
        .filter(ProcessedStripeEvent.stripe_event_id == "evt_charge_refunded_missing_pi_1")
        .count()
        == 1
    )


@pytest.mark.integration
def test_webhook_checkout_completed_replay_does_not_reactivate_refunded_purchase(
    client,
    db,
    user_factory,
    plan_factory,
    purchase_factory,
    monkeypatch,
):
    advisor = user_factory(
        role="advisor",
        password="AdvisorWebhookRefundReplay123!",
        email="advisor.webhook.refund.replay@example.com",
        name="Webhook Refund Replay Advisor",
    )
    plan = plan_factory(stripe_price_id="price_refund_replay_checkout")
    purchase = purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        credits_total=4,
        credits_remaining=4,
        status="completed",
        stripe_checkout_session_id="cs_refund_replay_1",
        stripe_payment_intent_id="pi_refund_replay_1",
    )

    refund_event = {
        "id": "evt_charge_refunded_replay_guard_1",
        "type": "charge.refunded",
        "data": {
            "object": {
                "id": "ch_refund_replay_1",
                "payment_intent": "pi_refund_replay_1",
                "amount_refunded": purchase.amount_cents,
                "reason": "requested_by_customer",
            }
        },
    }
    replay_success_event = _build_purchase_webhook_event(
        event_id="evt_checkout_completed_replay_guard_1",
        event_type="checkout.session.completed",
        session_id="cs_refund_replay_1",
        payment_intent_id="pi_refund_replay_1",
        user_id=advisor.id,
        package_id=plan.id,
        amount_cents=plan.price_cents,
    )
    event_holder = {"value": refund_event}

    monkeypatch.setattr(
        "app.api.v1.webhooks.stripe.Webhook.construct_event",
        lambda payload, sig_header, secret: event_holder["value"],
    )

    refund_response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert refund_response.status_code == 200, refund_response.text

    event_holder["value"] = replay_success_event
    replay_response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert replay_response.status_code == 200, replay_response.text

    db.refresh(purchase)
    assert purchase.status == "refunded"
    assert purchase.credits_remaining == 0
    assert (
        db.query(LeadCreditLedger)
        .filter(
            LeadCreditLedger.purchase_id == purchase.id,
            LeadCreditLedger.movement_type == "purchase_grant",
        )
        .count()
        == 0
    )
    assert (
        db.query(LeadCreditLedger)
        .filter(
            LeadCreditLedger.purchase_id == purchase.id,
            LeadCreditLedger.movement_type == "refund_adjustment",
        )
        .count()
        == 1
    )


@pytest.mark.integration
def test_webhook_checkout_completed_replay_preserves_consumed_credits(
    client,
    db,
    user_factory,
    plan_factory,
    purchase_factory,
    monkeypatch,
):
    advisor = user_factory(
        role="advisor",
        password="AdvisorWebhookConsumedReplay123!",
        email="advisor.webhook.consumed.replay@example.com",
        name="Webhook Consumed Replay Advisor",
    )
    plan = plan_factory(stripe_price_id="price_checkout_consumed_replay")
    purchase = purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        credits_total=4,
        credits_remaining=1,
        status="completed",
        stripe_checkout_session_id="cs_checkout_consumed_replay_1",
        stripe_payment_intent_id="pi_checkout_consumed_replay_1",
    )
    db.add(
        LeadCreditLedger(
            user_id=advisor.id,
            purchase_id=purchase.id,
            movement_type="purchase_grant",
            credits_delta=4,
            idempotency_key=f"purchase_grant:{purchase.id}",
            note="Seeded grant for replay idempotency",
        )
    )
    db.commit()

    replay_event = _build_purchase_webhook_event(
        event_id="evt_checkout_consumed_replay_guard_1",
        event_type="checkout.session.completed",
        session_id="cs_checkout_consumed_replay_1",
        payment_intent_id="pi_checkout_consumed_replay_1",
        user_id=advisor.id,
        package_id=plan.id,
        amount_cents=plan.price_cents,
    )
    monkeypatch.setattr(
        "app.api.v1.webhooks.stripe.Webhook.construct_event",
        lambda payload, sig_header, secret: replay_event,
    )

    response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert response.status_code == 200, response.text

    db.refresh(purchase)
    assert purchase.status == "completed"
    assert purchase.credits_remaining == 1
    assert (
        db.query(LeadCreditLedger)
        .filter(
            LeadCreditLedger.purchase_id == purchase.id,
            LeadCreditLedger.movement_type == "purchase_grant",
        )
        .count()
        == 1
    )


@pytest.mark.integration
def test_webhook_payment_intent_succeeded_replay_does_not_reactivate_refunded_purchase(
    client,
    db,
    user_factory,
    plan_factory,
    purchase_factory,
    monkeypatch,
):
    advisor = user_factory(
        role="advisor",
        password="AdvisorWebhookPIRefundReplay123!",
        email="advisor.webhook.pi.refund.replay@example.com",
        name="Webhook PI Refund Replay Advisor",
    )
    plan = plan_factory(stripe_price_id="price_refund_replay_pi")
    purchase = purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        credits_total=4,
        credits_remaining=0,
        status="refunded",
        stripe_checkout_session_id="cs_pi_refund_replay_1",
        stripe_payment_intent_id="pi_refund_replay_guard_2",
    )
    event = {
        "id": "evt_pi_succeeded_refund_replay_guard_1",
        "type": "payment_intent.succeeded",
        "data": {"object": {"id": "pi_refund_replay_guard_2"}},
    }

    monkeypatch.setattr(
        "app.api.v1.webhooks.stripe.Webhook.construct_event",
        lambda payload, sig_header, secret: event,
    )

    response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert response.status_code == 200, response.text

    db.refresh(purchase)
    assert purchase.status == "refunded"
    assert purchase.credits_remaining == 0
    assert (
        db.query(LeadCreditLedger)
        .filter(
            LeadCreditLedger.purchase_id == purchase.id,
            LeadCreditLedger.movement_type == "purchase_grant",
        )
        .count()
        == 0
    )


@pytest.mark.integration
def test_webhook_payment_intent_succeeded_replay_does_not_change_canceled_purchase(
    client,
    db,
    user_factory,
    plan_factory,
    purchase_factory,
    monkeypatch,
):
    advisor = user_factory(
        role="advisor",
        password="AdvisorWebhookPICanceledReplay123!",
        email="advisor.webhook.pi.canceled.replay@example.com",
        name="Webhook PI Canceled Replay Advisor",
    )
    plan = plan_factory(stripe_price_id="price_canceled_replay_pi")
    purchase = purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        credits_total=4,
        credits_remaining=0,
        status="canceled",
        stripe_checkout_session_id="cs_pi_canceled_replay_1",
        stripe_payment_intent_id="pi_canceled_replay_guard_1",
    )
    event_holder = {
        "value": {
            "id": "evt_pi_succeeded_canceled_replay_guard_1",
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": "pi_canceled_replay_guard_1"}},
        }
    }
    monkeypatch.setattr(
        "app.api.v1.webhooks.stripe.Webhook.construct_event",
        lambda payload, sig_header, secret: event_holder["value"],
    )

    monkeypatch.setattr("app.services.subscription_service.settings.PURCHASE_WEBHOOK_CREDIT_GRANT_ENABLED", False)
    disabled_response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert disabled_response.status_code == 200, disabled_response.text

    db.refresh(purchase)
    assert purchase.status == "canceled"

    event_holder["value"] = {
        "id": "evt_pi_succeeded_canceled_replay_guard_2",
        "type": "payment_intent.succeeded",
        "data": {"object": {"id": "pi_canceled_replay_guard_1"}},
    }
    monkeypatch.setattr("app.services.subscription_service.settings.PURCHASE_WEBHOOK_CREDIT_GRANT_ENABLED", True)
    enabled_response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert enabled_response.status_code == 200, enabled_response.text

    db.refresh(purchase)
    assert purchase.status == "canceled"
    assert purchase.credits_remaining == 0
    assert (
        db.query(LeadCreditLedger)
        .filter(
            LeadCreditLedger.purchase_id == purchase.id,
            LeadCreditLedger.movement_type == "purchase_grant",
        )
        .count()
        == 0
    )


@pytest.mark.integration
def test_webhook_checkout_completed_missing_metadata_is_acked_as_non_retryable(
    client,
    db,
    user_factory,
    monkeypatch,
):
    advisor = user_factory(
        role="advisor",
        password="AdvisorWebhookMissingMeta123!",
        email="advisor.webhook.missingmeta@example.com",
        name="Webhook Missing Meta",
    )

    event = {
        "id": "evt_checkout_missing_metadata",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_evt_missing_metadata",
                "mode": "payment",
                "payment_status": "paid",
                "amount_total": 5000,
                "currency": "usd",
                "metadata": {},
            }
        },
    }

    monkeypatch.setattr(
        "app.api.v1.webhooks.stripe.Webhook.construct_event",
        lambda payload, sig_header, secret: event,
    )
    metric_counters = []
    monkeypatch.setattr(
        "app.api.v1.webhooks.MetricsService.increment",
        lambda name, value=1, tags=None: metric_counters.append((name, value, tags or {})),
    )
    monkeypatch.setattr(
        "app.services.subscription_service.MetricsService.increment",
        lambda name, value=1, tags=None: metric_counters.append((name, value, tags or {})),
    )

    response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "ok"}

    poison = (
        db.query(StripePoisonEvent)
        .filter(StripePoisonEvent.stripe_event_id == "evt_checkout_missing_metadata")
        .first()
    )
    assert poison is not None
    assert poison.event_type == "checkout.session.completed"
    assert poison.reason == "missing_purchase_metadata"
    assert "session_id=cs_evt_missing_metadata" in poison.detail
    assert (poison.payload_excerpt or {}).get("object_id") == "cs_evt_missing_metadata"

    assert any(
        name == "purchase_webhook_non_retryable_total"
        and tags.get("reason") == "missing_purchase_metadata"
        and tags.get("poison_recorded") == "true"
        for name, _, tags in metric_counters
    )
    assert any(
        name == "purchase_webhook_acknowledged_non_retryable_total"
        and tags.get("reason") == "missing_purchase_metadata"
        for name, _, tags in metric_counters
    )

    current = client.post(
        "/api/v1/auth/login",
        json={"email": advisor.email, "password": "AdvisorWebhookMissingMeta123!"},
    )
    assert current.status_code == 204, current.text
    purchase_history = client.get("/api/v1/purchases/history?limit=5")
    assert purchase_history.status_code == 200, purchase_history.text
    assert purchase_history.json() == {"items": []}


@pytest.mark.integration
def test_webhook_checkout_completed_missing_session_id_is_acked_as_non_retryable(
    client,
    db,
    monkeypatch,
):
    event = {
        "id": "evt_checkout_missing_session_id_1",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "mode": "payment",
                "payment_status": "paid",
                "payment_intent": "pi_missing_session_id_1",
                "amount_total": 5000,
                "currency": "usd",
                "metadata": {"user_id": "1", "package_id": "1"},
            }
        },
    }
    monkeypatch.setattr(
        "app.api.v1.webhooks.stripe.Webhook.construct_event",
        lambda payload, sig_header, secret: event,
    )

    response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "ok"}

    poison = (
        db.query(StripePoisonEvent)
        .filter(StripePoisonEvent.stripe_event_id == "evt_checkout_missing_session_id_1")
        .first()
    )
    assert poison is not None
    assert poison.reason == "missing_session_id"
    assert "missing session ID" in poison.detail
    assert db.query(LeadPurchase).count() == 0


@pytest.mark.integration
def test_webhook_checkout_completed_invalid_metadata_is_acked_as_non_retryable(
    client,
    db,
    monkeypatch,
):
    event = {
        "id": "evt_checkout_invalid_metadata_1",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_evt_invalid_metadata_1",
                "mode": "payment",
                "payment_status": "paid",
                "payment_intent": "pi_invalid_metadata_1",
                "amount_total": 5000,
                "currency": "usd",
                "metadata": {"user_id": "not-an-int", "package_id": "also-not-an-int"},
            }
        },
    }
    monkeypatch.setattr(
        "app.api.v1.webhooks.stripe.Webhook.construct_event",
        lambda payload, sig_header, secret: event,
    )

    response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "ok"}

    poison = (
        db.query(StripePoisonEvent)
        .filter(StripePoisonEvent.stripe_event_id == "evt_checkout_invalid_metadata_1")
        .first()
    )
    assert poison is not None
    assert poison.reason == "invalid_purchase_metadata"
    assert "invalid purchase metadata" in poison.detail
    assert db.query(LeadPurchase).count() == 0


@pytest.mark.integration
def test_webhook_checkout_completed_missing_package_is_acked_as_non_retryable_once(
    client,
    db,
    user_factory,
    monkeypatch,
):
    advisor = user_factory(
        role="advisor",
        password="AdvisorWebhookMissingPlan123!",
        email="advisor.webhook.missingplan@example.com",
        name="Webhook Missing Plan",
    )

    event = {
        "id": "evt_checkout_missing_plan",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_evt_missing_plan",
                "mode": "payment",
                "payment_status": "paid",
                "payment_intent": "pi_missing_plan",
                "amount_total": 5000,
                "currency": "usd",
                "metadata": {"user_id": str(advisor.id), "package_id": "999999"},
            }
        },
    }

    monkeypatch.setattr(
        "app.api.v1.webhooks.stripe.Webhook.construct_event",
        lambda payload, sig_header, secret: event,
    )
    metric_counters = []
    monkeypatch.setattr(
        "app.api.v1.webhooks.MetricsService.increment",
        lambda name, value=1, tags=None: metric_counters.append((name, value, tags or {})),
    )
    monkeypatch.setattr(
        "app.services.subscription_service.MetricsService.increment",
        lambda name, value=1, tags=None: metric_counters.append((name, value, tags or {})),
    )

    first_response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert first_response.status_code == 200, first_response.text
    assert first_response.json() == {"status": "ok"}

    second_response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert second_response.status_code == 200, second_response.text
    assert second_response.json() == {"status": "ok"}

    poison_rows = (
        db.query(StripePoisonEvent)
        .filter(StripePoisonEvent.stripe_event_id == "evt_checkout_missing_plan")
        .all()
    )
    assert len(poison_rows) == 1
    poison = poison_rows[0]
    assert poison.event_type == "checkout.session.completed"
    assert poison.reason == "missing_package"
    assert "package_id=999999" in poison.detail

    assert any(
        name == "purchase_webhook_non_retryable_total"
        and tags.get("reason") == "missing_package"
        and tags.get("poison_recorded") == "true"
        for name, _, tags in metric_counters
    )
    assert any(
        name == "purchase_webhook_non_retryable_total"
        and tags.get("reason") == "missing_package"
        and tags.get("poison_recorded") == "false"
        for name, _, tags in metric_counters
    )
    assert (
        sum(1 for name, _, tags in metric_counters if name == "purchase_webhook_acknowledged_non_retryable_total")
        == 2
    )

    current = client.post(
        "/api/v1/auth/login",
        json={"email": advisor.email, "password": "AdvisorWebhookMissingPlan123!"},
    )
    assert current.status_code == 204, current.text
    purchase_history = client.get("/api/v1/purchases/history?limit=5")
    assert purchase_history.status_code == 200, purchase_history.text
    assert purchase_history.json() == {"items": []}


@pytest.mark.integration
@pytest.mark.parametrize(
    ("event_type", "event_id"),
    [
        ("customer.subscription.updated", "evt_subscription_updated_ignored"),
        ("customer.subscription.deleted", "evt_subscription_deleted_ignored"),
        ("invoice.payment_succeeded", "evt_invoice_payment_succeeded_ignored"),
        ("invoice.payment_failed", "evt_invoice_payment_failed_ignored"),
    ],
)
def test_webhook_subscription_lifecycle_event_is_ignored(
    client,
    db,
    user_factory,
    monkeypatch,
    event_type,
    event_id,
):
    user_factory(
        role="advisor",
        password="AdvisorWebhookIgnored123!",
        email="advisor.webhook.ignored@example.com",
        name="Webhook Ignored Advisor",
    )

    event = {
        "id": event_id,
        "type": event_type,
        "data": {
            "object": {
                "id": "sub_ignored_123",
                "status": "active",
            }
        },
    }

    monkeypatch.setattr(
        "app.api.v1.webhooks.stripe.Webhook.construct_event",
        lambda payload, sig_header, secret: event,
    )

    response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "ok"}
    assert (
        db.query(ProcessedStripeEvent)
        .filter(ProcessedStripeEvent.stripe_event_id == event_id)
        .count()
        == 1
    )


@pytest.mark.integration
def test_webhook_unknown_event_type_is_acked_without_side_effects(
    client,
    db,
    monkeypatch,
):
    event = {
        "id": "evt_unknown_type_1",
        "type": "totally.unknown.event",
        "data": {"object": {"id": "obj_unknown_type_1"}},
    }
    monkeypatch.setattr(
        "app.api.v1.webhooks.stripe.Webhook.construct_event",
        lambda payload, sig_header, secret: event,
    )

    response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "ok"}
    assert db.query(LeadPurchase).count() == 0
    assert (
        db.query(ProcessedStripeEvent)
        .filter(ProcessedStripeEvent.stripe_event_id == "evt_unknown_type_1")
        .count()
        == 1
    )


@pytest.mark.integration
def test_billing_summary_without_customer_returns_empty(
    client,
    user_factory,
    auth_headers,
):
    advisor = user_factory(
        role="advisor",
        password="AdvisorBilling123!",
        email="advisor.billing@example.com",
        name="Billing Advisor",
    )
    headers = auth_headers(advisor.email, "AdvisorBilling123!")
    response = client.get("/api/v1/purchases/billing/summary", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json() == {"payment_method": None, "invoices": []}


@pytest.mark.integration
def test_billing_summary_stripe_error_returns_502(
    client,
    db,
    user_factory,
    auth_headers,
    monkeypatch,
):
    advisor = user_factory(
        role="advisor",
        password="AdvisorBillingFail123!",
        email="advisor.billing.fail@example.com",
        name="Billing Fail Advisor",
    )
    advisor.stripe_customer_id = "cus_billing_fail_123"
    db.add(advisor)
    db.commit()

    monkeypatch.setattr(
        "app.services.subscription_service.settings.STRIPE_SECRET_KEY",
        "sk_test_billing",
    )

    def _raise_billing_retrieve_error(*args, **kwargs):
        raise stripe.error.StripeError("stripe unavailable")

    monkeypatch.setattr(
        "app.services.subscription_service.stripe.Customer.retrieve",
        _raise_billing_retrieve_error,
    )

    headers = auth_headers(advisor.email, "AdvisorBillingFail123!")
    response = client.get("/api/v1/purchases/billing/summary", headers=headers)
    assert response.status_code == 502
    assert response.json()["detail"] == "Stripe billing provider unavailable"


@pytest.mark.integration
def test_billing_summary_links_purchase_invoice_to_package_and_backfills_purchase(
    client,
    db,
    user_factory,
    auth_headers,
    plan_factory,
    purchase_factory,
    monkeypatch,
):
    advisor = user_factory(
        role="advisor",
        password="AdvisorBillingLinked123!",
        email="advisor.billing.linked@example.com",
        name="Billing Linked Advisor",
    )
    advisor.stripe_customer_id = "cus_billing_linked_123"
    db.add(advisor)
    db.commit()

    package = plan_factory(
        name="Single-State Leads (10)",
        stripe_price_id="price_billing_linked",
        daily_download_limit=10,
    )
    purchase = purchase_factory(
        user_id=advisor.id,
        package_id=package.id,
        status="completed",
        stripe_checkout_session_id="cs_billing_linked_1",
        stripe_payment_intent_id="pi_billing_linked_1",
        stripe_invoice_id=None,
    )

    monkeypatch.setattr(
        "app.services.subscription_service.settings.STRIPE_SECRET_KEY",
        "sk_test_billing_linked",
    )
    monkeypatch.setattr(
        "app.services.subscription_service.PaymentService._init_stripe",
        lambda: None,
    )
    monkeypatch.setattr(
        "app.services.subscription_service.stripe.Customer.retrieve",
        lambda customer_id, expand=None: {
            "id": customer_id,
            "invoice_settings": {"default_payment_method": None},
        },
    )
    monkeypatch.setattr(
        "app.services.subscription_service.stripe.Invoice.list",
        lambda customer, limit=50: {
            "data": [
                {
                    "id": "in_billing_linked_1",
                    "payment_intent": "pi_billing_linked_1",
                    "amount_paid": 10000,
                    "currency": "usd",
                    "status": "paid",
                    "created": int(datetime.now(timezone.utc).timestamp()),
                    "hosted_invoice_url": "https://stripe.test/hosted/in_billing_linked_1",
                    "invoice_pdf": "https://stripe.test/pdf/in_billing_linked_1.pdf",
                    "description": "One-time package purchase",
                }
            ]
        },
    )

    headers = auth_headers(advisor.email, "AdvisorBillingLinked123!")
    response = client.get("/api/v1/purchases/billing/summary", headers=headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["payment_method"] is None
    assert len(payload["invoices"]) == 1
    first_invoice = payload["invoices"][0]
    assert first_invoice["stripe_invoice_id"] == "in_billing_linked_1"
    assert first_invoice["package_name"].startswith("Single-State Leads (10)")
    assert first_invoice["hosted_invoice_url"] == "https://stripe.test/hosted/in_billing_linked_1"
    assert first_invoice["invoice_pdf"] == "https://stripe.test/pdf/in_billing_linked_1.pdf"

    db.refresh(purchase)
    assert purchase.stripe_invoice_id == "in_billing_linked_1"


@pytest.mark.integration
def test_credit_summary_returns_aggregated_purchase_credits(
    client,
    user_factory,
    license_factory,
    plan_factory,
    purchase_factory,
    auth_headers,
):
    advisor, headers = _create_advisor_with_verified_license(
        user_factory,
        license_factory,
        auth_headers,
    )
    plan = plan_factory(
        daily_download_limit=10,
        stripe_price_id="price_credit_summary",
    )
    purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        credits_total=10,
        credits_remaining=7,
        status="completed",
    )
    purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        credits_total=5,
        credits_remaining=5,
        status="completed",
    )
    purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        credits_total=8,
        credits_remaining=0,
        status="failed",
    )

    response = client.get("/api/v1/purchases/balance", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json() == {
        "total_credits": 15,
        "remaining_credits": 12,
        "completed_purchases": 2,
    }
