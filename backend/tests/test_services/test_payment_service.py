import pytest
import stripe
from fastapi import HTTPException

from app.services.payment_service import PaymentService


@pytest.fixture(autouse=True)
def reset_payment_service_state():
    PaymentService._initialized = False
    yield
    PaymentService._initialized = False


@pytest.mark.unit
def test_create_or_get_customer_returns_existing_id_without_stripe_call(db, user_factory):
    user = user_factory(
        role="advisor",
        password="PaymentExisting123!",
        email="payment.existing@example.com",
    )
    user.stripe_customer_id = "cus_existing_123"
    db.add(user)
    db.commit()
    db.refresh(user)

    customer_id = PaymentService.create_or_get_stripe_customer(db=db, user=user)
    assert customer_id == "cus_existing_123"


@pytest.mark.unit
def test_init_stripe_raises_when_secret_missing(monkeypatch):
    monkeypatch.setattr("app.services.payment_service.settings.STRIPE_SECRET_KEY", "")

    with pytest.raises(HTTPException) as exc_info:
        PaymentService._init_stripe()

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Stripe configuration error"


@pytest.mark.unit
def test_create_customer_persists_stripe_customer_id(db, user_factory, monkeypatch):
    user = user_factory(
        role="advisor",
        password="PaymentCreate123!",
        email="payment.create@example.com",
    )

    monkeypatch.setattr("app.services.payment_service.settings.STRIPE_SECRET_KEY", "sk_test_123")
    captured_create_kwargs = {}

    def _mock_customer_create(**kwargs):
        captured_create_kwargs.update(kwargs)
        return {"id": "cus_created_123"}

    monkeypatch.setattr(
        "app.services.payment_service.stripe.Customer.create",
        _mock_customer_create,
    )

    customer_id = PaymentService.create_or_get_stripe_customer(db=db, user=user)
    assert customer_id == "cus_created_123"
    db.refresh(user)
    assert user.stripe_customer_id == "cus_created_123"
    assert captured_create_kwargs["idempotency_key"] == f"customer-create:{user.id}:v1"


@pytest.mark.unit
def test_init_stripe_applies_timeout_and_network_retry_policy(monkeypatch):
    monkeypatch.setattr("app.services.payment_service.settings.STRIPE_SECRET_KEY", "sk_test_123")
    monkeypatch.setattr("app.services.payment_service.settings.STRIPE_API_VERSION", "2023-10-16")
    monkeypatch.setattr("app.services.payment_service.settings.STRIPE_REQUEST_TIMEOUT_SECONDS", 12.5)
    monkeypatch.setattr("app.services.payment_service.settings.STRIPE_MAX_NETWORK_RETRIES", 4)

    captured = {}

    class _FakeRequestsClient:
        def __init__(self, timeout):
            captured["timeout"] = timeout

    monkeypatch.setattr(
        PaymentService,
        "_stripe_http_client_candidates",
        staticmethod(lambda: [("RequestsClient", _FakeRequestsClient)]),
    )

    PaymentService._init_stripe()

    assert captured["timeout"] == 12.5
    assert PaymentService._initialized is True
    assert stripe.max_network_retries == 4
    assert isinstance(stripe.default_http_client, _FakeRequestsClient)


@pytest.mark.unit
def test_checkout_session_idempotency_key_is_stable_for_same_retry_token():
    first = PaymentService.checkout_session_idempotency_key(
        user_id=42,
        package_id=11,
        retry_token="retry_checkout_pkg11_attempt1",
    )
    second = PaymentService.checkout_session_idempotency_key(
        user_id=42,
        package_id=11,
        retry_token="retry_checkout_pkg11_attempt1",
    )

    assert first == second
    assert first.startswith("checkout-create:42:11:")
    assert first.endswith(":v2")


@pytest.mark.unit
def test_checkout_session_idempotency_key_changes_for_distinct_retry_tokens():
    first = PaymentService.checkout_session_idempotency_key(
        user_id=42,
        package_id=11,
        retry_token="retry_checkout_pkg11_attempt1",
    )
    second = PaymentService.checkout_session_idempotency_key(
        user_id=42,
        package_id=11,
        retry_token="retry_checkout_pkg11_attempt2",
    )

    assert first != second


@pytest.mark.unit
def test_checkout_session_idempotency_key_defaults_to_new_intent_without_retry_token():
    first = PaymentService.checkout_session_idempotency_key(
        user_id=42,
        package_id=11,
        retry_token=None,
    )
    second = PaymentService.checkout_session_idempotency_key(
        user_id=42,
        package_id=11,
        retry_token=None,
    )

    assert first != second


@pytest.mark.unit
def test_checkout_session_idempotency_key_rejects_invalid_retry_token():
    with pytest.raises(HTTPException) as exc_info:
        PaymentService.checkout_session_idempotency_key(
            user_id=42,
            package_id=11,
            retry_token="bad token with spaces",
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Invalid checkout retry token"


@pytest.mark.unit
def test_deactivate_stripe_plan_artifacts_deactivates_price_and_product(monkeypatch):
    monkeypatch.setattr("app.services.payment_service.settings.STRIPE_SECRET_KEY", "sk_test_123")
    captured = {}

    def _mock_price_modify(price_id, **kwargs):
        captured["price_id"] = price_id
        captured["price_kwargs"] = kwargs
        return {"id": price_id, "active": kwargs.get("active", True)}

    def _mock_product_modify(product_id, **kwargs):
        captured["product_id"] = product_id
        captured["product_kwargs"] = kwargs
        return {"id": product_id, "active": kwargs.get("active", True)}

    monkeypatch.setattr("app.services.payment_service.stripe.Price.modify", _mock_price_modify)
    monkeypatch.setattr("app.services.payment_service.stripe.Product.modify", _mock_product_modify)

    result = PaymentService.deactivate_stripe_plan_artifacts(
        stripe_price_id="price_cleanup_123",
        stripe_product_id="prod_cleanup_123",
    )
    assert result == {"price_deactivated": True, "product_deactivated": True}
    assert captured["price_id"] == "price_cleanup_123"
    assert captured["price_kwargs"] == {"active": False}
    assert captured["product_id"] == "prod_cleanup_123"
    assert captured["product_kwargs"] == {"active": False}


@pytest.mark.unit
def test_deactivate_stripe_plan_artifacts_raises_runtime_error_on_stripe_failure(monkeypatch):
    monkeypatch.setattr("app.services.payment_service.settings.STRIPE_SECRET_KEY", "sk_test_123")
    monkeypatch.setattr(
        "app.services.payment_service.stripe.Price.modify",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(stripe.error.StripeError("rate limited")),
    )

    with pytest.raises(RuntimeError) as exc_info:
        PaymentService.deactivate_stripe_plan_artifacts(
            stripe_price_id="price_cleanup_fail",
            stripe_product_id=None,
        )
    assert "price:price_cleanup_fail" in str(exc_info.value)


@pytest.mark.unit
def test_activate_stripe_plan_artifacts_activates_price_and_product(monkeypatch):
    monkeypatch.setattr("app.services.payment_service.settings.STRIPE_SECRET_KEY", "sk_test_123")
    captured = {}

    def _mock_price_modify(price_id, **kwargs):
        captured["price_id"] = price_id
        captured["price_kwargs"] = kwargs
        return {"id": price_id, "active": kwargs.get("active", False)}

    def _mock_product_modify(product_id, **kwargs):
        captured["product_id"] = product_id
        captured["product_kwargs"] = kwargs
        return {"id": product_id, "active": kwargs.get("active", False)}

    monkeypatch.setattr("app.services.payment_service.stripe.Price.modify", _mock_price_modify)
    monkeypatch.setattr("app.services.payment_service.stripe.Product.modify", _mock_product_modify)

    result = PaymentService.activate_stripe_plan_artifacts(
        stripe_price_id="price_activate_123",
        stripe_product_id="prod_activate_123",
    )
    assert result == {"price_activated": True, "product_activated": True}
    assert captured["price_id"] == "price_activate_123"
    assert captured["price_kwargs"] == {"active": True}
    assert captured["product_id"] == "prod_activate_123"
    assert captured["product_kwargs"] == {"active": True}


@pytest.mark.unit
def test_activate_stripe_plan_artifacts_raises_runtime_error_when_price_missing(monkeypatch):
    monkeypatch.setattr("app.services.payment_service.settings.STRIPE_SECRET_KEY", "sk_test_123")
    monkeypatch.setattr(
        "app.services.payment_service.stripe.Price.modify",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            stripe.error.InvalidRequestError(
                message="No such price: 'price_missing'",
                param="id",
            )
        ),
    )

    with pytest.raises(RuntimeError) as exc_info:
        PaymentService.activate_stripe_plan_artifacts(
            stripe_price_id="price_missing",
            stripe_product_id=None,
        )

    assert "price:price_missing" in str(exc_info.value)
