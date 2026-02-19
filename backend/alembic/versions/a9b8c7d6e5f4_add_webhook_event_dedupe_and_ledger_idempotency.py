"""Add durable webhook event dedupe and ledger grant idempotency keys.

Revision ID: a9b8c7d6e5f4
Revises: f5c6d7e8f9a0
Create Date: 2026-02-19 23:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a9b8c7d6e5f4"
down_revision: Union[str, None] = "f5c6d7e8f9a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "processed_stripe_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("stripe_event_id", sa.String(length=100), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("processed_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_processed_stripe_events_stripe_event_id"),
        "processed_stripe_events",
        ["stripe_event_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_processed_stripe_events_event_type"),
        "processed_stripe_events",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_processed_stripe_events_processed_at"),
        "processed_stripe_events",
        ["processed_at"],
        unique=False,
    )

    op.add_column("lead_credit_ledger", sa.Column("idempotency_key", sa.String(length=191), nullable=True))
    op.create_index(
        op.f("ix_lead_credit_ledger_idempotency_key"),
        "lead_credit_ledger",
        ["idempotency_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_lead_credit_ledger_idempotency_key"), table_name="lead_credit_ledger")
    op.drop_column("lead_credit_ledger", "idempotency_key")

    op.drop_index(op.f("ix_processed_stripe_events_processed_at"), table_name="processed_stripe_events")
    op.drop_index(op.f("ix_processed_stripe_events_event_type"), table_name="processed_stripe_events")
    op.drop_index(op.f("ix_processed_stripe_events_stripe_event_id"), table_name="processed_stripe_events")
    op.drop_table("processed_stripe_events")
