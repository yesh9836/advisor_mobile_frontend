"""Add license resubmissions table

Revision ID: c9f6d4a6f2b1
Revises: ff8847dbae31
Create Date: 2026-02-10 14:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c9f6d4a6f2b1"
down_revision: Union[str, None] = "ff8847dbae31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "license_resubmissions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("license_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "attempted_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["license_id"], ["licenses.id"], onupdate="CASCADE", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], onupdate="CASCADE", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_license_resubmissions_attempted_at"), "license_resubmissions", ["attempted_at"], unique=False)
    op.create_index(op.f("ix_license_resubmissions_license_id"), "license_resubmissions", ["license_id"], unique=False)
    op.create_index(op.f("ix_license_resubmissions_user_id"), "license_resubmissions", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_license_resubmissions_user_id"), table_name="license_resubmissions")
    op.drop_index(op.f("ix_license_resubmissions_license_id"), table_name="license_resubmissions")
    op.drop_index(op.f("ix_license_resubmissions_attempted_at"), table_name="license_resubmissions")
    op.drop_table("license_resubmissions")
