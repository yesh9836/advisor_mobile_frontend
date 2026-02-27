"""Add stripe plan cleanup outbox table.

Revision ID: b9c0d1e2f3a4
Revises: a6b7c8d9e0f1
Create Date: 2026-02-27 11:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b9c0d1e2f3a4"
down_revision: Union[str, None] = "a6b7c8d9e0f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "stripe_plan_cleanup_outbox",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("stripe_price_id", sa.String(length=100), nullable=True),
        sa.Column("stripe_product_id", sa.String(length=100), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "processing",
                "processed",
                "failed",
                name="stripe_plan_cleanup_outbox_status_enum",
            ),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default=sa.text("10")),
        sa.Column("next_retry_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("locked_at", sa.DateTime(), nullable=True),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=191), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "stripe_price_id IS NOT NULL OR stripe_product_id IS NOT NULL",
            name="ck_stripe_plan_cleanup_outbox_target_present",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        op.f("ix_stripe_plan_cleanup_outbox_source"),
        "stripe_plan_cleanup_outbox",
        ["source"],
        unique=False,
    )
    op.create_index(
        op.f("ix_stripe_plan_cleanup_outbox_stripe_price_id"),
        "stripe_plan_cleanup_outbox",
        ["stripe_price_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_stripe_plan_cleanup_outbox_stripe_product_id"),
        "stripe_plan_cleanup_outbox",
        ["stripe_product_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_stripe_plan_cleanup_outbox_status"),
        "stripe_plan_cleanup_outbox",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_stripe_plan_cleanup_outbox_next_retry_at"),
        "stripe_plan_cleanup_outbox",
        ["next_retry_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_stripe_plan_cleanup_outbox_locked_at"),
        "stripe_plan_cleanup_outbox",
        ["locked_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_stripe_plan_cleanup_outbox_processed_at"),
        "stripe_plan_cleanup_outbox",
        ["processed_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_stripe_plan_cleanup_outbox_idempotency_key"),
        "stripe_plan_cleanup_outbox",
        ["idempotency_key"],
        unique=True,
    )
    op.create_index(
        op.f("ix_stripe_plan_cleanup_outbox_created_at"),
        "stripe_plan_cleanup_outbox",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_stripe_plan_cleanup_outbox_status_retry",
        "stripe_plan_cleanup_outbox",
        ["status", "next_retry_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_stripe_plan_cleanup_outbox_status_retry", table_name="stripe_plan_cleanup_outbox")
    op.drop_index(op.f("ix_stripe_plan_cleanup_outbox_created_at"), table_name="stripe_plan_cleanup_outbox")
    op.drop_index(op.f("ix_stripe_plan_cleanup_outbox_idempotency_key"), table_name="stripe_plan_cleanup_outbox")
    op.drop_index(op.f("ix_stripe_plan_cleanup_outbox_processed_at"), table_name="stripe_plan_cleanup_outbox")
    op.drop_index(op.f("ix_stripe_plan_cleanup_outbox_locked_at"), table_name="stripe_plan_cleanup_outbox")
    op.drop_index(op.f("ix_stripe_plan_cleanup_outbox_next_retry_at"), table_name="stripe_plan_cleanup_outbox")
    op.drop_index(op.f("ix_stripe_plan_cleanup_outbox_status"), table_name="stripe_plan_cleanup_outbox")
    op.drop_index(op.f("ix_stripe_plan_cleanup_outbox_stripe_product_id"), table_name="stripe_plan_cleanup_outbox")
    op.drop_index(op.f("ix_stripe_plan_cleanup_outbox_stripe_price_id"), table_name="stripe_plan_cleanup_outbox")
    op.drop_index(op.f("ix_stripe_plan_cleanup_outbox_source"), table_name="stripe_plan_cleanup_outbox")
    op.drop_table("stripe_plan_cleanup_outbox")
