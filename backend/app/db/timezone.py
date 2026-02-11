from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime
from sqlalchemy.dialects import mysql
from sqlalchemy.types import TypeDecorator


def utcnow() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


def ensure_utc(value: Optional[datetime]) -> Optional[datetime]:
    """Normalize datetimes to UTC while preserving naive-as-UTC compatibility."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class UTCDateTime(TypeDecorator):
    """
    Persist UTC datetimes in DB and always return timezone-aware UTC datetimes.
    """

    impl = DateTime
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "mysql":
            return dialect.type_descriptor(mysql.TIMESTAMP())
        return dialect.type_descriptor(DateTime())

    def process_bind_param(self, value: Optional[datetime], dialect):
        normalized = ensure_utc(value)
        if normalized is None:
            return None
        # Store as naive UTC; MySQL session timezone is forced to UTC.
        return normalized.replace(tzinfo=None)

    def process_result_value(self, value: Optional[datetime], dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
