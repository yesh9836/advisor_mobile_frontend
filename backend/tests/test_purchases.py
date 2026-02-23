import time
from uuid import uuid4

import pytest

from app.core.config import settings
from app.models.lead import LeadOwnership
from app.models.purchase import LeadCreditLedger
from app.services.payment_service import PaymentService


def _create_advisor_with_verified_license(user_factory, license_factory, auth_headers):
    unique_key = uuid4().hex[:10]
    advisor = user_factory(
        role="advisor",
        password="AdvisorPurchases123!",
        email=f"advisor.purchases.{unique_key}@example.com",
        name="Advisor Purchases",
    )
    license_factory(
        user_id=advisor.id,
        state="CA",
        status="verified",
        license_number="CA-PURCHASE-001",
    )
    headers = auth_headers(advisor.email, "AdvisorPurchases123!")
    return advisor, headers


def _enable_first_purchase_offer(client, admin_headers, trigger_package_id: int) -> int:
    update_response = client.put(
        "/api/v1/admin/first-purchase-offer",
        headers=admin_headers,
        json={
            "is_enabled": True,
            "trigger_package_id": trigger_package_id,
            "offer_credits_total": 5,
            "offer_price_cents": 6400,
            "offer_currency": "USD",
            "headline": "First order bonus",
            "message": "Upgrade and receive more credits.",
            "cta_label": "Upgrade now",
        },
    )
    assert update_response.status_code == 200, update_response.text
    offer_package_id = update_response.json().get("offer_package_id")
    assert offer_package_id is not None
    return int(offer_package_id)


@pytest.mark.integration
def test_purchase_packages_return_sorted_by_price(client, plan_factory):
    plan_factory(name="PackageA", price_cents=10000, stripe_price_id="price_package_a")
    plan_factory(name="PackageB", price_cents=20000, stripe_price_id="price_package_b")

    purchases_response = client.get("/api/v1/purchases/packages")
    assert purchases_response.status_code == 200, purchases_response.text

    purchase_payload = purchases_response.json()
    assert [item["price_cents"] for item in purchase_payload] == sorted(
        [item["price_cents"] for item in purchase_payload]
    )


@pytest.mark.integration
def test_purchase_checkout_uses_idempotency_key_and_metadata(
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
    plan = plan_factory(stripe_price_id="price_purchase_checkout_success")

    captured_checkout_kwargs = {}
    retry_token = "retry_purchase_pkg_checkout_1234"

    def _mock_checkout_create(**kwargs):
        captured_checkout_kwargs.update(kwargs)
        return {
            "id": "cs_purchase_checkout",
            "url": "https://checkout.stripe.test/purchase-session",
        }

    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.create_or_get_stripe_customer",
        lambda db, user: "cus_purchase_checkout_success",
    )
    monkeypatch.setattr(
        "app.services.subscription_service.stripe.checkout.Session.create",
        _mock_checkout_create,
    )

    response = client.post(
        "/api/v1/purchases/checkout",
        headers=headers,
        json={"package_id": plan.id, "retry_token": retry_token},
    )
    assert response.status_code == 200, response.text
    assert response.json()["session_id"] == "cs_purchase_checkout"
    assert captured_checkout_kwargs["mode"] == "payment"
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
    assert captured_checkout_kwargs["idempotency_key"] == PaymentService.checkout_session_idempotency_key(
        user_id=advisor.id,
        package_id=plan.id,
        retry_token=retry_token,
    )


@pytest.mark.integration
def test_purchase_checkout_rejects_invalid_retry_token(
    client,
    user_factory,
    license_factory,
    plan_factory,
    auth_headers,
    monkeypatch,
):
    _, headers = _create_advisor_with_verified_license(
        user_factory,
        license_factory,
        auth_headers,
    )
    plan = plan_factory(stripe_price_id="price_purchase_checkout_retry_token_invalid")

    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.create_or_get_stripe_customer",
        lambda db, user: "cus_purchase_checkout_retry_token_invalid",
    )

    response = client.post(
        "/api/v1/purchases/checkout",
        headers=headers,
        json={"package_id": plan.id, "retry_token": "bad token with spaces"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid checkout retry token"


@pytest.mark.integration
def test_purchase_checkout_is_blocked_when_rollout_disabled_for_user(
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
    plan = plan_factory(stripe_price_id="price_purchase_rollout_blocked")
    _ = advisor

    monkeypatch.setattr("app.services.subscription_service.settings.ONE_TIME_PURCHASES_ENABLED", False)
    monkeypatch.setattr("app.services.subscription_service.settings.ONE_TIME_PURCHASES_ROLLOUT_USER_IDS", [])
    monkeypatch.setattr("app.services.subscription_service.settings.ONE_TIME_PURCHASES_ROLLOUT_EMAILS", [])

    response = client.post(
        "/api/v1/purchases/checkout",
        headers=headers,
        json={"package_id": plan.id},
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "One-time purchases are temporarily unavailable for this account"


@pytest.mark.integration
def test_purchase_checkout_allows_rollout_allowlisted_user_when_globally_disabled(
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
    plan = plan_factory(stripe_price_id="price_purchase_rollout_allowlisted")

    monkeypatch.setattr("app.services.subscription_service.settings.ONE_TIME_PURCHASES_ENABLED", False)
    monkeypatch.setattr(
        "app.services.subscription_service.settings.ONE_TIME_PURCHASES_ROLLOUT_USER_IDS",
        [advisor.id],
    )
    monkeypatch.setattr("app.services.subscription_service.settings.ONE_TIME_PURCHASES_ROLLOUT_EMAILS", [])
    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.create_or_get_stripe_customer",
        lambda db, user: "cus_purchase_rollout_allowlisted",
    )
    monkeypatch.setattr(
        "app.services.subscription_service.stripe.checkout.Session.create",
        lambda **kwargs: {
            "id": "cs_purchase_rollout_allowlisted",
            "url": "https://checkout.stripe.test/purchase-rollout-allowlisted",
        },
    )

    response = client.post(
        "/api/v1/purchases/checkout",
        headers=headers,
        json={"package_id": plan.id},
    )
    assert response.status_code == 200, response.text
    assert response.json()["session_id"] == "cs_purchase_rollout_allowlisted"


@pytest.mark.integration
def test_purchase_balance_orders_and_history_endpoints(
    client,
    db,
    user_factory,
    license_factory,
    plan_factory,
    purchase_factory,
    lead_factory,
    auth_headers,
):
    advisor, headers = _create_advisor_with_verified_license(
        user_factory,
        license_factory,
        auth_headers,
    )
    plan = plan_factory(stripe_price_id="price_purchase_orders")

    completed_purchase = purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        credits_total=10,
        credits_remaining=6,
        status="completed",
        stripe_checkout_session_id="cs_purchase_order_completed",
        stripe_payment_intent_id="pi_purchase_order_completed",
    )
    pending_purchase = purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        credits_total=4,
        credits_remaining=0,
        status="pending",
        stripe_checkout_session_id="cs_purchase_order_pending",
        stripe_payment_intent_id="pi_purchase_order_pending",
    )
    _ = pending_purchase
    _ = completed_purchase
    assigned_a = lead_factory(state_code="CA", mobile_phone="555-PURCHASE-ASSIGN-0001")
    assigned_b = lead_factory(state_code="CA", mobile_phone="555-PURCHASE-ASSIGN-0002")
    db.add(LeadOwnership(user_id=advisor.id, lead_id=assigned_a.id, purchase_id=completed_purchase.id))
    db.add(LeadOwnership(user_id=advisor.id, lead_id=assigned_b.id, purchase_id=completed_purchase.id))
    db.commit()

    balance_response = client.get("/api/v1/purchases/balance", headers=headers)
    assert balance_response.status_code == 200, balance_response.text
    assert balance_response.json() == {
        "total_credits": 10,
        "remaining_credits": 6,
        "completed_purchases": 1,
    }

    orders_response = client.get("/api/v1/purchases/orders?page=1&size=20", headers=headers)
    assert orders_response.status_code == 200, orders_response.text
    orders_payload = orders_response.json()
    assert orders_payload["total"] == 2
    assert len(orders_payload["items"]) == 2
    assert all("order_reference" in item for item in orders_payload["items"])
    assert all("credits_total" in item for item in orders_payload["items"])
    assert all("entitled_credits_total" in item for item in orders_payload["items"])
    assert all("credits_remaining" in item for item in orders_payload["items"])
    assert all("assigned_count" in item for item in orders_payload["items"])
    assert all("unfulfilled_count" in item for item in orders_payload["items"])
    assert all("fulfillment_status" in item for item in orders_payload["items"])
    orders_by_id = {item["id"]: item for item in orders_payload["items"]}
    assert orders_by_id[completed_purchase.id]["assigned_count"] == 2
    assert orders_by_id[completed_purchase.id]["entitled_credits_total"] == 10
    assert orders_by_id[completed_purchase.id]["unfulfilled_count"] == 8
    assert orders_by_id[completed_purchase.id]["fulfillment_status"] == "partially_fulfilled"
    assert orders_by_id[pending_purchase.id]["assigned_count"] == 0
    assert orders_by_id[pending_purchase.id]["entitled_credits_total"] == 4
    assert orders_by_id[pending_purchase.id]["unfulfilled_count"] == 4
    assert orders_by_id[pending_purchase.id]["fulfillment_status"] == "pending"

    completed_only = client.get(
        "/api/v1/purchases/orders?page=1&size=20&status=completed",
        headers=headers,
    )
    assert completed_only.status_code == 200, completed_only.text
    completed_payload = completed_only.json()
    assert completed_payload["total"] == 1
    assert completed_payload["items"][0]["status"] == "completed"
    assert completed_payload["items"][0]["order_reference"] == "cs_purchase_order_completed"

    history_response = client.get("/api/v1/purchases/history?limit=10", headers=headers)
    assert history_response.status_code == 200, history_response.text
    history_payload = history_response.json()
    assert len(history_payload["items"]) == 2
    assert history_payload["items"][0]["purchased_at"] >= history_payload["items"][1]["purchased_at"]
    assert all("assigned_count" in item for item in history_payload["items"])
    assert all("entitled_credits_total" in item for item in history_payload["items"])
    assert all("unfulfilled_count" in item for item in history_payload["items"])
    assert all("fulfillment_status" in item for item in history_payload["items"])


@pytest.mark.integration
def test_purchase_orders_and_history_use_refund_adjusted_entitlement_for_pending_math(
    client,
    db,
    user_factory,
    license_factory,
    plan_factory,
    purchase_factory,
    lead_factory,
    auth_headers,
):
    advisor, headers = _create_advisor_with_verified_license(
        user_factory,
        license_factory,
        auth_headers,
    )
    plan = plan_factory(stripe_price_id="price_purchase_orders_refund_adjusted")
    completed_purchase = purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        credits_total=10,
        credits_remaining=2,
        status="completed",
        stripe_checkout_session_id="cs_purchase_order_refund_adjusted",
        stripe_payment_intent_id="pi_purchase_order_refund_adjusted",
    )

    for index in range(8):
        lead = lead_factory(state_code="CA", mobile_phone=f"555-PURCHASE-REFUND-{index:04d}")
        db.add(LeadOwnership(user_id=advisor.id, lead_id=lead.id, purchase_id=completed_purchase.id))

    db.add(
        LeadCreditLedger(
            user_id=advisor.id,
            purchase_id=completed_purchase.id,
            movement_type="refund_adjustment",
            credits_delta=-4,
            note="test partial refund adjustment",
            idempotency_key=f"test:refund-adjustment:{completed_purchase.id}",
        )
    )
    db.commit()

    orders_response = client.get("/api/v1/purchases/orders?page=1&size=20", headers=headers)
    assert orders_response.status_code == 200, orders_response.text
    order_item = orders_response.json()["items"][0]
    assert order_item["credits_total"] == 10
    assert order_item["entitled_credits_total"] == 6
    assert order_item["assigned_count"] == 8
    assert order_item["unfulfilled_count"] == 0
    assert order_item["fulfillment_status"] == "fulfilled"

    history_response = client.get("/api/v1/purchases/history?limit=20", headers=headers)
    assert history_response.status_code == 200, history_response.text
    history_item = history_response.json()["items"][0]
    assert history_item["credits_total"] == 10
    assert history_item["entitled_credits_total"] == 6
    assert history_item["assigned_count"] == 8
    assert history_item["unfulfilled_count"] == 0
    assert history_item["fulfillment_status"] == "fulfilled"


@pytest.mark.integration
def test_first_purchase_offer_eligibility_depends_on_first_completed_purchase(
    client,
    user_factory,
    auth_headers,
    plan_factory,
    purchase_factory,
):
    admin = user_factory(
        role="admin",
        password="AdminOffer123!",
        email=f"admin.offer.{uuid4().hex[:8]}@example.com",
        name="Offer Admin",
    )
    admin_headers = auth_headers(admin.email, "AdminOffer123!")

    advisor = user_factory(
        role="advisor",
        password="AdvisorOffer123!",
        email=f"advisor.offer.{uuid4().hex[:8]}@example.com",
        name="Offer Advisor",
    )
    advisor_headers = auth_headers(advisor.email, "AdvisorOffer123!")

    trigger_package = plan_factory(
        name="OfferTrigger",
        price_cents=11000,
        daily_download_limit=10,
    )

    update_response = client.put(
        "/api/v1/admin/first-purchase-offer",
        headers=admin_headers,
        json={
            "is_enabled": True,
            "trigger_package_id": trigger_package.id,
            "offer_credits_total": 5,
            "offer_price_cents": 6400,
            "offer_currency": "USD",
            "headline": "First order bonus",
            "message": "Upgrade and receive more credits.",
            "cta_label": "Upgrade now",
        },
    )
    assert update_response.status_code == 200, update_response.text

    before_purchase = client.get(
        "/api/v1/purchases/first-purchase-offer?checkout_session_id=cs_before_purchase",
        headers=advisor_headers,
    )
    assert before_purchase.status_code == 200, before_purchase.text
    assert before_purchase.json() == {"eligible": False, "offer": None}

    first_purchase = purchase_factory(
        user_id=advisor.id,
        package_id=trigger_package.id,
        status="completed",
        credits_total=trigger_package.daily_download_limit,
        stripe_checkout_session_id="cs_first_purchase_offer",
    )

    first_check = client.get(
        "/api/v1/purchases/first-purchase-offer?checkout_session_id=cs_first_purchase_offer",
        headers=advisor_headers,
    )
    assert first_check.status_code == 200, first_check.text
    assert first_check.json()["eligible"] is True
    assert first_check.json()["offer"]["offer_package_id"] is not None
    assert first_check.json()["offer"]["offer_credits_total"] == 5

    add_on_purchase = purchase_factory(
        user_id=advisor.id,
        package_id=first_check.json()["offer"]["offer_package_id"],
        status="completed",
        credits_total=5,
        stripe_checkout_session_id="cs_second_purchase_offer",
    )
    _ = first_purchase
    _ = add_on_purchase

    after_second_purchase = client.get(
        "/api/v1/purchases/first-purchase-offer?checkout_session_id=cs_first_purchase_offer",
        headers=advisor_headers,
    )
    assert after_second_purchase.status_code == 200, after_second_purchase.text
    assert after_second_purchase.json() == {"eligible": False, "offer": None}


@pytest.mark.integration
def test_purchase_checkout_rejects_direct_managed_offer_when_not_eligible(
    client,
    user_factory,
    license_factory,
    auth_headers,
    plan_factory,
):
    admin = user_factory(
        role="admin",
        password="AdminOfferCheckout123!",
        email=f"admin.offer.checkout.{uuid4().hex[:8]}@example.com",
        name="Offer Admin Checkout",
    )
    admin_headers = auth_headers(admin.email, "AdminOfferCheckout123!")

    advisor, advisor_headers = _create_advisor_with_verified_license(
        user_factory,
        license_factory,
        auth_headers,
    )
    _ = advisor

    trigger_package = plan_factory(
        name="OfferCheckoutTrigger",
        price_cents=11000,
        daily_download_limit=10,
    )
    offer_package_id = _enable_first_purchase_offer(client, admin_headers, trigger_package.id)

    checkout_response = client.post(
        "/api/v1/purchases/checkout",
        headers=advisor_headers,
        json={"package_id": offer_package_id},
    )
    assert checkout_response.status_code == 403, checkout_response.text
    assert checkout_response.json()["detail"] == "Package is not available for this account"


@pytest.mark.integration
def test_purchase_checkout_allows_managed_offer_for_first_eligible_purchase(
    client,
    user_factory,
    license_factory,
    auth_headers,
    plan_factory,
    purchase_factory,
    monkeypatch,
):
    admin = user_factory(
        role="admin",
        password="AdminOfferCheckoutAllow123!",
        email=f"admin.offer.allow.{uuid4().hex[:8]}@example.com",
        name="Offer Admin Checkout Allow",
    )
    admin_headers = auth_headers(admin.email, "AdminOfferCheckoutAllow123!")

    advisor, advisor_headers = _create_advisor_with_verified_license(
        user_factory,
        license_factory,
        auth_headers,
    )

    trigger_package = plan_factory(
        name="OfferCheckoutAllowTrigger",
        price_cents=11000,
        daily_download_limit=10,
    )
    offer_package_id = _enable_first_purchase_offer(client, admin_headers, trigger_package.id)

    purchase_factory(
        user_id=advisor.id,
        package_id=trigger_package.id,
        status="completed",
        credits_total=trigger_package.daily_download_limit,
        stripe_checkout_session_id="cs_offer_checkout_trigger_completed",
    )

    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.create_or_get_stripe_customer",
        lambda db, user: "cus_offer_checkout_allow",
    )
    monkeypatch.setattr(
        "app.services.subscription_service.stripe.checkout.Session.create",
        lambda **kwargs: {
            "id": "cs_offer_checkout_allowed",
            "url": "https://checkout.stripe.test/offer-checkout-allowed",
        },
    )

    checkout_response = client.post(
        "/api/v1/purchases/checkout",
        headers=advisor_headers,
        json={"package_id": offer_package_id},
    )
    assert checkout_response.status_code == 200, checkout_response.text
    assert checkout_response.json()["session_id"] == "cs_offer_checkout_allowed"


@pytest.mark.integration
def test_purchase_checkout_rejects_managed_offer_after_second_completed_purchase(
    client,
    user_factory,
    license_factory,
    auth_headers,
    plan_factory,
    purchase_factory,
):
    admin = user_factory(
        role="admin",
        password="AdminOfferCheckoutReplay123!",
        email=f"admin.offer.replay.{uuid4().hex[:8]}@example.com",
        name="Offer Admin Checkout Replay",
    )
    admin_headers = auth_headers(admin.email, "AdminOfferCheckoutReplay123!")

    advisor, advisor_headers = _create_advisor_with_verified_license(
        user_factory,
        license_factory,
        auth_headers,
    )

    trigger_package = plan_factory(
        name="OfferCheckoutReplayTrigger",
        price_cents=11000,
        daily_download_limit=10,
    )
    offer_package_id = _enable_first_purchase_offer(client, admin_headers, trigger_package.id)

    purchase_factory(
        user_id=advisor.id,
        package_id=trigger_package.id,
        status="completed",
        credits_total=trigger_package.daily_download_limit,
        stripe_checkout_session_id="cs_offer_checkout_replay_trigger",
    )
    purchase_factory(
        user_id=advisor.id,
        package_id=offer_package_id,
        status="completed",
        credits_total=5,
        stripe_checkout_session_id="cs_offer_checkout_replay_addon",
    )

    checkout_response = client.post(
        "/api/v1/purchases/checkout",
        headers=advisor_headers,
        json={"package_id": offer_package_id},
    )
    assert checkout_response.status_code == 403, checkout_response.text
    assert checkout_response.json()["detail"] == "Package is not available for this account"


@pytest.mark.integration
def test_subscription_compat_routes_are_removed(client):
    assert client.get("/api/v1/subscriptions/plans").status_code == 404
    assert client.post("/api/v1/subscriptions/checkout", json={"plan_id": 1}).status_code == 404
    assert client.get("/api/v1/subscriptions/current").status_code == 404
    assert client.post("/api/v1/subscriptions/cancel").status_code == 404
