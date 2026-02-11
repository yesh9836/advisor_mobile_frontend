from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.timezone import UTCDateTime, utcnow

from .base import Base

if TYPE_CHECKING:
    from .license import License
    from .user import User


class LicenseResubmission(Base):
    """Tracks advisor resubmissions for rejected licenses."""

    __tablename__ = "license_resubmissions"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    license_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("licenses.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    attempted_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utcnow,
        server_default=text("CURRENT_TIMESTAMP"),
        index=True,
    )

    license: Mapped["License"] = relationship("License", back_populates="resubmissions")
    user: Mapped["User"] = relationship("User")
