"""Add password reset request attempts table.

Revision ID: e1b2c3d4e5f6
Revises: d7e8f9a0b1c2
Create Date: 2026-02-20 11:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e1b2c3d4e5f6"
down_revision: Union[str, None] = "d7e8f9a0b1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "password_reset_request_attempts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("subject_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_password_reset_request_attempts_subject_hash"),
        "password_reset_request_attempts",
        ["subject_hash"],
        unique=False,
    )
    op.create_index(
        "ix_password_reset_request_attempts_subject_created_at",
        "password_reset_request_attempts",
        ["subject_hash", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_password_reset_request_attempts_subject_created_at",
        table_name="password_reset_request_attempts",
    )
    op.drop_index(
        op.f("ix_password_reset_request_attempts_subject_hash"),
        table_name="password_reset_request_attempts",
    )
    op.drop_table("password_reset_request_attempts")
