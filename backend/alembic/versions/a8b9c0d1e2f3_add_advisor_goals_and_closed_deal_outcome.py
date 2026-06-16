"""Add advisor goals and closed deal lead outcome.

Revision ID: a8b9c0d1e2f3
Revises: a5b6c7d8e9f0
Create Date: 2026-06-09 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a8b9c0d1e2f3"
down_revision: Union[str, None] = "a5b6c7d8e9f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_OLD_OUTCOMES = ("new", "contacted", "appointment_set")
_NEW_OUTCOMES = ("new", "contacted", "appointment_set", "closed_deal")


def upgrade() -> None:
    op.create_table(
        "advisor_goals",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("target_year", sa.Integer(), nullable=False),
        sa.Column("annual_income_goal_cents", sa.Integer(), nullable=False),
        sa.Column("average_commission_cents", sa.Integer(), nullable=False),
        sa.Column("earned_ytd_cents", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("appointment_to_deal_rate_bps", sa.Integer(), nullable=False),
        sa.Column("lead_to_appointment_rate_bps", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "annual_income_goal_cents > 0",
            name="ck_advisor_goals_annual_income_positive",
        ),
        sa.CheckConstraint(
            "appointment_to_deal_rate_bps >= 1 AND appointment_to_deal_rate_bps <= 10000",
            name="ck_advisor_goals_appointment_to_deal_rate",
        ),
        sa.CheckConstraint(
            "average_commission_cents > 0",
            name="ck_advisor_goals_average_commission_positive",
        ),
        sa.CheckConstraint(
            "earned_ytd_cents >= 0",
            name="ck_advisor_goals_earned_ytd_non_negative",
        ),
        sa.CheckConstraint(
            "lead_to_appointment_rate_bps >= 1 AND lead_to_appointment_rate_bps <= 10000",
            name="ck_advisor_goals_lead_to_appointment_rate",
        ),
        sa.CheckConstraint(
            "target_year >= 2000 AND target_year <= 2100",
            name="ck_advisor_goals_target_year",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], onupdate="CASCADE", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "target_year", name="uq_advisor_goals_user_year"),
    )
    op.create_index(op.f("ix_advisor_goals_target_year"), "advisor_goals", ["target_year"], unique=False)
    op.create_index(op.f("ix_advisor_goals_user_id"), "advisor_goals", ["user_id"], unique=False)

    with op.batch_alter_table("lead_outcomes") as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=sa.Enum(*_OLD_OUTCOMES, name="lead_outcome_status_enum"),
            type_=sa.Enum(*_NEW_OUTCOMES, name="lead_outcome_status_enum"),
            existing_nullable=False,
            existing_server_default=sa.text("'new'"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    existing_closed_deal = bind.execute(
        sa.text("SELECT id FROM lead_outcomes WHERE status = 'closed_deal' LIMIT 1")
    ).mappings().first()
    if existing_closed_deal:
        raise RuntimeError(
            "Downgrade blocked: found lead_outcomes row using 'closed_deal' status."
        )

    with op.batch_alter_table("lead_outcomes") as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=sa.Enum(*_NEW_OUTCOMES, name="lead_outcome_status_enum"),
            type_=sa.Enum(*_OLD_OUTCOMES, name="lead_outcome_status_enum"),
            existing_nullable=False,
            existing_server_default=sa.text("'new'"),
        )

    op.drop_index(op.f("ix_advisor_goals_user_id"), table_name="advisor_goals")
    op.drop_index(op.f("ix_advisor_goals_target_year"), table_name="advisor_goals")
    op.drop_table("advisor_goals")
