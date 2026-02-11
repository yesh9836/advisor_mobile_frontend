from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, declared_attr

from app.db.timezone import UTCDateTime, utcnow

class Base(DeclarativeBase):
    pass

class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""

    @declared_attr
    def created_at(cls) -> Mapped[datetime]:
        return mapped_column(
            UTCDateTime(),
            nullable=False,
            default=utcnow,
            server_default=text("CURRENT_TIMESTAMP"),
        )

    @declared_attr
    def updated_at(cls) -> Mapped[datetime]:
        return mapped_column(
            UTCDateTime(),
            nullable=False,
            default=utcnow,
            onupdate=utcnow,
            server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        )
