"""Add first-purchase add-on offer config table.

Revision ID: f2d3e4c5b6a7
Revises: b8e1f2a3c4d5
Create Date: 2026-02-19 10:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f2d3e4c5b6a7"
down_revision: Union[str, None] = "b8e1f2a3c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "first_purchase_addon_offers",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("trigger_package_id", sa.BigInteger(), nullable=True),
        sa.Column("offer_package_id", sa.BigInteger(), nullable=True),
        sa.Column("headline", sa.String(length=120), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("cta_label", sa.String(length=80), nullable=True),
        sa.Column("starts_at", sa.DateTime(), nullable=True),
        sa.Column("ends_at", sa.DateTime(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(
            ["offer_package_id"],
            ["lead_packages.id"],
            onupdate="CASCADE",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["trigger_package_id"],
            ["lead_packages.id"],
            onupdate="CASCADE",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
            onupdate="CASCADE",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        op.f("ix_first_purchase_addon_offers_is_enabled"),
        "first_purchase_addon_offers",
        ["is_enabled"],
        unique=False,
    )
    op.create_index(
        op.f("ix_first_purchase_addon_offers_trigger_package_id"),
        "first_purchase_addon_offers",
        ["trigger_package_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_first_purchase_addon_offers_offer_package_id"),
        "first_purchase_addon_offers",
        ["offer_package_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_first_purchase_addon_offers_starts_at"),
        "first_purchase_addon_offers",
        ["starts_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_first_purchase_addon_offers_ends_at"),
        "first_purchase_addon_offers",
        ["ends_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_first_purchase_addon_offers_updated_by"),
        "first_purchase_addon_offers",
        ["updated_by"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_first_purchase_addon_offers_updated_by"), table_name="first_purchase_addon_offers")
    op.drop_index(op.f("ix_first_purchase_addon_offers_ends_at"), table_name="first_purchase_addon_offers")
    op.drop_index(op.f("ix_first_purchase_addon_offers_starts_at"), table_name="first_purchase_addon_offers")
    op.drop_index(op.f("ix_first_purchase_addon_offers_offer_package_id"), table_name="first_purchase_addon_offers")
    op.drop_index(op.f("ix_first_purchase_addon_offers_trigger_package_id"), table_name="first_purchase_addon_offers")
    op.drop_index(op.f("ix_first_purchase_addon_offers_is_enabled"), table_name="first_purchase_addon_offers")
    op.drop_table("first_purchase_addon_offers")
