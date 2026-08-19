"""Add selected target states to lead purchases.

Revision ID: d0e1f2a3b4c6
Revises: a8b9c0d1e2f3
Create Date: 2026-08-09 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d0e1f2a3b4c6"
down_revision: Union[str, None] = "a8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("lead_purchases", sa.Column("target_states", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("lead_purchases", "target_states")
