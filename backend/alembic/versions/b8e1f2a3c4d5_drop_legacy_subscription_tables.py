"""Drop retired subscription catalog and lifecycle tables.

Revision ID: b8e1f2a3c4d5
Revises: a7c3d9e1f2b4
Create Date: 2026-02-18 17:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b8e1f2a3c4d5"
down_revision: Union[str, None] = "a7c3d9e1f2b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_LEGACY_PLAN_TABLE = "subscription_plans"
_LEGACY_SUBSCRIPTION_TABLE = "subscriptions"
_PURCHASE_TABLE = "lead_purchases"


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def _drop_purchase_fk_to_legacy_plan() -> None:
    inspector = sa.inspect(op.get_bind())
    for foreign_key in inspector.get_foreign_keys(_PURCHASE_TABLE):
        referred_table = foreign_key.get("referred_table")
        constrained_columns = foreign_key.get("constrained_columns") or []
        constraint_name = foreign_key.get("name")
        if (
            referred_table == _LEGACY_PLAN_TABLE
            and constrained_columns == ["package_id"]
            and constraint_name
        ):
            with op.batch_alter_table(_PURCHASE_TABLE) as batch_op:
                batch_op.drop_constraint(constraint_name, type_="foreignkey")
            break


def upgrade() -> None:
    if _table_exists(_LEGACY_PLAN_TABLE):
        _drop_purchase_fk_to_legacy_plan()

    if _table_exists(_LEGACY_SUBSCRIPTION_TABLE):
        op.drop_table(_LEGACY_SUBSCRIPTION_TABLE)
    if _table_exists(_LEGACY_PLAN_TABLE):
        op.drop_table(_LEGACY_PLAN_TABLE)


def downgrade() -> None:
    if not _table_exists(_LEGACY_PLAN_TABLE):
        op.create_table(
            _LEGACY_PLAN_TABLE,
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("price_cents", sa.Integer(), nullable=False),
            sa.Column("currency", sa.String(length=3), server_default=sa.text("'USD'"), nullable=False),
            sa.Column("state_limit", sa.Integer(), nullable=True),
            sa.Column("daily_download_limit", sa.Integer(), server_default=sa.text("0"), nullable=False),
            sa.Column("features", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("stripe_price_id", sa.String(length=100), nullable=False, unique=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_subscription_plans_name"), _LEGACY_PLAN_TABLE, ["name"], unique=True)

    if not _table_exists(_LEGACY_SUBSCRIPTION_TABLE):
        op.create_table(
            _LEGACY_SUBSCRIPTION_TABLE,
            sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column("plan_id", sa.BigInteger(), nullable=False),
            sa.Column("stripe_subscription_id", sa.String(length=100), nullable=False),
            sa.Column(
                "status",
                sa.Enum(
                    "trialing",
                    "active",
                    "past_due",
                    "canceled",
                    "unpaid",
                    "incomplete",
                    "incomplete_expired",
                    "paused",
                    name="subscription_status_enum",
                ),
                server_default=sa.text("'active'"),
                nullable=False,
            ),
            sa.Column("current_period_start", sa.DateTime(), nullable=True),
            sa.Column("current_period_end", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.ForeignKeyConstraint(["plan_id"], ["subscription_plans.id"], onupdate="CASCADE", ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], onupdate="CASCADE", ondelete="RESTRICT"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_subscriptions_plan_id"), _LEGACY_SUBSCRIPTION_TABLE, ["plan_id"], unique=False)
        op.create_index(
            op.f("ix_subscriptions_stripe_subscription_id"),
            _LEGACY_SUBSCRIPTION_TABLE,
            ["stripe_subscription_id"],
            unique=True,
        )
        op.create_index(op.f("ix_subscriptions_user_id"), _LEGACY_SUBSCRIPTION_TABLE, ["user_id"], unique=False)
