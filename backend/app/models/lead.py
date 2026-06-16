from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    BigInteger,
    Enum as SQLEnum,
    ForeignKey,
    JSON,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.timezone import UTCDateTime, utcnow

from .base import Base

if TYPE_CHECKING:
    from .purchase import LeadPurchase
    from .user import User


class Lead(Base):
    """
    Retirement planning lead with 25+ survey fields.
    
    No email field - phone only for privacy.
    
    Attributes:
        id: Primary key
        source: wordpress_import, manual_entry, api_submission
        
        Location fields:
        state_code: Two-letter state code (required)
        zip_code: ZIP code
        
        Contact fields:
        first_name, last_name, mobile_phone
        preferred_follow_up_method, best_time_to_reach
        
        Retirement fields:
        retirement_timeline, confidence_in_long_term_plan,
        most_important_retirement_activity, planning_to_relocate_retirement,
        expected_retirement_income_source
        
        Personal/risk fields:
        overall_health, money_management_style, investor_profile_statement,
        investment_comfort_level, main_purpose_for_investing (JSON)
        
        Financial fields (ranges):
        retirement_savings_range, annual_household_income_range,
        total_investable_assets_range, monthly_savings_range,
        wants_to_improve_strategy_timing
        
        Current strategies:
        current_investment_strategies (JSON), has_financial_advisor,
        advisor_local_preference, owns_annuity
        
        Free text:
        additional_notes
    """

    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)

    state_code: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    zip_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    first_name: Mapped[Optional[str]] = mapped_column(String(80), nullable=True, index=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(80), nullable=True, index=True)
    mobile_phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    preferred_follow_up_method: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    best_time_to_reach: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    retirement_timeline: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    confidence_in_long_term_plan: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    most_important_retirement_activity: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    planning_to_relocate_retirement: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    expected_retirement_income_source: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    overall_health: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    money_management_style: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    investor_profile_statement: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    investment_comfort_level: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    main_purpose_for_investing: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    retirement_savings_range: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    annual_household_income_range: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    total_investable_assets_range: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    monthly_savings_range: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    wants_to_improve_strategy_timing: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)

    current_investment_strategies: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    has_financial_advisor: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    advisor_local_preference: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    owns_annuity: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    additional_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

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
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )

    downloads: Mapped[list["LeadDownload"]] = relationship(
        "LeadDownload",
        back_populates="lead",
        cascade="all, delete-orphan",
    )
    ownerships: Mapped[list["LeadOwnership"]] = relationship(
        "LeadOwnership",
        back_populates="lead",
        cascade="all, delete-orphan",
    )

    outcomes: Mapped[list["LeadOutcome"]] = relationship(
        "LeadOutcome",
        back_populates="lead",
        cascade="all, delete-orphan",
    )
    intake_events: Mapped[list["LeadIntakeWebhookEvent"]] = relationship(
        "LeadIntakeWebhookEvent",
        back_populates="lead",
        cascade="all, delete-orphan",
    )


    def __repr__(self) -> str:
        return f"<Lead(id={self.id}, state='{self.state_code}', name='{self.first_name} {self.last_name}')>"


class LeadIntakeWebhookEvent(Base):
    """
    Idempotency registry for public lead intake webhooks.

    Prevents duplicate lead inserts when providers retry webhook deliveries.
    """

    __tablename__ = "lead_intake_webhook_events"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "external_entry_id",
            name="uq_lead_intake_webhook_events_provider_entry",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    provider: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    external_entry_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    payload_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    lead_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("leads.id", onupdate="CASCADE", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utcnow,
        server_default=text("CURRENT_TIMESTAMP"),
        index=True,
    )

    lead: Mapped[Optional["Lead"]] = relationship("Lead", back_populates="intake_events")

    def __repr__(self) -> str:
        return (
            f"<LeadIntakeWebhookEvent(id={self.id}, provider='{self.provider}', "
            f"external_entry_id='{self.external_entry_id}', lead_id={self.lead_id})>"
        )


class LeadDownload(Base):
    """
    Append-only export audit rows for advisor lead downloads.
    
    Attributes:
        id: Primary key
        user_id: Which advisor downloaded
        lead_id: Which lead was downloaded
        downloaded_at: When (for daily limit checking)
        csv_batch_id: Groups downloads together (same CSV export)
    """

    __tablename__ = "lead_downloads"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    lead_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("leads.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    purchase_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("lead_purchases.id", onupdate="CASCADE", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    downloaded_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utcnow,
        server_default=text("CURRENT_TIMESTAMP"),
        index=True,
    )

    csv_batch_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    user: Mapped["User"] = relationship("User", back_populates="lead_downloads")
    lead: Mapped["Lead"] = relationship("Lead", back_populates="downloads")
    purchase: Mapped[Optional["LeadPurchase"]] = relationship("LeadPurchase", back_populates="funded_downloads")

    def __repr__(self) -> str:
        return f"<LeadDownload(id={self.id}, user_id={self.user_id}, lead_id={self.lead_id}, batch='{self.csv_batch_id}')>"


class LeadOwnership(Base):
    """
    Immutable ownership record for purchased lead assignments.
    One lead can only be owned by one advisor globally.
    """

    __tablename__ = "lead_ownerships"
    __table_args__ = (
        UniqueConstraint("user_id", "lead_id", name="uq_lead_ownerships_user_lead"),
        UniqueConstraint("lead_id", name="uq_lead_ownerships_global_lead"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    lead_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("leads.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    purchase_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("lead_purchases.id", onupdate="CASCADE", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    assigned_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utcnow,
        server_default=text("CURRENT_TIMESTAMP"),
        index=True,
    )

    user: Mapped["User"] = relationship("User", back_populates="lead_ownerships")
    lead: Mapped["Lead"] = relationship("Lead", back_populates="ownerships")
    purchase: Mapped[Optional["LeadPurchase"]] = relationship("LeadPurchase")

    def __repr__(self) -> str:
        return (
            f"<LeadOwnership(id={self.id}, user_id={self.user_id}, "
            f"lead_id={self.lead_id}, purchase_id={self.purchase_id})>"
        )


class LeadOutcome(Base):
    """
    Advisor-specific lead outcome tracking (status + notes).
    One row per (user_id, lead_id).
    """

    __tablename__ = "lead_outcomes"
    __table_args__ = (
        UniqueConstraint("user_id", "lead_id", name="uq_lead_outcomes_user_lead"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    lead_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("leads.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        SQLEnum(
            "new",
            "contacted",
            "appointment_set",
            "closed_deal",
            name="lead_outcome_status_enum",
        ),
        nullable=False,
        default="new",
        server_default=text("'new'"),
        index=True,
    )

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

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
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )

    user: Mapped["User"] = relationship("User", back_populates="lead_outcomes")
    lead: Mapped["Lead"] = relationship("Lead", back_populates="outcomes")

    def __repr__(self) -> str:
        return f"<LeadOutcome(id={self.id}, user_id={self.user_id}, lead_id={self.lead_id}, status='{self.status}')>"
