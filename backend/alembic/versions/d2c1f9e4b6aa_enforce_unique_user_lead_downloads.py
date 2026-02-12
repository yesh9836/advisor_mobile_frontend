"""Enforce unique user/lead deliveries in lead_downloads.

Revision ID: d2c1f9e4b6aa
Revises: a4f2e7d91c3b
Create Date: 2026-02-11 13:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d2c1f9e4b6aa"
down_revision: Union[str, None] = "a4f2e7d91c3b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TARGET_TABLE = "lead_downloads"
_TARGET_CONSTRAINT = "uq_lead_downloads_user_lead"
_TARGET_COLUMNS = {"user_id", "lead_id"}


def _deduplicate_lead_downloads_mysql() -> None:
    op.execute(
        sa.text(
            """
            DELETE newer
            FROM lead_downloads AS newer
            INNER JOIN lead_downloads AS existing
                ON newer.user_id = existing.user_id
                AND newer.lead_id = existing.lead_id
                AND newer.id > existing.id
            """
        )
    )


def _has_named_key(name: str) -> bool:
    inspector = sa.inspect(op.get_bind())

    unique_names = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints(_TARGET_TABLE)
        if constraint.get("name")
    }
    index_names = {
        index["name"]
        for index in inspector.get_indexes(_TARGET_TABLE)
        if index.get("name")
    }

    return name in unique_names or name in index_names


def _has_equivalent_user_lead_uniqueness() -> bool:
    inspector = sa.inspect(op.get_bind())

    for constraint in inspector.get_unique_constraints(_TARGET_TABLE):
        columns = constraint.get("column_names") or []
        if set(columns) == _TARGET_COLUMNS:
            return True

    for index in inspector.get_indexes(_TARGET_TABLE):
        columns = index.get("column_names") or []
        if index.get("unique") and set(columns) == _TARGET_COLUMNS:
            return True

    return False


def upgrade() -> None:
    _deduplicate_lead_downloads_mysql()

    if not _has_equivalent_user_lead_uniqueness() and not _has_named_key(_TARGET_CONSTRAINT):
        op.create_unique_constraint(
            _TARGET_CONSTRAINT,
            _TARGET_TABLE,
            ["user_id", "lead_id"],
        )


def downgrade() -> None:
    if _has_named_key(_TARGET_CONSTRAINT):
        op.drop_constraint(_TARGET_CONSTRAINT, _TARGET_TABLE, type_="unique")
