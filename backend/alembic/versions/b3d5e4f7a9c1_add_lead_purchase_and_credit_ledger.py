"""Add lead purchase and credit ledger domain tables.

Revision ID: b3d5e4f7a9c1
Revises: aa12bb34cc56
Create Date: 2026-02-16 15:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b3d5e4f7a9c1"
down_revision: Union[str, None] = "aa12bb34cc56"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lead_purchases",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("package_id", sa.BigInteger(), nullable=False),
        sa.Column("stripe_checkout_session_id", sa.String(length=100), nullable=False),
        sa.Column("stripe_payment_intent_id", sa.String(length=100), nullable=True),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default=sa.text("'USD'"), nullable=False),
        sa.Column("credits_total", sa.Integer(), nullable=False),
        sa.Column("credits_remaining", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "completed",
                "failed",
                "refunded",
                "canceled",
                name="lead_purchase_status_enum",
            ),
            server_default=sa.text("'completed'"),
            nullable=False,
        ),
        sa.Column("purchased_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("credits_total >= 0", name="ck_lead_purchases_credits_total_nonnegative"),
        sa.CheckConstraint("credits_remaining >= 0", name="ck_lead_purchases_credits_remaining_nonnegative"),
        sa.CheckConstraint("credits_remaining <= credits_total", name="ck_lead_purchases_credits_remaining_lte_total"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], onupdate="CASCADE", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["package_id"], ["subscription_plans.id"], onupdate="CASCADE", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_lead_purchases_user_id"), "lead_purchases", ["user_id"], unique=False)
    op.create_index(op.f("ix_lead_purchases_package_id"), "lead_purchases", ["package_id"], unique=False)
    op.create_index(
        op.f("ix_lead_purchases_stripe_checkout_session_id"),
        "lead_purchases",
        ["stripe_checkout_session_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_lead_purchases_stripe_payment_intent_id"),
        "lead_purchases",
        ["stripe_payment_intent_id"],
        unique=True,
    )
    op.create_index(op.f("ix_lead_purchases_status"), "lead_purchases", ["status"], unique=False)
    op.create_index(op.f("ix_lead_purchases_purchased_at"), "lead_purchases", ["purchased_at"], unique=False)

    op.create_table(
        "lead_credit_ledger",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("purchase_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "movement_type",
            sa.Enum(
                "purchase_grant",
                "lead_consumed",
                "refund_adjustment",
                "admin_adjustment",
                name="lead_credit_movement_type_enum",
            ),
            nullable=False,
        ),
        sa.Column("credits_delta", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], onupdate="CASCADE", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["purchase_id"], ["lead_purchases.id"], onupdate="CASCADE", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_lead_credit_ledger_user_id"), "lead_credit_ledger", ["user_id"], unique=False)
    op.create_index(op.f("ix_lead_credit_ledger_purchase_id"), "lead_credit_ledger", ["purchase_id"], unique=False)
    op.create_index(
        op.f("ix_lead_credit_ledger_movement_type"),
        "lead_credit_ledger",
        ["movement_type"],
        unique=False,
    )
    op.create_index(op.f("ix_lead_credit_ledger_created_at"), "lead_credit_ledger", ["created_at"], unique=False)

    op.add_column("lead_downloads", sa.Column("purchase_id", sa.BigInteger(), nullable=True))
    op.create_index(op.f("ix_lead_downloads_purchase_id"), "lead_downloads", ["purchase_id"], unique=False)
    op.create_foreign_key(
        "fk_lead_downloads_purchase_id_lead_purchases",
        "lead_downloads",
        "lead_purchases",
        ["purchase_id"],
        ["id"],
        onupdate="CASCADE",
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_lead_downloads_purchase_id_lead_purchases", "lead_downloads", type_="foreignkey")
    op.drop_index(op.f("ix_lead_downloads_purchase_id"), table_name="lead_downloads")
    op.drop_column("lead_downloads", "purchase_id")

    op.drop_index(op.f("ix_lead_credit_ledger_created_at"), table_name="lead_credit_ledger")
    op.drop_index(op.f("ix_lead_credit_ledger_movement_type"), table_name="lead_credit_ledger")
    op.drop_index(op.f("ix_lead_credit_ledger_purchase_id"), table_name="lead_credit_ledger")
    op.drop_index(op.f("ix_lead_credit_ledger_user_id"), table_name="lead_credit_ledger")
    op.drop_table("lead_credit_ledger")

    op.drop_index(op.f("ix_lead_purchases_purchased_at"), table_name="lead_purchases")
    op.drop_index(op.f("ix_lead_purchases_status"), table_name="lead_purchases")
    op.drop_index(op.f("ix_lead_purchases_stripe_payment_intent_id"), table_name="lead_purchases")
    op.drop_index(op.f("ix_lead_purchases_stripe_checkout_session_id"), table_name="lead_purchases")
    op.drop_index(op.f("ix_lead_purchases_package_id"), table_name="lead_purchases")
    op.drop_index(op.f("ix_lead_purchases_user_id"), table_name="lead_purchases")
    op.drop_table("lead_purchases")
