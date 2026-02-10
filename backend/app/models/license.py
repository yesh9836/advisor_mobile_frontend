from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, String, Enum as SQLEnum, DateTime, ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .license_resubmission import LicenseResubmission
    from .user import User


class License(Base):
    """
    State license for financial advisors.
    
    Attributes:
        id: Primary key
        user_id: Foreign key to users (which advisor)
        state: Two-letter state code (CA, NY, TX, etc.)
        license_number: License ID from state
        license_type: Type of license (optional)
        document_path: Where uploaded document is stored
        verification_status: pending/verified/rejected
        verified_at: When license was verified
        verified_by: Which admin user approved it
        reviewed_at: When an admin last reviewed (approved/rejected) the license
        reviewed_by: Which admin user last reviewed the license
        created_at: Auto-set timestamp
    """

    __tablename__ = "licenses"

    __table_args__ = (
        UniqueConstraint('state', 'license_number', name='uq_licenses_state_number'),
    )

    # Primary key
    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    # Foreign keys
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    verified_by: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("users.id", onupdate="CASCADE", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    reviewed_by: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("users.id", onupdate="CASCADE", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # License details
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    license_number: Mapped[str] = mapped_column(String(80), nullable=False)
    license_type: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)

    # Document storage
    document_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Verification workflow
    verification_status: Mapped[str] = mapped_column(
        SQLEnum("pending", "verified", "rejected", name="license_verification_status_enum"),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
    )

    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Rejection reason (if applicable)
    rejection_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Latest admin review metadata
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), server_default=text("CURRENT_TIMESTAMP")
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="licenses",
        foreign_keys=[user_id],
    )

    verified_by_user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="verified_licenses",
        foreign_keys=[verified_by],
    )

    resubmissions: Mapped[list["LicenseResubmission"]] = relationship(
        "LicenseResubmission",
        back_populates="license",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<License(id={self.id}, state='{self.state}', license_number='{self.license_number}', status='{self.verification_status}')>"
