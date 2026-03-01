"""Add lead intake webhook idempotency table.

Revision ID: c0e1f2a3b4c5
Revises: b9c0d1e2f3a4
Create Date: 2026-03-01 11:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c0e1f2a3b4c5"
down_revision: Union[str, None] = "b9c0d1e2f3a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lead_intake_webhook_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("external_entry_id", sa.String(length=120), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=True),
        sa.Column("lead_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["lead_id"],
            ["leads.id"],
            onupdate="CASCADE",
            ondelete="SET NULL",
            name="fk_lead_intake_webhook_events_lead_id",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "external_entry_id",
            name="uq_lead_intake_webhook_events_provider_entry",
        ),
    )
    op.create_index(
        op.f("ix_lead_intake_webhook_events_provider"),
        "lead_intake_webhook_events",
        ["provider"],
        unique=False,
    )
    op.create_index(
        op.f("ix_lead_intake_webhook_events_external_entry_id"),
        "lead_intake_webhook_events",
        ["external_entry_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_lead_intake_webhook_events_lead_id"),
        "lead_intake_webhook_events",
        ["lead_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_lead_intake_webhook_events_created_at"),
        "lead_intake_webhook_events",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_lead_intake_webhook_events_created_at"),
        table_name="lead_intake_webhook_events",
    )
    op.drop_index(
        op.f("ix_lead_intake_webhook_events_lead_id"),
        table_name="lead_intake_webhook_events",
    )
    op.drop_index(
        op.f("ix_lead_intake_webhook_events_external_entry_id"),
        table_name="lead_intake_webhook_events",
    )
    op.drop_index(
        op.f("ix_lead_intake_webhook_events_provider"),
        table_name="lead_intake_webhook_events",
    )
    op.drop_table("lead_intake_webhook_events")
