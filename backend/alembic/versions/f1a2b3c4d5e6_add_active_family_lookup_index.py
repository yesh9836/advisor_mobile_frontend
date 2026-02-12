"""Add composite index for active refresh-session family lookups.

Revision ID: f1a2b3c4d5e6
Revises: e7f8a1b2c3d4
Create Date: 2026-02-12 16:40:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "e7f8a1b2c3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_INDEX_NAME = "ix_refresh_token_sessions_user_family_active"
_TABLE_NAME = "refresh_token_sessions"


def upgrade() -> None:
    op.create_index(
        _INDEX_NAME,
        _TABLE_NAME,
        ["user_id", "family_id", "revoked_at", "expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(_INDEX_NAME, table_name=_TABLE_NAME)
