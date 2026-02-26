from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.timezone import UTCDateTime, utcnow

from .base import Base

if TYPE_CHECKING:
    from .lead import LeadDownload
    from .user import User


class LeadPackage(Base):
    """Catalog entry for one-time lead packages."""

    __tablename__ = "lead_packages"
    __table_args__ = (
        CheckConstraint("currency = 'USD'", name="ck_lead_packages_currency_usd"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="USD",
        server_default=text("'USD'"),
    )
    stripe_price_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    state_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    daily_download_limit: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    features: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utcnow,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    purchases: Mapped[List["LeadPurchase"]] = relationship(
        "LeadPurchase",
        back_populates="package",
    )


class LeadPurchase(Base):
    """Immutable record of a one-time package purchase."""

    __tablename__ = "lead_purchases"
    __table_args__ = (
        CheckConstraint("currency = 'USD'", name="ck_lead_purchases_currency_usd"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    package_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("lead_packages.id", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    stripe_checkout_session_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
    )
    stripe_payment_intent_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        unique=True,
        index=True,
    )
    stripe_invoice_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        unique=True,
        index=True,
    )

    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="USD",
        server_default=text("'USD'"),
    )

    credits_total: Mapped[int] = mapped_column(Integer, nullable=False)
    credits_remaining: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[str] = mapped_column(
        SQLEnum(
            "pending",
            "completed",
            "failed",
            "refunded",
            "canceled",
            name="lead_purchase_status_enum",
        ),
        nullable=False,
        default="completed",
        server_default=text("'completed'"),
        index=True,
    )

    purchased_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utcnow,
        server_default=text("CURRENT_TIMESTAMP"),
        index=True,
    )

    user: Mapped["User"] = relationship("User", back_populates="lead_purchases")
    package: Mapped["LeadPackage"] = relationship("LeadPackage", back_populates="purchases")
    credit_ledger_entries: Mapped[List["LeadCreditLedger"]] = relationship(
        "LeadCreditLedger",
        back_populates="purchase",
    )
    funded_downloads: Mapped[List["LeadDownload"]] = relationship(
        "LeadDownload",
        back_populates="purchase",
    )


class LeadCreditLedger(Base):
    """Immutable journal of advisor credit movements."""

    __tablename__ = "lead_credit_ledger"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    purchase_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("lead_purchases.id", onupdate="CASCADE", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    movement_type: Mapped[str] = mapped_column(
        SQLEnum(
            "purchase_grant",
            "lead_consumed",
            "refund_adjustment",
            "replacement_credit",
            "admin_adjustment",
            name="lead_credit_movement_type_enum",
        ),
        nullable=False,
        index=True,
    )
    credits_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(
        String(191),
        nullable=True,
        unique=True,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utcnow,
        server_default=text("CURRENT_TIMESTAMP"),
        index=True,
    )

    user: Mapped["User"] = relationship("User", back_populates="lead_credit_ledger_entries")
    purchase: Mapped[Optional["LeadPurchase"]] = relationship("LeadPurchase", back_populates="credit_ledger_entries")


class ProcessedStripeEvent(Base):
    """Durable dedupe record for Stripe webhook event IDs."""

    __tablename__ = "processed_stripe_events"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    stripe_event_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        index=True,
    )
    processed_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utcnow,
        server_default=text("CURRENT_TIMESTAMP"),
        index=True,
    )


class StripePoisonEvent(Base):
    """Durable record for non-retryable Stripe webhook events."""

    __tablename__ = "stripe_poison_events"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    stripe_event_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        unique=True,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        index=True,
    )
    reason: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        index=True,
    )
    detail: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    payload_excerpt: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utcnow,
        server_default=text("CURRENT_TIMESTAMP"),
        index=True,
    )


class StripeWebhookInbox(Base):
    """Durable inbox queue for Stripe webhook events."""

    __tablename__ = "stripe_webhook_inbox"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    stripe_event_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        index=True,
    )
    payload: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        SQLEnum(
            "pending",
            "processing",
            "processed",
            "failed",
            name="stripe_webhook_inbox_status_enum",
        ),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
        index=True,
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=10,
        server_default=text("10"),
    )
    next_retry_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utcnow,
        server_default=text("CURRENT_TIMESTAMP"),
        index=True,
    )
    locked_at: Mapped[Optional[datetime]] = mapped_column(
        UTCDateTime(),
        nullable=True,
        index=True,
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        UTCDateTime(),
        nullable=True,
        index=True,
    )
    last_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utcnow,
        server_default=text("CURRENT_TIMESTAMP"),
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )


class StripeWebhookWorkerHeartbeat(Base):
    """Worker heartbeat state for Stripe webhook inbox processing."""

    __tablename__ = "stripe_webhook_worker_heartbeats"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    source: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        unique=True,
        index=True,
    )
    last_started_at: Mapped[Optional[datetime]] = mapped_column(
        UTCDateTime(),
        nullable=True,
        index=True,
    )
    last_completed_at: Mapped[Optional[datetime]] = mapped_column(
        UTCDateTime(),
        nullable=True,
        index=True,
    )
    last_success_at: Mapped[Optional[datetime]] = mapped_column(
        UTCDateTime(),
        nullable=True,
        index=True,
    )
    last_summary: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
    )
    last_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utcnow,
        server_default=text("CURRENT_TIMESTAMP"),
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )


class StripeReconciliationCheckpoint(Base):
    """Durable checkpoint for Stripe reconciliation backfill scans."""

    __tablename__ = "stripe_reconciliation_checkpoints"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    source: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        unique=True,
        index=True,
    )
    last_event_created: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        index=True,
    )
    last_event_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utcnow,
        server_default=text("CURRENT_TIMESTAMP"),
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )


class FirstPurchaseAddonOffer(Base):
    """Singleton-style config for first completed purchase upsell behavior."""

    __tablename__ = "first_purchase_addon_offers"
    __table_args__ = (
        CheckConstraint("offer_currency = 'USD'", name="ck_first_purchase_addon_offers_offer_currency_usd"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
        index=True,
    )
    trigger_package_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("lead_packages.id", onupdate="CASCADE", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    offer_package_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("lead_packages.id", onupdate="CASCADE", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    offer_credits_total: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    offer_price_cents: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    offer_currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="USD",
        server_default=text("'USD'"),
    )
    headline: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cta_label: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    starts_at: Mapped[Optional[datetime]] = mapped_column(
        UTCDateTime(),
        nullable=True,
        index=True,
    )
    ends_at: Mapped[Optional[datetime]] = mapped_column(
        UTCDateTime(),
        nullable=True,
        index=True,
    )
    updated_by: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("users.id", onupdate="CASCADE", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utcnow,
        server_default=text("CURRENT_TIMESTAMP"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=text("CURRENT_TIMESTAMP"),
    )
