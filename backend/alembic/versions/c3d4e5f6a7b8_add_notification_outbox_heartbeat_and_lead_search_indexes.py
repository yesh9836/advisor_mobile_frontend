"""Add notification outbox heartbeat table and lead search indexes.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-02-20 21:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notification_outbox_worker_heartbeats",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("last_started_at", sa.DateTime(), nullable=True),
        sa.Column("last_completed_at", sa.DateTime(), nullable=True),
        sa.Column("last_success_at", sa.DateTime(), nullable=True),
        sa.Column("last_summary", sa.JSON(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_notification_outbox_worker_heartbeats_source"),
        "notification_outbox_worker_heartbeats",
        ["source"],
        unique=True,
    )
    op.create_index(
        op.f("ix_notification_outbox_worker_heartbeats_last_started_at"),
        "notification_outbox_worker_heartbeats",
        ["last_started_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notification_outbox_worker_heartbeats_last_completed_at"),
        "notification_outbox_worker_heartbeats",
        ["last_completed_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notification_outbox_worker_heartbeats_last_success_at"),
        "notification_outbox_worker_heartbeats",
        ["last_success_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notification_outbox_worker_heartbeats_created_at"),
        "notification_outbox_worker_heartbeats",
        ["created_at"],
        unique=False,
    )

    op.create_index(op.f("ix_leads_source"), "leads", ["source"], unique=False)
    op.create_index(op.f("ix_leads_first_name"), "leads", ["first_name"], unique=False)
    op.create_index(op.f("ix_leads_last_name"), "leads", ["last_name"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_leads_last_name"), table_name="leads")
    op.drop_index(op.f("ix_leads_first_name"), table_name="leads")
    op.drop_index(op.f("ix_leads_source"), table_name="leads")

    op.drop_index(
        op.f("ix_notification_outbox_worker_heartbeats_created_at"),
        table_name="notification_outbox_worker_heartbeats",
    )
    op.drop_index(
        op.f("ix_notification_outbox_worker_heartbeats_last_success_at"),
        table_name="notification_outbox_worker_heartbeats",
    )
    op.drop_index(
        op.f("ix_notification_outbox_worker_heartbeats_last_completed_at"),
        table_name="notification_outbox_worker_heartbeats",
    )
    op.drop_index(
        op.f("ix_notification_outbox_worker_heartbeats_last_started_at"),
        table_name="notification_outbox_worker_heartbeats",
    )
    op.drop_index(
        op.f("ix_notification_outbox_worker_heartbeats_source"),
        table_name="notification_outbox_worker_heartbeats",
    )
    op.drop_table("notification_outbox_worker_heartbeats")
