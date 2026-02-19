"""Add Stripe reconciliation checkpoints table.

Revision ID: d7e8f9a0b1c2
Revises: c6d7e8f9a0b1
Create Date: 2026-02-20 03:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d7e8f9a0b1c2"
down_revision: Union[str, None] = "c6d7e8f9a0b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "stripe_reconciliation_checkpoints",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("last_event_created", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_event_id", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source"),
    )
    op.create_index(
        op.f("ix_stripe_reconciliation_checkpoints_source"),
        "stripe_reconciliation_checkpoints",
        ["source"],
        unique=True,
    )
    op.create_index(
        op.f("ix_stripe_reconciliation_checkpoints_last_event_created"),
        "stripe_reconciliation_checkpoints",
        ["last_event_created"],
        unique=False,
    )
    op.create_index(
        op.f("ix_stripe_reconciliation_checkpoints_created_at"),
        "stripe_reconciliation_checkpoints",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_stripe_reconciliation_checkpoints_created_at"),
        table_name="stripe_reconciliation_checkpoints",
    )
    op.drop_index(
        op.f("ix_stripe_reconciliation_checkpoints_last_event_created"),
        table_name="stripe_reconciliation_checkpoints",
    )
    op.drop_index(
        op.f("ix_stripe_reconciliation_checkpoints_source"),
        table_name="stripe_reconciliation_checkpoints",
    )
    op.drop_table("stripe_reconciliation_checkpoints")

