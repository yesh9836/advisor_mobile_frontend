"""Add stripe invoice ID to lead purchases.

Revision ID: a1d2e3f4b5c6
Revises: e1b2c3d4e5f6
Create Date: 2026-02-20 17:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1d2e3f4b5c6"
down_revision: Union[str, None] = "e1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("lead_purchases", sa.Column("stripe_invoice_id", sa.String(length=100), nullable=True))
    op.create_index(
        op.f("ix_lead_purchases_stripe_invoice_id"),
        "lead_purchases",
        ["stripe_invoice_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_lead_purchases_stripe_invoice_id"), table_name="lead_purchases")
    op.drop_column("lead_purchases", "stripe_invoice_id")
