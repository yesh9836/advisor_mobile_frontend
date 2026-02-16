"""Add dedicated lead package catalog and rewire purchases to it.

Revision ID: d4e5f6a7b8c9
Revises: c1a8e9f0d7b2
Create Date: 2026-02-16 18:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c1a8e9f0d7b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PURCHASES_TABLE = "lead_purchases"
_LEGACY_PLAN_TABLE = "subscription_plans"
_PACKAGE_TABLE = "lead_packages"
_FK_TO_PACKAGES = "fk_lead_purchases_package_id_lead_packages"
_FK_TO_LEGACY_PLANS = "fk_lead_purchases_package_id_subscription_plans"


def _drop_package_fk_to(table_name: str) -> None:
    inspector = sa.inspect(op.get_bind())
    for foreign_key in inspector.get_foreign_keys(_PURCHASES_TABLE):
        referred_table = foreign_key.get("referred_table")
        constrained_columns = foreign_key.get("constrained_columns") or []
        constraint_name = foreign_key.get("name")
        if (
            referred_table == table_name
            and constrained_columns == ["package_id"]
            and constraint_name
        ):
            op.drop_constraint(constraint_name, _PURCHASES_TABLE, type_="foreignkey")
            break


def _backfill_packages_from_subscription_plans() -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO lead_packages (
                id,
                name,
                price_cents,
                currency,
                stripe_price_id,
                state_limit,
                daily_download_limit,
                features,
                created_at
            )
            SELECT
                sp.id,
                sp.name,
                sp.price_cents,
                COALESCE(sp.currency, 'USD'),
                sp.stripe_price_id,
                sp.state_limit,
                COALESCE(sp.daily_download_limit, 0),
                sp.features,
                COALESCE(sp.created_at, CURRENT_TIMESTAMP)
            FROM subscription_plans AS sp
            LEFT JOIN lead_packages AS lp ON lp.id = sp.id
            WHERE lp.id IS NULL
            """
        )
    )


def _backfill_subscription_plans_from_packages() -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO subscription_plans (
                id,
                name,
                price_cents,
                currency,
                stripe_price_id,
                state_limit,
                daily_download_limit,
                features,
                created_at
            )
            SELECT
                lp.id,
                lp.name,
                lp.price_cents,
                COALESCE(lp.currency, 'USD'),
                lp.stripe_price_id,
                lp.state_limit,
                COALESCE(lp.daily_download_limit, 0),
                lp.features,
                COALESCE(lp.created_at, CURRENT_TIMESTAMP)
            FROM lead_packages AS lp
            LEFT JOIN subscription_plans AS sp ON sp.id = lp.id
            WHERE sp.id IS NULL
            """
        )
    )


def upgrade() -> None:
    op.create_table(
        _PACKAGE_TABLE,
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), server_default=sa.text("'USD'"), nullable=False),
        sa.Column("stripe_price_id", sa.String(length=100), nullable=False),
        sa.Column("state_limit", sa.Integer(), nullable=True),
        sa.Column("daily_download_limit", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("features", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_lead_packages_name"), _PACKAGE_TABLE, ["name"], unique=True)
    op.create_index(op.f("ix_lead_packages_stripe_price_id"), _PACKAGE_TABLE, ["stripe_price_id"], unique=True)

    _backfill_packages_from_subscription_plans()

    _drop_package_fk_to(_LEGACY_PLAN_TABLE)
    op.create_foreign_key(
        _FK_TO_PACKAGES,
        _PURCHASES_TABLE,
        _PACKAGE_TABLE,
        ["package_id"],
        ["id"],
        onupdate="CASCADE",
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    _drop_package_fk_to(_PACKAGE_TABLE)
    _backfill_subscription_plans_from_packages()
    op.create_foreign_key(
        _FK_TO_LEGACY_PLANS,
        _PURCHASES_TABLE,
        _LEGACY_PLAN_TABLE,
        ["package_id"],
        ["id"],
        onupdate="CASCADE",
        ondelete="RESTRICT",
    )

    op.drop_index(op.f("ix_lead_packages_stripe_price_id"), table_name=_PACKAGE_TABLE)
    op.drop_index(op.f("ix_lead_packages_name"), table_name=_PACKAGE_TABLE)
    op.drop_table(_PACKAGE_TABLE)
