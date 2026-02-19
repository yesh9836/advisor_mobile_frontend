"""Add durable poison-event sink for non-retryable Stripe webhook failures.

Revision ID: b1c2d3e4f5a6
Revises: a9b8c7d6e5f4
Create Date: 2026-02-20 00:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, None] = "a9b8c7d6e5f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "stripe_poison_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("stripe_event_id", sa.String(length=100), nullable=True),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("reason", sa.String(length=120), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("payload_excerpt", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_stripe_poison_events_stripe_event_id"),
        "stripe_poison_events",
        ["stripe_event_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_stripe_poison_events_event_type"),
        "stripe_poison_events",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_stripe_poison_events_reason"),
        "stripe_poison_events",
        ["reason"],
        unique=False,
    )
    op.create_index(
        op.f("ix_stripe_poison_events_created_at"),
        "stripe_poison_events",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_stripe_poison_events_created_at"), table_name="stripe_poison_events")
    op.drop_index(op.f("ix_stripe_poison_events_reason"), table_name="stripe_poison_events")
    op.drop_index(op.f("ix_stripe_poison_events_event_type"), table_name="stripe_poison_events")
    op.drop_index(op.f("ix_stripe_poison_events_stripe_event_id"), table_name="stripe_poison_events")
    op.drop_table("stripe_poison_events")
