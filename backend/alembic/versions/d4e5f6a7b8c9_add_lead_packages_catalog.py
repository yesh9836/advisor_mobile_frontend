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
_PACKAGE_NAME_INDEX = "ix_lead_packages_name"
_PACKAGE_STRIPE_PRICE_INDEX = "ix_lead_packages_stripe_price_id"


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
            with op.batch_alter_table(_PURCHASES_TABLE) as batch_op:
                batch_op.drop_constraint(constraint_name, type_="foreignkey")
            break


def _create_package_fk(constraint_name: str, referred_table: str) -> None:
    with op.batch_alter_table(_PURCHASES_TABLE) as batch_op:
        batch_op.create_foreign_key(
            constraint_name,
            referred_table,
            ["package_id"],
            ["id"],
            onupdate="CASCADE",
            ondelete="RESTRICT",
        )


def _table_exists(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def _index_exists(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    existing_indexes = {
        index.get("name")
        for index in inspector.get_indexes(table_name)
        if index.get("name")
    }
    return index_name in existing_indexes


def _has_package_fk_to(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    for foreign_key in inspector.get_foreign_keys(_PURCHASES_TABLE):
        if (
            foreign_key.get("referred_table") == table_name
            and (foreign_key.get("constrained_columns") or []) == ["package_id"]
        ):
            return True
    return False


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
    if not _table_exists(_PACKAGE_TABLE):
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

    if not _index_exists(_PACKAGE_TABLE, _PACKAGE_NAME_INDEX):
        op.create_index(op.f(_PACKAGE_NAME_INDEX), _PACKAGE_TABLE, ["name"], unique=True)
    if not _index_exists(_PACKAGE_TABLE, _PACKAGE_STRIPE_PRICE_INDEX):
        op.create_index(op.f(_PACKAGE_STRIPE_PRICE_INDEX), _PACKAGE_TABLE, ["stripe_price_id"], unique=True)

    _backfill_packages_from_subscription_plans()

    if _has_package_fk_to(_LEGACY_PLAN_TABLE):
        _drop_package_fk_to(_LEGACY_PLAN_TABLE)
    if not _has_package_fk_to(_PACKAGE_TABLE):
        _create_package_fk(_FK_TO_PACKAGES, _PACKAGE_TABLE)


def downgrade() -> None:
    if _has_package_fk_to(_PACKAGE_TABLE):
        _drop_package_fk_to(_PACKAGE_TABLE)
    _backfill_subscription_plans_from_packages()
    if not _has_package_fk_to(_LEGACY_PLAN_TABLE):
        _create_package_fk(_FK_TO_LEGACY_PLANS, _LEGACY_PLAN_TABLE)

    if _table_exists(_PACKAGE_TABLE):
        if _index_exists(_PACKAGE_TABLE, _PACKAGE_STRIPE_PRICE_INDEX):
            op.drop_index(op.f(_PACKAGE_STRIPE_PRICE_INDEX), table_name=_PACKAGE_TABLE)
        if _index_exists(_PACKAGE_TABLE, _PACKAGE_NAME_INDEX):
            op.drop_index(op.f(_PACKAGE_NAME_INDEX), table_name=_PACKAGE_TABLE)
        op.drop_table(_PACKAGE_TABLE)
