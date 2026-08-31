"""Add persisted advisor onboarding inputs and completion state.

Revision ID: d1e2f3a4b5c7
Revises: d0e1f2a3b4c6
Create Date: 2026-08-30 18:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d1e2f3a4b5c7"
down_revision: Union[str, None] = "d0e1f2a3b4c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "advisor_goals",
        sa.Column("average_sale_cents", sa.Integer(), nullable=True),
    )
    op.add_column(
        "advisor_goals",
        sa.Column("commission_rate_bps", sa.Integer(), nullable=True),
    )
    op.add_column(
        "advisor_goals",
        sa.Column("onboarding_completed_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "advisor_goals",
        sa.Column("onboarding_consent_at", sa.DateTime(), nullable=True),
    )

    # Existing advisors already using the application must not be forced back
    # through a newly introduced mandatory flow. Preserve their derived average
    # commission with a conventional 20% commission assumption.
    op.execute(
        "UPDATE advisor_goals SET "
        "average_sale_cents = average_commission_cents * 5, "
        "commission_rate_bps = 2000, "
        "onboarding_completed_at = updated_at, "
        "onboarding_consent_at = updated_at"
    )


def downgrade() -> None:
    op.drop_column("advisor_goals", "onboarding_consent_at")
    op.drop_column("advisor_goals", "onboarding_completed_at")
    op.drop_column("advisor_goals", "commission_rate_bps")
    op.drop_column("advisor_goals", "average_sale_cents")
