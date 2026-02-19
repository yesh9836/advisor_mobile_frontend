from uuid import uuid4

import pytest

from app.models.lead import LeadOwnership


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
        json={"package_id": plan.id},
    )
    assert response.status_code == 200, response.text
    assert response.json()["session_id"] == "cs_purchase_checkout"
    assert captured_checkout_kwargs["mode"] == "payment"
    assert captured_checkout_kwargs["metadata"] == {
        "user_id": str(advisor.id),
        "package_id": str(plan.id),
    }
    assert captured_checkout_kwargs["payment_intent_data"]["metadata"] == {
        "user_id": str(advisor.id),
        "package_id": str(plan.id),
    }
    assert captured_checkout_kwargs["idempotency_key"].startswith(
        f"checkout-create:{advisor.id}:{plan.id}:"
    )


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
    assert all("credits_remaining" in item for item in orders_payload["items"])
    assert all("assigned_count" in item for item in orders_payload["items"])
    assert all("unfulfilled_count" in item for item in orders_payload["items"])
    assert all("fulfillment_status" in item for item in orders_payload["items"])
    orders_by_id = {item["id"]: item for item in orders_payload["items"]}
    assert orders_by_id[completed_purchase.id]["assigned_count"] == 2
    assert orders_by_id[completed_purchase.id]["unfulfilled_count"] == 8
    assert orders_by_id[completed_purchase.id]["fulfillment_status"] == "partially_fulfilled"
    assert orders_by_id[pending_purchase.id]["assigned_count"] == 0
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
    assert all("unfulfilled_count" in item for item in history_payload["items"])
    assert all("fulfillment_status" in item for item in history_payload["items"])


@pytest.mark.integration
def test_subscription_compat_routes_are_removed(client):
    assert client.get("/api/v1/subscriptions/plans").status_code == 404
    assert client.post("/api/v1/subscriptions/checkout", json={"plan_id": 1}).status_code == 404
    assert client.get("/api/v1/subscriptions/current").status_code == 404
    assert client.post("/api/v1/subscriptions/cancel").status_code == 404
