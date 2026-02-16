"""Relax lead_downloads uniqueness to allow repeated export auditing.

Revision ID: f6a7b8c9d0e1
Revises: e9a1c2d3f4a5
Create Date: 2026-02-16 20:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e9a1c2d3f4a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TARGET_TABLE = "lead_downloads"
_USER_LEAD_UNIQUE_NAME = "uq_lead_downloads_user_lead"
_GLOBAL_LEAD_UNIQUE_NAME = "uq_lead_downloads_global_lead"
_USER_LEAD_INDEX_NAME = "ix_lead_downloads_user_lead"


def _get_unique_names() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {
        constraint.get("name")
        for constraint in inspector.get_unique_constraints(_TARGET_TABLE)
        if constraint.get("name")
    }


def _get_index_names() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {
        index.get("name")
        for index in inspector.get_indexes(_TARGET_TABLE)
        if index.get("name")
    }


def _drop_named_unique_or_index(name: str) -> None:
    unique_names = _get_unique_names()
    if name in unique_names:
        with op.batch_alter_table(_TARGET_TABLE) as batch_op:
            batch_op.drop_constraint(name, type_="unique")
        return

    index_names = _get_index_names()
    if name in index_names:
        op.drop_index(name, table_name=_TARGET_TABLE)


def _has_named_key(name: str) -> bool:
    return name in _get_unique_names() or name in _get_index_names()


def _deduplicate_by_global_lead() -> None:
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


def upgrade() -> None:
    _drop_named_unique_or_index(_USER_LEAD_UNIQUE_NAME)
    _drop_named_unique_or_index(_GLOBAL_LEAD_UNIQUE_NAME)

    if not _has_named_key(_USER_LEAD_INDEX_NAME):
        op.create_index(
            _USER_LEAD_INDEX_NAME,
            _TARGET_TABLE,
            ["user_id", "lead_id"],
            unique=False,
        )


def downgrade() -> None:
    if _has_named_key(_USER_LEAD_INDEX_NAME):
        op.drop_index(_USER_LEAD_INDEX_NAME, table_name=_TARGET_TABLE)

    _deduplicate_by_global_lead()

    if not _has_named_key(_USER_LEAD_UNIQUE_NAME):
        op.create_unique_constraint(
            _USER_LEAD_UNIQUE_NAME,
            _TARGET_TABLE,
            ["user_id", "lead_id"],
        )

    if not _has_named_key(_GLOBAL_LEAD_UNIQUE_NAME):
        op.create_unique_constraint(
            _GLOBAL_LEAD_UNIQUE_NAME,
            _TARGET_TABLE,
            ["lead_id"],
        )
