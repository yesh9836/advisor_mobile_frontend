"""Normalize timestamp columns to UTC-safe MySQL TIMESTAMP

Revision ID: a4f2e7d91c3b
Revises: 4e2ad347ac11
Create Date: 2026-02-10 21:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


# revision identifiers, used by Alembic.
revision: str = "a4f2e7d91c3b"
down_revision: Union[str, None] = "4e2ad347ac11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _to_timestamp() -> None:
    op.execute("SET time_zone = '+00:00'")

    op.alter_column(
        "leads",
        "created_at",
        existing_type=sa.DateTime(),
        type_=mysql.TIMESTAMP(),
        existing_nullable=False,
        existing_server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    op.alter_column(
        "leads",
        "updated_at",
        existing_type=sa.DateTime(),
        type_=mysql.TIMESTAMP(),
        existing_nullable=False,
        existing_server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )
    op.alter_column(
        "subscription_plans",
        "created_at",
        existing_type=sa.DateTime(),
        type_=mysql.TIMESTAMP(),
        existing_nullable=False,
        existing_server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    op.alter_column(
        "users",
        "created_at",
        existing_type=sa.DateTime(),
        type_=mysql.TIMESTAMP(),
        existing_nullable=False,
        existing_server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    op.alter_column(
        "audit_logs",
        "created_at",
        existing_type=sa.DateTime(),
        type_=mysql.TIMESTAMP(),
        existing_nullable=False,
        existing_server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    op.alter_column(
        "lead_downloads",
        "downloaded_at",
        existing_type=sa.DateTime(),
        type_=mysql.TIMESTAMP(),
        existing_nullable=False,
        existing_server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    op.alter_column(
        "licenses",
        "verified_at",
        existing_type=sa.DateTime(),
        type_=mysql.TIMESTAMP(),
        existing_nullable=True,
        existing_server_default=None,
    )
    op.alter_column(
        "licenses",
        "reviewed_at",
        existing_type=sa.DateTime(),
        type_=mysql.TIMESTAMP(),
        existing_nullable=True,
        existing_server_default=None,
    )
    op.alter_column(
        "licenses",
        "created_at",
        existing_type=sa.DateTime(),
        type_=mysql.TIMESTAMP(),
        existing_nullable=False,
        existing_server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    op.alter_column(
        "subscriptions",
        "current_period_start",
        existing_type=sa.DateTime(),
        type_=mysql.TIMESTAMP(),
        existing_nullable=True,
        existing_server_default=None,
    )
    op.alter_column(
        "subscriptions",
        "current_period_end",
        existing_type=sa.DateTime(),
        type_=mysql.TIMESTAMP(),
        existing_nullable=True,
        existing_server_default=None,
    )
    op.alter_column(
        "subscriptions",
        "created_at",
        existing_type=sa.DateTime(),
        type_=mysql.TIMESTAMP(),
        existing_nullable=False,
        existing_server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    op.alter_column(
        "lead_outcomes",
        "created_at",
        existing_type=sa.DateTime(),
        type_=mysql.TIMESTAMP(),
        existing_nullable=False,
        existing_server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    op.alter_column(
        "lead_outcomes",
        "updated_at",
        existing_type=sa.DateTime(),
        type_=mysql.TIMESTAMP(),
        existing_nullable=False,
        existing_server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )
    op.alter_column(
        "license_resubmissions",
        "attempted_at",
        existing_type=sa.DateTime(),
        type_=mysql.TIMESTAMP(),
        existing_nullable=False,
        existing_server_default=sa.text("CURRENT_TIMESTAMP"),
    )


def _to_datetime() -> None:
    op.execute("SET time_zone = '+00:00'")

    op.alter_column(
        "leads",
        "created_at",
        existing_type=mysql.TIMESTAMP(),
        type_=sa.DateTime(),
        existing_nullable=False,
        existing_server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    op.alter_column(
        "leads",
        "updated_at",
        existing_type=mysql.TIMESTAMP(),
        type_=sa.DateTime(),
        existing_nullable=False,
        existing_server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )
    op.alter_column(
        "subscription_plans",
        "created_at",
        existing_type=mysql.TIMESTAMP(),
        type_=sa.DateTime(),
        existing_nullable=False,
        existing_server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    op.alter_column(
        "users",
        "created_at",
        existing_type=mysql.TIMESTAMP(),
        type_=sa.DateTime(),
        existing_nullable=False,
        existing_server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    op.alter_column(
        "audit_logs",
        "created_at",
        existing_type=mysql.TIMESTAMP(),
        type_=sa.DateTime(),
        existing_nullable=False,
        existing_server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    op.alter_column(
        "lead_downloads",
        "downloaded_at",
        existing_type=mysql.TIMESTAMP(),
        type_=sa.DateTime(),
        existing_nullable=False,
        existing_server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    op.alter_column(
        "licenses",
        "verified_at",
        existing_type=mysql.TIMESTAMP(),
        type_=sa.DateTime(),
        existing_nullable=True,
        existing_server_default=None,
    )
    op.alter_column(
        "licenses",
        "reviewed_at",
        existing_type=mysql.TIMESTAMP(),
        type_=sa.DateTime(),
        existing_nullable=True,
        existing_server_default=None,
    )
    op.alter_column(
        "licenses",
        "created_at",
        existing_type=mysql.TIMESTAMP(),
        type_=sa.DateTime(),
        existing_nullable=False,
        existing_server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    op.alter_column(
        "subscriptions",
        "current_period_start",
        existing_type=mysql.TIMESTAMP(),
        type_=sa.DateTime(),
        existing_nullable=True,
        existing_server_default=None,
    )
    op.alter_column(
        "subscriptions",
        "current_period_end",
        existing_type=mysql.TIMESTAMP(),
        type_=sa.DateTime(),
        existing_nullable=True,
        existing_server_default=None,
    )
    op.alter_column(
        "subscriptions",
        "created_at",
        existing_type=mysql.TIMESTAMP(),
        type_=sa.DateTime(),
        existing_nullable=False,
        existing_server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    op.alter_column(
        "lead_outcomes",
        "created_at",
        existing_type=mysql.TIMESTAMP(),
        type_=sa.DateTime(),
        existing_nullable=False,
        existing_server_default=sa.text("CURRENT_TIMESTAMP"),
    )
    op.alter_column(
        "lead_outcomes",
        "updated_at",
        existing_type=mysql.TIMESTAMP(),
        type_=sa.DateTime(),
        existing_nullable=False,
        existing_server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )
    op.alter_column(
        "license_resubmissions",
        "attempted_at",
        existing_type=mysql.TIMESTAMP(),
        type_=sa.DateTime(),
        existing_nullable=False,
        existing_server_default=sa.text("CURRENT_TIMESTAMP"),
    )


def upgrade() -> None:
    _to_timestamp()


def downgrade() -> None:
    _to_datetime()
