import pytest
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
