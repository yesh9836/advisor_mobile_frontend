from datetime import datetime, timezone

import pytest
import stripe

from app.models.audit_log import AuditLog
from app.models.lead import LeadOwnership
from app.models.purchase import LeadCreditLedger, LeadPurchase
from app.models.subscription import Subscription
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
):
    return {
        "id": event_id,
        "type": event_type,
        "data": {
            "object": {
                "id": session_id,
                "mode": "payment",
                "payment_status": payment_status,
                "payment_intent": payment_intent_id,
                "amount_total": amount_cents,
                "currency": "usd",
                "created": int(datetime.now(timezone.utc).timestamp()),
                "metadata": {"user_id": str(user_id), "package_id": str(package_id)},
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
    assert captured_checkout_kwargs["metadata"] == {
        "user_id": str(advisor.id),
        "package_id": str(plan.id),
    }
    assert captured_checkout_kwargs["payment_intent_data"]["metadata"] == {
        "user_id": str(advisor.id),
        "package_id": str(plan.id),
    }


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
    assert audit_event.entity_id is None
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
def test_checkout_allows_purchase_with_existing_trialing_subscription(
    client,
    user_factory,
    license_factory,
    plan_factory,
    subscription_factory,
    auth_headers,
    monkeypatch,
):
    advisor, headers = _create_advisor_with_verified_license(
        user_factory,
        license_factory,
        auth_headers,
    )
    existing_plan = plan_factory(stripe_price_id="price_existing_trialing_plan")
    target_plan = plan_factory(stripe_price_id="price_target_trialing_plan")
    _ = subscription_factory(
        user_id=advisor.id,
        plan_id=existing_plan.id,
        status="trialing",
        stripe_subscription_id="sub_trialing_existing",
    )

    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.create_or_get_stripe_customer",
        lambda db, user: "cus_trialing",
    )
    monkeypatch.setattr(
        "app.services.subscription_service.stripe.checkout.Session.create",
        lambda **kwargs: {"id": "cs_trialing_ok", "url": "https://checkout.stripe.test/trialing-ok"},
    )

    response = client.post(
        "/api/v1/purchases/checkout",
        headers=headers,
        json={"package_id": target_plan.id},
    )
    assert response.status_code == 200, response.text
    assert response.json()["session_id"] == "cs_trialing_ok"


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
    assert purchase.credits_remaining == plan.daily_download_limit

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

    purchases = (
        db.query(LeadPurchase)
        .filter(LeadPurchase.stripe_checkout_session_id == "cs_same_event")
        .all()
    )
    assert len(purchases) == 1
    purchase = purchases[0]
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

    purchases = (
        db.query(LeadPurchase)
        .filter(LeadPurchase.stripe_payment_intent_id == "pi_semantic_dup_shared")
        .all()
    )
    assert len(purchases) == 1
    purchase = purchases[0]
    assert purchase.stripe_checkout_session_id == "cs_semantic_dup_1"
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

    event = {
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
        lambda payload, sig_header, secret: event,
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

    monkeypatch.setattr("app.services.subscription_service.settings.PURCHASE_WEBHOOK_CREDIT_GRANT_ENABLED", True)
    monkeypatch.setattr(
        "app.api.v1.webhooks.stripe.Webhook.construct_event",
        lambda payload, sig_header, secret: event,
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
def test_webhook_checkout_completed_missing_metadata_returns_500(
    client,
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

    response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert response.status_code == 500
    assert response.json()["detail"] == "Webhook processing failed"

    current = client.post(
        "/api/v1/auth/login",
        json={"email": advisor.email, "password": "AdvisorWebhookMissingMeta123!"},
    )
    assert current.status_code == 204, current.text
    purchase_history = client.get("/api/v1/purchases/history?limit=5")
    assert purchase_history.status_code == 200, purchase_history.text
    assert purchase_history.json() == {"items": []}


@pytest.mark.integration
def test_webhook_checkout_completed_missing_plan_returns_500(
    client,
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

    response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert response.status_code == 500
    assert response.json()["detail"] == "Webhook processing failed"

    current = client.post(
        "/api/v1/auth/login",
        json={"email": advisor.email, "password": "AdvisorWebhookMissingPlan123!"},
    )
    assert current.status_code == 204, current.text
    purchase_history = client.get("/api/v1/purchases/history?limit=5")
    assert purchase_history.status_code == 200, purchase_history.text
    assert purchase_history.json() == {"items": []}


@pytest.mark.integration
def test_webhook_invoice_payment_succeeded_stripe_error_returns_500(
    client,
    db,
    user_factory,
    plan_factory,
    subscription_factory,
    monkeypatch,
):
    advisor = user_factory(
        role="advisor",
        password="AdvisorWebhookInvoice123!",
        email="advisor.webhook.invoice@example.com",
        name="Webhook Invoice Advisor",
    )
    plan = plan_factory(stripe_price_id="price_webhook_invoice")
    sub = subscription_factory(
        user_id=advisor.id,
        plan_id=plan.id,
        status="past_due",
        stripe_subscription_id="sub_invoice_succeeded_error",
    )

    event = {
        "id": "evt_invoice_payment_succeeded_error",
        "type": "invoice.payment_succeeded",
        "data": {
            "object": {
                "id": "in_test_invoice",
                "subscription": "sub_invoice_succeeded_error",
            }
        },
    }

    monkeypatch.setattr(
        "app.api.v1.webhooks.stripe.Webhook.construct_event",
        lambda payload, sig_header, secret: event,
    )

    def _raise_transient_retrieve_error(stripe_subscription_id):
        raise stripe.error.StripeError("transient stripe api error")

    monkeypatch.setattr(
        "app.services.subscription_service.stripe.Subscription.retrieve",
        _raise_transient_retrieve_error,
    )

    response = client.post(
        "/api/v1/webhooks/stripe",
        headers={"stripe-signature": "sig_test"},
        json={"mock": "payload"},
    )
    assert response.status_code == 500
    assert response.json()["detail"] == "Webhook processing failed"

    db.expire_all()
    refreshed = (
        db.query(Subscription)
        .filter(Subscription.stripe_subscription_id == sub.stripe_subscription_id)
        .first()
    )
    assert refreshed is not None
    assert refreshed.status == "past_due"


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
