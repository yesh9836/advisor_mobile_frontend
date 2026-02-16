"""Add lead ownership records for purchase-time assignment.

Revision ID: e9a1c2d3f4a5
Revises: d4e5f6a7b8c9
Create Date: 2026-02-16 19:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e9a1c2d3f4a5"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lead_ownerships",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("lead_id", sa.BigInteger(), nullable=False),
        sa.Column("purchase_id", sa.BigInteger(), nullable=True),
        sa.Column("assigned_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], onupdate="CASCADE", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["purchase_id"], ["lead_purchases.id"], onupdate="CASCADE", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], onupdate="CASCADE", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "lead_id", name="uq_lead_ownerships_user_lead"),
        sa.UniqueConstraint("lead_id", name="uq_lead_ownerships_global_lead"),
    )
    op.create_index(op.f("ix_lead_ownerships_user_id"), "lead_ownerships", ["user_id"], unique=False)
    op.create_index(op.f("ix_lead_ownerships_lead_id"), "lead_ownerships", ["lead_id"], unique=False)
    op.create_index(op.f("ix_lead_ownerships_purchase_id"), "lead_ownerships", ["purchase_id"], unique=False)
    op.create_index(op.f("ix_lead_ownerships_assigned_at"), "lead_ownerships", ["assigned_at"], unique=False)

    # Preserve existing sold-lead ownership semantics by backfilling from historic download records.
    op.execute(
        sa.text(
            """
            INSERT INTO lead_ownerships (user_id, lead_id, purchase_id, assigned_at)
            SELECT
                ld.user_id,
                ld.lead_id,
                ld.purchase_id,
                COALESCE(ld.downloaded_at, CURRENT_TIMESTAMP)
            FROM lead_downloads AS ld
            LEFT JOIN lead_ownerships AS lo ON lo.lead_id = ld.lead_id
            WHERE lo.id IS NULL
            """
        )
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_lead_ownerships_assigned_at"), table_name="lead_ownerships")
    op.drop_index(op.f("ix_lead_ownerships_purchase_id"), table_name="lead_ownerships")
    op.drop_index(op.f("ix_lead_ownerships_lead_id"), table_name="lead_ownerships")
    op.drop_index(op.f("ix_lead_ownerships_user_id"), table_name="lead_ownerships")
    op.drop_table("lead_ownerships")
