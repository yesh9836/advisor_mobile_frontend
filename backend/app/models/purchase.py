from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    BigInteger,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.timezone import UTCDateTime, utcnow

from .base import Base

if TYPE_CHECKING:
    from .lead import LeadDownload
    from .subscription import SubscriptionPlan
    from .user import User


class LeadPurchase(Base):
    """Immutable record of a one-time package purchase."""

    __tablename__ = "lead_purchases"

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
        ForeignKey("subscription_plans.id", onupdate="CASCADE", ondelete="RESTRICT"),
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
    package: Mapped["SubscriptionPlan"] = relationship("SubscriptionPlan", back_populates="lead_purchases")
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
            "admin_adjustment",
            name="lead_credit_movement_type_enum",
        ),
        nullable=False,
        index=True,
    )
    credits_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utcnow,
        server_default=text("CURRENT_TIMESTAMP"),
        index=True,
    )

    user: Mapped["User"] = relationship("User", back_populates="lead_credit_ledger_entries")
    purchase: Mapped[Optional["LeadPurchase"]] = relationship("LeadPurchase", back_populates="credit_ledger_entries")
