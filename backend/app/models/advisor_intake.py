from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, ForeignKey, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.timezone import UTCDateTime, utcnow

from .base import Base

if TYPE_CHECKING:
    from .user import User


class AdvisorIntakeWebhookEvent(Base):
    """
    Idempotency registry for public advisor account intake webhooks.

    Prevents duplicate advisor account work when WordPress/Elementor retries
    deliveries for the same external submission.
    """

    __tablename__ = "advisor_intake_webhook_events"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "external_entry_id",
            name="uq_advisor_intake_webhook_events_provider_entry",
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
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    status_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_id: Mapped[Optional[int]] = mapped_column(
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
        index=True,
    )

    user: Mapped[Optional["User"]] = relationship("User", back_populates="advisor_intake_events")

    def __repr__(self) -> str:
        return (
            f"<AdvisorIntakeWebhookEvent(id={self.id}, provider='{self.provider}', "
            f"external_entry_id='{self.external_entry_id}', user_id={self.user_id}, "
            f"status='{self.status}')>"
        )
