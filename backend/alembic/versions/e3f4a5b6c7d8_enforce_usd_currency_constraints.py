"""Enforce USD-only currency constraints for purchase pricing tables.

Revision ID: e3f4a5b6c7d8
Revises: d9f1a2b3c4d5
Create Date: 2026-02-26 17:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e3f4a5b6c7d8"
down_revision: Union[str, None] = "d9f1a2b3c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _check_constraint_exists(table_name: str, constraint_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(
        (constraint.get("name") == constraint_name)
        for constraint in inspector.get_check_constraints(table_name)
    )


def _assert_no_non_usd_rows() -> None:
    connection = op.get_bind()
    checks = (
        ("lead_packages", "currency"),
        ("lead_purchases", "currency"),
        ("first_purchase_addon_offers", "offer_currency"),
    )

    for table_name, column_name in checks:
        row = connection.execute(
            sa.text(
                f"SELECT id, {column_name} AS currency_value "
                f"FROM {table_name} "
                f"WHERE {column_name} <> 'USD' "
                "LIMIT 1"
            )
        ).mappings().first()
        if row:
            raise RuntimeError(
                (
                    "USD-only migration blocked: found non-USD currency in "
                    f"{table_name} (id={row['id']}, value={row['currency_value']}). "
                    "Remediate data explicitly before rerunning migration."
                )
            )


def upgrade() -> None:
    _assert_no_non_usd_rows()

    if not _check_constraint_exists("lead_packages", "ck_lead_packages_currency_usd"):
        with op.batch_alter_table("lead_packages") as batch_op:
            batch_op.create_check_constraint(
                "ck_lead_packages_currency_usd",
                "currency = 'USD'",
            )

    if not _check_constraint_exists("lead_purchases", "ck_lead_purchases_currency_usd"):
        with op.batch_alter_table("lead_purchases") as batch_op:
            batch_op.create_check_constraint(
                "ck_lead_purchases_currency_usd",
                "currency = 'USD'",
            )

    if not _check_constraint_exists(
        "first_purchase_addon_offers",
        "ck_first_purchase_addon_offers_offer_currency_usd",
    ):
        with op.batch_alter_table("first_purchase_addon_offers") as batch_op:
            batch_op.create_check_constraint(
                "ck_first_purchase_addon_offers_offer_currency_usd",
                "offer_currency = 'USD'",
            )


def downgrade() -> None:
    if _check_constraint_exists(
        "first_purchase_addon_offers",
        "ck_first_purchase_addon_offers_offer_currency_usd",
    ):
        with op.batch_alter_table("first_purchase_addon_offers") as batch_op:
            batch_op.drop_constraint("ck_first_purchase_addon_offers_offer_currency_usd", type_="check")

    if _check_constraint_exists("lead_purchases", "ck_lead_purchases_currency_usd"):
        with op.batch_alter_table("lead_purchases") as batch_op:
            batch_op.drop_constraint("ck_lead_purchases_currency_usd", type_="check")

    if _check_constraint_exists("lead_packages", "ck_lead_packages_currency_usd"):
        with op.batch_alter_table("lead_packages") as batch_op:
            batch_op.drop_constraint("ck_lead_packages_currency_usd", type_="check")
