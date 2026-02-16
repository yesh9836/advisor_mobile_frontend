"""Enforce global single-owner uniqueness for lead deliveries.

Revision ID: c1a8e9f0d7b2
Revises: b3d5e4f7a9c1
Create Date: 2026-02-16 18:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c1a8e9f0d7b2"
down_revision: Union[str, None] = "b3d5e4f7a9c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TARGET_TABLE = "lead_downloads"
_GLOBAL_UNIQUE_NAME = "uq_lead_downloads_global_lead"
_GLOBAL_COLUMNS = {"lead_id"}


def _deduplicate_global_lead_ownership() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name if bind is not None else ""

    if dialect_name == "mysql":
        op.execute(
            sa.text(
                """
                DELETE newer
                FROM lead_downloads AS newer
                INNER JOIN lead_downloads AS existing
                    ON newer.lead_id = existing.lead_id
                    AND (
                        newer.downloaded_at > existing.downloaded_at
                        OR (
                            newer.downloaded_at = existing.downloaded_at
                            AND newer.id > existing.id
                        )
                    )
                """
            )
        )
        return

    op.execute(
        sa.text(
            """
            DELETE FROM lead_downloads
            WHERE id IN (
                SELECT id
                FROM (
                    SELECT
                        id,
                        ROW_NUMBER() OVER (
                            PARTITION BY lead_id
                            ORDER BY downloaded_at ASC, id ASC
                        ) AS rn
                    FROM lead_downloads
                ) AS ranked
                WHERE ranked.rn > 1
            )
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


def _has_equivalent_global_uniqueness() -> bool:
    inspector = sa.inspect(op.get_bind())

    for constraint in inspector.get_unique_constraints(_TARGET_TABLE):
        columns = constraint.get("column_names") or []
        if set(columns) == _GLOBAL_COLUMNS:
            return True

    for index in inspector.get_indexes(_TARGET_TABLE):
        columns = index.get("column_names") or []
        if index.get("unique") and set(columns) == _GLOBAL_COLUMNS:
            return True

    return False


def upgrade() -> None:
    _deduplicate_global_lead_ownership()

    if not _has_equivalent_global_uniqueness() and not _has_named_key(_GLOBAL_UNIQUE_NAME):
        op.create_index(
            _GLOBAL_UNIQUE_NAME,
            _TARGET_TABLE,
            ["lead_id"],
            unique=True,
        )


def downgrade() -> None:
    if _has_named_key(_GLOBAL_UNIQUE_NAME):
        op.drop_index(_GLOBAL_UNIQUE_NAME, table_name=_TARGET_TABLE)
