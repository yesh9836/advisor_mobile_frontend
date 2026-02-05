from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import (
    BigInteger,
    String,
    Integer,
    JSON,
    Enum as SQLEnum,
    DateTime,
    ForeignKey,
    text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .user import User


class SubscriptionPlan(Base):
    """
    Subscription plan/tier definition.
    
    Attributes:
        id: Primary key
        name: Plan name (unique)
        price_cents: Price in cents (e.g., 120000 = $1,200.00)
        currency: 3-letter currency code (default USD)
        state_limit: Max states allowed (NULL = unlimited)
        daily_download_limit: Max leads per day
        features: JSON array of features
        created_at: Auto-set timestamp
    """

    __tablename__ = "subscription_plans"

    # Primary key
    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    # Plan details
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD", server_default=text("'USD'"))

    stripe_price_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)

    # Limits
    state_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    daily_download_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))

    # Features (JSON array)
    features: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now(timezone.utc), server_default=text("CURRENT_TIMESTAMP")
    )

    # Relationships
    subscriptions: Mapped[List["Subscription"]] = relationship(
        "Subscription",
        back_populates="plan",
    )

    def __repr__(self) -> str:
        return f"<SubscriptionPlan(id={self.id}, name='{self.name}', price_cents={self.price_cents})>"


class Subscription(Base):
    """
    User subscription record.
    
    Attributes:
        id: Primary key
        user_id: Foreign key to users table
        plan_id: Foreign key to subscription_plans table
        stripe_subscription_id: Stripe's subscription ID (unique)
        status: Subscription status (8 possible values)
        current_period_start: Billing period start
        current_period_end: Billing period end
        created_at: Auto-set timestamp
    """

    __tablename__ = "subscriptions"

    # Primary key
    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    # Foreign keys
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    plan_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("subscription_plans.id", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Stripe integration
    stripe_subscription_id: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, index=True
    )

    # Status (8 possible Stripe states)
    status: Mapped[str] = mapped_column(
        SQLEnum(
            "trialing",
            "active",
            "past_due",
            "canceled",
            "unpaid",
            "incomplete",
            "incomplete_expired",
            "paused",
            name="subscription_status_enum",
        ),
        nullable=False,
        default="active",
        server_default=text("'active'"),
    )

    # Billing period
    current_period_start: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    current_period_end: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now(timezone.utc), server_default=text("CURRENT_TIMESTAMP")
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="subscriptions")
    plan: Mapped["SubscriptionPlan"] = relationship("SubscriptionPlan", back_populates="subscriptions")

    def __repr__(self) -> str:
        return f"<Subscription(id={self.id}, user_id={self.user_id}, status='{self.status}')>"