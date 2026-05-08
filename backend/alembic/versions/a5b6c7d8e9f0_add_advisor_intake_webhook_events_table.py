"""Add advisor intake webhook events table.

Revision ID: a5b6c7d8e9f0
Revises: c4d5e6f7a8b9
Create Date: 2026-05-08 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a5b6c7d8e9f0"
down_revision: Union[str, None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "advisor_intake_webhook_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("external_entry_id", sa.String(length=120), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("status_reason", sa.Text(), nullable=True),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            onupdate="CASCADE",
            ondelete="SET NULL",
            name="fk_advisor_intake_webhook_events_user_id",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "external_entry_id",
            name="uq_advisor_intake_webhook_events_provider_entry",
        ),
    )
    op.create_index(
        op.f("ix_advisor_intake_webhook_events_provider"),
        "advisor_intake_webhook_events",
        ["provider"],
        unique=False,
    )
    op.create_index(
        op.f("ix_advisor_intake_webhook_events_external_entry_id"),
        "advisor_intake_webhook_events",
        ["external_entry_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_advisor_intake_webhook_events_email"),
        "advisor_intake_webhook_events",
        ["email"],
        unique=False,
    )
    op.create_index(
        op.f("ix_advisor_intake_webhook_events_status"),
        "advisor_intake_webhook_events",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_advisor_intake_webhook_events_user_id"),
        "advisor_intake_webhook_events",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_advisor_intake_webhook_events_created_at"),
        "advisor_intake_webhook_events",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_advisor_intake_webhook_events_created_at"), table_name="advisor_intake_webhook_events")
    op.drop_index(op.f("ix_advisor_intake_webhook_events_user_id"), table_name="advisor_intake_webhook_events")
    op.drop_index(op.f("ix_advisor_intake_webhook_events_status"), table_name="advisor_intake_webhook_events")
    op.drop_index(op.f("ix_advisor_intake_webhook_events_email"), table_name="advisor_intake_webhook_events")
    op.drop_index(
        op.f("ix_advisor_intake_webhook_events_external_entry_id"),
        table_name="advisor_intake_webhook_events",
    )
    op.drop_index(op.f("ix_advisor_intake_webhook_events_provider"), table_name="advisor_intake_webhook_events")
    op.drop_table("advisor_intake_webhook_events")
