"""Add configurable add-on price and credits fields.

Revision ID: f3a4b5c6d7e8
Revises: f2d3e4c5b6a7
Create Date: 2026-02-19 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f3a4b5c6d7e8"
down_revision: Union[str, None] = "f2d3e4c5b6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("first_purchase_addon_offers") as batch_op:
        batch_op.add_column(sa.Column("offer_credits_total", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("offer_price_cents", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "offer_currency",
                sa.String(length=3),
                nullable=False,
                server_default=sa.text("'USD'"),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("first_purchase_addon_offers") as batch_op:
        batch_op.drop_column("offer_currency")
        batch_op.drop_column("offer_price_cents")
        batch_op.drop_column("offer_credits_total")
