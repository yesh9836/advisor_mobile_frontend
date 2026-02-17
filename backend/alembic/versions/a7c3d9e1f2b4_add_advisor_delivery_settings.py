"""Add advisor delivery settings table.

Revision ID: a7c3d9e1f2b4
Revises: f6a7b8c9d0e1
Create Date: 2026-02-17 14:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a7c3d9e1f2b4"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "advisor_delivery_settings"
_UPDATED_AT_INDEX = "ix_advisor_delivery_settings_updated_at"


def _has_table(name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return name in inspector.get_table_names()


def _get_index_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {
        index.get("name")
        for index in inspector.get_indexes(table_name)
        if index.get("name")
    }


def upgrade() -> None:
    if not _has_table(_TABLE):
        op.create_table(
            _TABLE,
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("email_alerts_enabled", sa.Boolean(), server_default=sa.text("0"), nullable=False),
            sa.Column("sms_alerts_enabled", sa.Boolean(), server_default=sa.text("0"), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], onupdate="CASCADE", ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("user_id"),
        )

    if _UPDATED_AT_INDEX not in _get_index_names(_TABLE):
        op.create_index(_UPDATED_AT_INDEX, _TABLE, ["updated_at"], unique=False)

    # Backfill one default row per advisor if missing.
    op.execute(
        sa.text(
            """
            INSERT INTO advisor_delivery_settings (
                user_id,
                email_alerts_enabled,
                sms_alerts_enabled,
                created_at,
                updated_at,
                version
            )
            SELECT
                u.id,
                0,
                0,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP,
                1
            FROM users AS u
            LEFT JOIN advisor_delivery_settings AS ads ON ads.user_id = u.id
            WHERE u.role = 'advisor' AND ads.user_id IS NULL
            """
        )
    )


def downgrade() -> None:
    if not _has_table(_TABLE):
        return

    if _UPDATED_AT_INDEX in _get_index_names(_TABLE):
        op.drop_index(_UPDATED_AT_INDEX, table_name=_TABLE)
    op.drop_table(_TABLE)
