from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, String, JSON, ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.timezone import UTCDateTime, utcnow

from .base import Base

if TYPE_CHECKING:
    from .user import User


class AuditLog(Base):
    """
    Complete audit trail of all actions.
    
    Logs user registration, license submission/approval/rejection,
    subscription creation/cancellation, lead downloads, admin actions, etc.
    
    Attributes:
        id: Primary key
        actor_user_id: Which user performed action
        action: What they did (e.g., 'license_approved', 'lead_downloaded')
        entity_type: Type of thing affected (e.g., 'License', 'Lead')
        entity_id: Specific ID (e.g., license #123)
        metadata: Extra info as JSON
        ip_address: User's IP address
        created_at: Auto-set timestamp
    """

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    actor_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        index=True,
    )

    meta_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utcnow,
        server_default=text("CURRENT_TIMESTAMP"),
        index=True,
    )

    actor_user: Mapped["User"] = relationship("User", back_populates="audit_logs")

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action='{self.action}', entity='{self.entity_type}:{self.entity_id}')>"
