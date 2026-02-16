from datetime import datetime, timezone
from uuid import uuid4

import pytest


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
def test_purchase_packages_and_subscription_plans_wrapper_match(client, plan_factory):
    plan_factory(name="PackageA", price_cents=10000, stripe_price_id="price_package_a")
    plan_factory(name="PackageB", price_cents=20000, stripe_price_id="price_package_b")

    purchases_response = client.get("/api/v1/purchases/packages")
    plans_wrapper_response = client.get("/api/v1/subscriptions/plans")

    assert purchases_response.status_code == 200, purchases_response.text
    assert plans_wrapper_response.status_code == 200, plans_wrapper_response.text

    purchase_payload = purchases_response.json()
    wrapper_payload = plans_wrapper_response.json()
    assert [item["id"] for item in purchase_payload] == [item["id"] for item in wrapper_payload]
    assert [item["price_cents"] for item in purchase_payload] == [item["price_cents"] for item in wrapper_payload]


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


@pytest.mark.integration
def test_subscription_current_and_cancel_expose_deprecation_headers(
    client,
    user_factory,
    plan_factory,
    subscription_factory,
    auth_headers,
    monkeypatch,
):
    unique_key = uuid4().hex[:10]
    advisor = user_factory(
        role="advisor",
        password="AdvisorPurchaseDeprecated123!",
        email=f"advisor.purchase.deprecated.{unique_key}@example.com",
        name="Advisor Purchase Deprecated",
    )
    plan = plan_factory(stripe_price_id="price_purchase_deprecated")
    subscription_factory(
        user_id=advisor.id,
        plan_id=plan.id,
        status="active",
        stripe_subscription_id="sub_purchase_deprecated",
    )
    headers = auth_headers(advisor.email, "AdvisorPurchaseDeprecated123!")

    current_response = client.get("/api/v1/subscriptions/current", headers=headers)
    assert current_response.status_code == 200, current_response.text
    assert current_response.headers.get("Deprecation") == "true"
    assert current_response.headers.get("X-Deprecated-Endpoint") == "/subscriptions/current"

    monkeypatch.setattr(
        "app.services.subscription_service.stripe.Subscription.modify",
        lambda subscription_id, cancel_at_period_end=True: {
            "id": subscription_id,
            "status": "active",
            "current_period_end": int(datetime.now(timezone.utc).timestamp()),
        },
    )
    cancel_response = client.post("/api/v1/subscriptions/cancel", headers=headers)
    assert cancel_response.status_code == 200, cancel_response.text
    assert cancel_response.headers.get("Deprecation") == "true"
    assert cancel_response.headers.get("X-Deprecated-Endpoint") == "/subscriptions/cancel"


@pytest.mark.integration
def test_subscription_current_and_cancel_return_410_when_compat_disabled(
    client,
    user_factory,
    plan_factory,
    subscription_factory,
    auth_headers,
    monkeypatch,
):
    unique_key = uuid4().hex[:10]
    advisor = user_factory(
        role="advisor",
        password="AdvisorPurchaseCompatOff123!",
        email=f"advisor.purchase.compatoff.{unique_key}@example.com",
        name="Advisor Purchase Compat Off",
    )
    plan = plan_factory(stripe_price_id="price_purchase_compat_disabled")
    subscription_factory(
        user_id=advisor.id,
        plan_id=plan.id,
        status="active",
        stripe_subscription_id="sub_purchase_compat_disabled",
    )
    headers = auth_headers(advisor.email, "AdvisorPurchaseCompatOff123!")
    monkeypatch.setattr("app.api.v1.subscriptions.settings.SUBSCRIPTION_COMPAT_ENDPOINTS_ENABLED", False)

    current_response = client.get("/api/v1/subscriptions/current", headers=headers)
    assert current_response.status_code == 410
    assert current_response.json()["detail"] == (
        "/subscriptions/current has been sunset. Use /purchases endpoints instead."
    )

    cancel_response = client.post("/api/v1/subscriptions/cancel", headers=headers)
    assert cancel_response.status_code == 410
    assert cancel_response.json()["detail"] == (
        "/subscriptions/cancel has been sunset. Use /purchases endpoints instead."
    )
