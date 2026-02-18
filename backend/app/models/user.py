from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import BigInteger, Boolean, ForeignKey, String, Enum as SQLEnum, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.timezone import UTCDateTime, utcnow

from .base import Base

if TYPE_CHECKING:
    from .license import License
    from .purchase import LeadCreditLedger, LeadPurchase
    from .lead import LeadDownload, LeadOutcome, LeadOwnership
    from .delivery_settings import AdvisorDeliverySettings
    from .audit_log import AuditLog
    from .auth_session import RefreshTokenSession

class User(Base):
    """
    User model for advisor and admin accounts.
    
    Attributes:
        id: Primary key (BIGINT)
        name: Full name (max 150 chars)
        email: Unique login email
        password_hash: Hashed password
        phone: Optional phone number
        role: Either 'advisor' or 'admin'
        stripe_customer_id: Links to Stripe customer
        created_at: Auto-set timestamp
    """

    __tablename__ = "users"

    # Primary key
    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    # User details
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Role
    role: Mapped[str] = mapped_column(
        SQLEnum("advisor", "admin", name="user_role_enum"),
        nullable=False,
        default="advisor",
        server_default="advisor",
    )

    # Stripe integration
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(
        String(100), 
        nullable=True, 
        unique=True, 
        index=True
    )

    # Account lifecycle
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("1"),
        index=True,
    )
    deactivated_at: Mapped[Optional[datetime]] = mapped_column(
        UTCDateTime(),
        nullable=True,
        index=True,
    )
    deactivated_by: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("users.id", onupdate="CASCADE", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False, 
        default=utcnow,
        server_default=text("CURRENT_TIMESTAMP")
    )

    # Relationships
    licenses: Mapped[List["License"]] = relationship(
        "License",
        back_populates="user",
        foreign_keys="License.user_id",
        cascade="all, delete-orphan",
    )

    verified_licenses: Mapped[List["License"]] = relationship(
        "License",
        back_populates="verified_by_user",
        foreign_keys="License.verified_by",
    )

    lead_purchases: Mapped[List["LeadPurchase"]] = relationship(
        "LeadPurchase",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    lead_credit_ledger_entries: Mapped[List["LeadCreditLedger"]] = relationship(
        "LeadCreditLedger",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    lead_downloads: Mapped[List["LeadDownload"]] = relationship(
        "LeadDownload",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    lead_ownerships: Mapped[List["LeadOwnership"]] = relationship(
        "LeadOwnership",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    lead_outcomes: Mapped[List["LeadOutcome"]] = relationship(
        "LeadOutcome",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    delivery_settings: Mapped[Optional["AdvisorDeliverySettings"]] = relationship(
        "AdvisorDeliverySettings",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    audit_logs: Mapped[List["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="actor_user",
    )

    refresh_sessions: Mapped[List["RefreshTokenSession"]] = relationship(
        "RefreshTokenSession",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}', role='{self.role}')>"
