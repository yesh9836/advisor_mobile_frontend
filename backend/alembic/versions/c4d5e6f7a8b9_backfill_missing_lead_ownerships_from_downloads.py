"""Backfill missing lead ownership rows from historic lead downloads.

Revision ID: c4d5e6f7a8b9
Revises: c0e1f2a3b4c5
Create Date: 2026-03-03 15:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, None] = "c0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Backfill only leads that still have no ownership record, selecting a deterministic
    # winner per lead from historic download rows (earliest downloaded_at, then lowest id).
    op.execute(
        sa.text(
            """
            INSERT INTO lead_ownerships (user_id, lead_id, purchase_id, assigned_at)
            SELECT
                ld.user_id,
                ld.lead_id,
                ld.purchase_id,
                COALESCE(ld.downloaded_at, CURRENT_TIMESTAMP)
            FROM lead_downloads AS ld
            LEFT JOIN lead_ownerships AS existing_owner
                ON existing_owner.lead_id = ld.lead_id
            WHERE existing_owner.id IS NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM lead_downloads AS earlier
                  WHERE earlier.lead_id = ld.lead_id
                    AND (
                        earlier.downloaded_at < ld.downloaded_at
                        OR (
                            earlier.downloaded_at = ld.downloaded_at
                            AND earlier.id < ld.id
                        )
                    )
              )
            """
        )
    )


def downgrade() -> None:
    # Irreversible data backfill: intentionally no-op to avoid deleting valid ownership rows.
    pass
