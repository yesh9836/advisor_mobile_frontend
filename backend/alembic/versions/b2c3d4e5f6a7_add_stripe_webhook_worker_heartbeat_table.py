"""Add Stripe webhook worker heartbeat table.

Revision ID: b2c3d4e5f6a7
Revises: a1d2e3f4b5c6
Create Date: 2026-02-20 18:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1d2e3f4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "stripe_webhook_worker_heartbeats",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("last_started_at", sa.DateTime(), nullable=True),
        sa.Column("last_completed_at", sa.DateTime(), nullable=True),
        sa.Column("last_success_at", sa.DateTime(), nullable=True),
        sa.Column("last_summary", sa.JSON(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_stripe_webhook_worker_heartbeats_source"),
        "stripe_webhook_worker_heartbeats",
        ["source"],
        unique=True,
    )
    op.create_index(
        op.f("ix_stripe_webhook_worker_heartbeats_last_started_at"),
        "stripe_webhook_worker_heartbeats",
        ["last_started_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_stripe_webhook_worker_heartbeats_last_completed_at"),
        "stripe_webhook_worker_heartbeats",
        ["last_completed_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_stripe_webhook_worker_heartbeats_last_success_at"),
        "stripe_webhook_worker_heartbeats",
        ["last_success_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_stripe_webhook_worker_heartbeats_created_at"),
        "stripe_webhook_worker_heartbeats",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_stripe_webhook_worker_heartbeats_created_at"),
        table_name="stripe_webhook_worker_heartbeats",
    )
    op.drop_index(
        op.f("ix_stripe_webhook_worker_heartbeats_last_success_at"),
        table_name="stripe_webhook_worker_heartbeats",
    )
    op.drop_index(
        op.f("ix_stripe_webhook_worker_heartbeats_last_completed_at"),
        table_name="stripe_webhook_worker_heartbeats",
    )
    op.drop_index(
        op.f("ix_stripe_webhook_worker_heartbeats_last_started_at"),
        table_name="stripe_webhook_worker_heartbeats",
    )
    op.drop_index(
        op.f("ix_stripe_webhook_worker_heartbeats_source"),
        table_name="stripe_webhook_worker_heartbeats",
    )
    op.drop_table("stripe_webhook_worker_heartbeats")

