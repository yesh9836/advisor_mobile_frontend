"""Add durable Stripe webhook inbox table.

Revision ID: c6d7e8f9a0b1
Revises: b1c2d3e4f5a6
Create Date: 2026-02-20 01:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c6d7e8f9a0b1"
down_revision: Union[str, None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "stripe_webhook_inbox",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("stripe_event_id", sa.String(length=100), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "processing",
                "processed",
                "failed",
                name="stripe_webhook_inbox_status_enum",
            ),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("attempt_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default=sa.text("10"), nullable=False),
        sa.Column("next_retry_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("locked_at", sa.DateTime(), nullable=True),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stripe_event_id"),
    )
    op.create_index(
        op.f("ix_stripe_webhook_inbox_stripe_event_id"),
        "stripe_webhook_inbox",
        ["stripe_event_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_stripe_webhook_inbox_event_type"),
        "stripe_webhook_inbox",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_stripe_webhook_inbox_status"),
        "stripe_webhook_inbox",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_stripe_webhook_inbox_next_retry_at"),
        "stripe_webhook_inbox",
        ["next_retry_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_stripe_webhook_inbox_locked_at"),
        "stripe_webhook_inbox",
        ["locked_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_stripe_webhook_inbox_processed_at"),
        "stripe_webhook_inbox",
        ["processed_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_stripe_webhook_inbox_created_at"),
        "stripe_webhook_inbox",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_stripe_webhook_inbox_status_retry",
        "stripe_webhook_inbox",
        ["status", "next_retry_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_stripe_webhook_inbox_status_retry", table_name="stripe_webhook_inbox")
    op.drop_index(op.f("ix_stripe_webhook_inbox_created_at"), table_name="stripe_webhook_inbox")
    op.drop_index(op.f("ix_stripe_webhook_inbox_processed_at"), table_name="stripe_webhook_inbox")
    op.drop_index(op.f("ix_stripe_webhook_inbox_locked_at"), table_name="stripe_webhook_inbox")
    op.drop_index(op.f("ix_stripe_webhook_inbox_next_retry_at"), table_name="stripe_webhook_inbox")
    op.drop_index(op.f("ix_stripe_webhook_inbox_status"), table_name="stripe_webhook_inbox")
    op.drop_index(op.f("ix_stripe_webhook_inbox_event_type"), table_name="stripe_webhook_inbox")
    op.drop_index(op.f("ix_stripe_webhook_inbox_stripe_event_id"), table_name="stripe_webhook_inbox")
    op.drop_table("stripe_webhook_inbox")

