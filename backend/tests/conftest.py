from __future__ import annotations

import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Generator
from uuid import uuid4

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


def _install_stripe_stub() -> None:
    """Install a lightweight Stripe stub if the dependency is unavailable."""
    try:
        __import__("stripe")
        return
    except ModuleNotFoundError:
        pass

    stripe = types.ModuleType("stripe")

    class StripeError(Exception):
        pass

    class SignatureVerificationError(StripeError):
        pass

    class _Webhook:
        @staticmethod
        def construct_event(*args, **kwargs):
            raise NotImplementedError("stripe.Webhook.construct_event must be mocked in tests")

    class _CheckoutSession:
        @staticmethod
        def create(*args, **kwargs):
            raise NotImplementedError("stripe.checkout.Session.create must be mocked in tests")

    class _Checkout:
        Session = _CheckoutSession

    class _Customer:
        @staticmethod
        def create(*args, **kwargs):
            raise NotImplementedError("stripe.Customer.create must be mocked in tests")

        @staticmethod
        def retrieve(*args, **kwargs):
            return {}

    class _Subscription:
        @staticmethod
        def retrieve(*args, **kwargs):
            raise NotImplementedError("stripe.Subscription.retrieve must be mocked in tests")

        @staticmethod
        def modify(*args, **kwargs):
            raise NotImplementedError("stripe.Subscription.modify must be mocked in tests")

    class _PaymentMethod:
        @staticmethod
        def retrieve(*args, **kwargs):
            return {}

    class _Invoice:
        @staticmethod
        def list(*args, **kwargs):
            return {"data": []}

    stripe.error = types.SimpleNamespace(
        StripeError=StripeError,
        SignatureVerificationError=SignatureVerificationError,
    )
    stripe.Webhook = _Webhook
    stripe.checkout = _Checkout
    stripe.Customer = _Customer
    stripe.Subscription = _Subscription
    stripe.PaymentMethod = _PaymentMethod
    stripe.Invoice = _Invoice
    stripe.api_key = None
    stripe.api_version = None

    sys.modules["stripe"] = stripe


_install_stripe_stub()

from app.api import deps as deps_module
from app.core.config import settings
from app.core.security import get_password_hash
from app.main import app
from app.models import Base
from app.models.lead import Lead
from app.models.license import License
from app.models.purchase import LeadPackage, LeadPurchase
from app.models.subscription import Subscription, SubscriptionPlan
from app.models.user import User
from app.services import audit_service, subscription_service


_METADATA_PATCHED = False


def _patch_metadata_for_sqlite() -> None:
    """
    Adjust MySQL-specific model metadata for SQLite test execution.
    """
    global _METADATA_PATCHED
    if _METADATA_PATCHED:
        return

    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, sa.BigInteger):
                column.type = sa.Integer()

            if column.server_default is not None:
                default_sql = str(column.server_default.arg)
                if "ON UPDATE CURRENT_TIMESTAMP" in default_sql:
                    column.server_default = sa.DefaultClause(sa.text("CURRENT_TIMESTAMP"))

    _METADATA_PATCHED = True


@pytest.fixture(scope="session")
def engine():
    _patch_metadata_for_sqlite()
    test_engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def session_factory(engine):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture
def db(session_factory) -> Generator[Session, None, None]:
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def test_settings(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "SECRET_KEY", "test-secret-key")
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_local")
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setattr(settings, "FRONTEND_URL", "http://localhost:5173")


@pytest.fixture
def client(
    session_factory,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Generator[TestClient, None, None]:
    monkeypatch.chdir(tmp_path)

    # Align all SessionLocal consumers with the same test session factory.
    monkeypatch.setattr("app.db.session.SessionLocal", session_factory)
    monkeypatch.setattr(deps_module, "SessionLocal", session_factory)
    monkeypatch.setattr(audit_service, "SessionLocal", session_factory)
    monkeypatch.setattr(subscription_service, "SessionLocal", session_factory)

    def override_get_db():
        test_db = session_factory()
        try:
            yield test_db
        finally:
            test_db.close()

    app.dependency_overrides[deps_module.get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def user_factory(db: Session) -> Callable[..., User]:
    def _create_user(
        *,
        role: str = "advisor",
        password: str = "StrongPass123!",
        email: str | None = None,
        name: str = "Test User",
    ) -> User:
        user = User(
            email=email or f"{uuid4().hex}@example.com",
            name=name,
            phone="555-0100",
            password_hash=get_password_hash(password),
            role=role,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    return _create_user


@pytest.fixture
def plan_factory(db: Session) -> Callable[..., SubscriptionPlan]:
    def _create_plan(
        *,
        name: str = "Starter",
        price_cents: int = 20000,
        state_limit: int | None = 1,
        daily_download_limit: int = 50,
        stripe_price_id: str | None = None,
    ) -> SubscriptionPlan:
        plan = SubscriptionPlan(
            name=f"{name}-{uuid4().hex[:6]}",
            price_cents=price_cents,
            currency="USD",
            state_limit=state_limit,
            daily_download_limit=daily_download_limit,
            features=["one", "two"],
            stripe_price_id=stripe_price_id or f"price_{uuid4().hex[:10]}",
        )
        db.add(plan)
        db.commit()
        db.refresh(plan)

        package = LeadPackage(
            id=plan.id,
            name=plan.name,
            price_cents=plan.price_cents,
            currency=plan.currency,
            stripe_price_id=plan.stripe_price_id,
            state_limit=plan.state_limit,
            daily_download_limit=plan.daily_download_limit,
            features=plan.features,
            created_at=plan.created_at,
        )
        db.add(package)
        db.commit()

        return plan

    return _create_plan


@pytest.fixture
def license_factory(db: Session) -> Callable[..., License]:
    def _create_license(
        *,
        user_id: int,
        state: str = "CA",
        status: str = "verified",
        license_number: str | None = None,
    ) -> License:
        license_row = License(
            user_id=user_id,
            state=state,
            license_number=license_number or f"{state}-{uuid4().hex[:8]}",
            license_type="Series 65",
            document_path="uploads/licenses/test.pdf",
            verification_status=status,
            verified_at=datetime.now(timezone.utc) if status == "verified" else None,
        )
        db.add(license_row)
        db.commit()
        db.refresh(license_row)
        return license_row

    return _create_license


@pytest.fixture
def subscription_factory(db: Session) -> Callable[..., Subscription]:
    def _create_subscription(
        *,
        user_id: int,
        plan_id: int,
        status: str = "active",
        period_end_days: int = 30,
        stripe_subscription_id: str | None = None,
    ) -> Subscription:
        now = datetime.now(timezone.utc)
        subscription_row = Subscription(
            user_id=user_id,
            plan_id=plan_id,
            stripe_subscription_id=stripe_subscription_id or f"sub_{uuid4().hex[:12]}",
            status=status,
            current_period_start=now - timedelta(days=1),
            current_period_end=now + timedelta(days=period_end_days),
        )
        db.add(subscription_row)
        db.commit()
        db.refresh(subscription_row)
        return subscription_row

    return _create_subscription


@pytest.fixture
def purchase_factory(db: Session) -> Callable[..., LeadPurchase]:
    def _create_purchase(
        *,
        user_id: int,
        package_id: int,
        credits_total: int = 10,
        credits_remaining: int | None = None,
        status: str = "completed",
        stripe_checkout_session_id: str | None = None,
        stripe_payment_intent_id: str | None = None,
    ) -> LeadPurchase:
        purchase = LeadPurchase(
            user_id=user_id,
            package_id=package_id,
            stripe_checkout_session_id=stripe_checkout_session_id or f"cs_{uuid4().hex[:12]}",
            stripe_payment_intent_id=stripe_payment_intent_id,
            amount_cents=10000,
            currency="USD",
            credits_total=credits_total,
            credits_remaining=credits_total if credits_remaining is None else credits_remaining,
            status=status,
            purchased_at=datetime.now(timezone.utc),
        )
        db.add(purchase)
        db.commit()
        db.refresh(purchase)
        return purchase

    return _create_purchase


@pytest.fixture
def lead_factory(db: Session) -> Callable[..., Lead]:
    def _create_lead(
        *,
        state_code: str = "CA",
        mobile_phone: str | None = None,
        first_name: str = "Alex",
        last_name: str = "Lead",
    ) -> Lead:
        lead = Lead(
            state_code=state_code,
            mobile_phone=mobile_phone or f"555-{uuid4().hex[:8]}",
            first_name=first_name,
            last_name=last_name,
            source="manual_entry",
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)
        return lead

    return _create_lead


@pytest.fixture
def auth_headers(client: TestClient) -> Callable[[str, str], dict[str, str]]:
    def _headers(email: str, password: str) -> dict[str, str]:
        response = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert response.status_code == 204, response.text

        access_cookie = response.cookies.get(settings.AUTH_ACCESS_COOKIE_NAME)
        refresh_cookie = response.cookies.get(settings.AUTH_REFRESH_COOKIE_NAME)
        csrf_cookie = response.cookies.get(settings.AUTH_CSRF_COOKIE_NAME)
        assert access_cookie
        assert refresh_cookie
        assert csrf_cookie

        cookie_header = (
            f"{settings.AUTH_ACCESS_COOKIE_NAME}={access_cookie}; "
            f"{settings.AUTH_REFRESH_COOKIE_NAME}={refresh_cookie}; "
            f"{settings.AUTH_CSRF_COOKIE_NAME}={csrf_cookie}"
        )
        return {
            "Cookie": cookie_header,
            settings.AUTH_CSRF_HEADER_NAME: csrf_cookie,
        }

    return _headers
