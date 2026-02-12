"""Add user deactivation fields.

Revision ID: aa12bb34cc56
Revises: f1a2b3c4d5e6
Create Date: 2026-02-12 18:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "aa12bb34cc56"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )
    op.add_column("users", sa.Column("deactivated_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("deactivated_by", sa.BigInteger(), nullable=True))

    op.execute("UPDATE users SET is_active = 1 WHERE is_active IS NULL")

    op.create_index(op.f("ix_users_is_active"), "users", ["is_active"], unique=False)
    op.create_index(
        op.f("ix_users_deactivated_at"),
        "users",
        ["deactivated_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_users_deactivated_by"),
        "users",
        ["deactivated_by"],
        unique=False,
    )

    op.create_foreign_key(
        "fk_users_deactivated_by_users",
        "users",
        "users",
        ["deactivated_by"],
        ["id"],
        onupdate="CASCADE",
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_users_deactivated_by_users", "users", type_="foreignkey")
    op.drop_index(op.f("ix_users_deactivated_by"), table_name="users")
    op.drop_index(op.f("ix_users_deactivated_at"), table_name="users")
    op.drop_index(op.f("ix_users_is_active"), table_name="users")

    op.drop_column("users", "deactivated_by")
    op.drop_column("users", "deactivated_at")
    op.drop_column("users", "is_active")
