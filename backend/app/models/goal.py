from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Integer, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.timezone import UTCDateTime, utcnow

from .base import Base

if TYPE_CHECKING:
    from .user import User


class AdvisorGoal(Base):
    """One saved annual income goal per advisor."""

    __tablename__ = "advisor_goals"
    __table_args__ = (
        UniqueConstraint("user_id", "target_year", name="uq_advisor_goals_user_year"),
        CheckConstraint("target_year >= 2000 AND target_year <= 2100", name="ck_advisor_goals_target_year"),
        CheckConstraint("annual_income_goal_cents > 0", name="ck_advisor_goals_annual_income_positive"),
        CheckConstraint("average_commission_cents > 0", name="ck_advisor_goals_average_commission_positive"),
        CheckConstraint("earned_ytd_cents >= 0", name="ck_advisor_goals_earned_ytd_non_negative"),
        CheckConstraint(
            "appointment_to_deal_rate_bps >= 1 AND appointment_to_deal_rate_bps <= 10000",
            name="ck_advisor_goals_appointment_to_deal_rate",
        ),
        CheckConstraint(
            "lead_to_appointment_rate_bps >= 1 AND lead_to_appointment_rate_bps <= 10000",
            name="ck_advisor_goals_lead_to_appointment_rate",
        ),
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
    target_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    annual_income_goal_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    average_commission_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    average_sale_cents: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    commission_rate_bps: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    earned_ytd_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    appointment_to_deal_rate_bps: Mapped[int] = mapped_column(Integer, nullable=False)
    lead_to_appointment_rate_bps: Mapped[int] = mapped_column(Integer, nullable=False)
    onboarding_completed_at: Mapped[Optional[datetime]] = mapped_column(
        UTCDateTime(),
        nullable=True,
    )
    onboarding_consent_at: Mapped[Optional[datetime]] = mapped_column(
        UTCDateTime(),
        nullable=True,
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
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )

    user: Mapped["User"] = relationship("User", back_populates="advisor_goals")

    def __repr__(self) -> str:
        return (
            f"<AdvisorGoal(id={self.id}, user_id={self.user_id}, "
            f"target_year={self.target_year})>"
        )
