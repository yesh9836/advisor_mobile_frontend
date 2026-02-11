"""Enforce unique user/lead deliveries in lead_downloads.

Revision ID: d2c1f9e4b6aa
Revises: a4f2e7d91c3b
Create Date: 2026-02-11 13:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d2c1f9e4b6aa"
down_revision: Union[str, None] = "a4f2e7d91c3b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _deduplicate_lead_downloads_mysql() -> None:
    op.execute(
        sa.text(
            """
            DELETE newer
            FROM lead_downloads AS newer
            INNER JOIN lead_downloads AS existing
                ON newer.user_id = existing.user_id
                AND newer.lead_id = existing.lead_id
                AND newer.id > existing.id
            """
        )
    )


def upgrade() -> None:
    _deduplicate_lead_downloads_mysql()

    op.create_unique_constraint(
        "uq_lead_downloads_user_lead",
        "lead_downloads",
        ["user_id", "lead_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_lead_downloads_user_lead", "lead_downloads", type_="unique")
