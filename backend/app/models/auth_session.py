from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.timezone import UTCDateTime, utcnow

from .base import Base

if TYPE_CHECKING:
    from .user import User


class RefreshTokenSession(Base):
    """
    Persisted refresh-token record used for rotation and reuse detection.
    """

    __tablename__ = "refresh_token_sessions"

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

    family_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)

    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, index=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime(), nullable=True)

    revoked_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime(), nullable=True, index=True)
    revoked_reason: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    user_agent: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utcnow,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    user: Mapped["User"] = relationship("User", back_populates="refresh_sessions")

    def __repr__(self) -> str:
        return (
            f"<RefreshTokenSession(id={self.id}, user_id={self.user_id}, "
            f"family_id='{self.family_id}')>"
        )
