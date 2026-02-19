"""Add notification outbox table.

Revision ID: f5c6d7e8f9a0
Revises: f4b5c6d7e8f9
Create Date: 2026-02-19 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f5c6d7e8f9a0"
down_revision: Union[str, None] = "f4b5c6d7e8f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notification_outbox",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("lead_id", sa.BigInteger(), nullable=True),
        sa.Column("purchase_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "channel",
            sa.Enum("email", "sms", name="notification_channel_enum"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("recipient", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=True),
        sa.Column("message_body", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=191), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "processing", "sent", "failed", name="notification_status_enum"),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("attempt_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default=sa.text("5"), nullable=False),
        sa.Column("next_retry_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("locked_at", sa.DateTime(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("provider_message_id", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], onupdate="CASCADE", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["purchase_id"], ["lead_purchases.id"], onupdate="CASCADE", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], onupdate="CASCADE", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(op.f("ix_notification_outbox_user_id"), "notification_outbox", ["user_id"], unique=False)
    op.create_index(op.f("ix_notification_outbox_lead_id"), "notification_outbox", ["lead_id"], unique=False)
    op.create_index(op.f("ix_notification_outbox_purchase_id"), "notification_outbox", ["purchase_id"], unique=False)
    op.create_index(op.f("ix_notification_outbox_channel"), "notification_outbox", ["channel"], unique=False)
    op.create_index(op.f("ix_notification_outbox_event_type"), "notification_outbox", ["event_type"], unique=False)
    op.create_index(op.f("ix_notification_outbox_status"), "notification_outbox", ["status"], unique=False)
    op.create_index(
        op.f("ix_notification_outbox_idempotency_key"),
        "notification_outbox",
        ["idempotency_key"],
        unique=True,
    )
    op.create_index(op.f("ix_notification_outbox_next_retry_at"), "notification_outbox", ["next_retry_at"], unique=False)
    op.create_index(op.f("ix_notification_outbox_locked_at"), "notification_outbox", ["locked_at"], unique=False)
    op.create_index(op.f("ix_notification_outbox_sent_at"), "notification_outbox", ["sent_at"], unique=False)
    op.create_index(
        "ix_notification_outbox_status_retry",
        "notification_outbox",
        ["status", "next_retry_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_notification_outbox_status_retry", table_name="notification_outbox")
    op.drop_index(op.f("ix_notification_outbox_sent_at"), table_name="notification_outbox")
    op.drop_index(op.f("ix_notification_outbox_locked_at"), table_name="notification_outbox")
    op.drop_index(op.f("ix_notification_outbox_next_retry_at"), table_name="notification_outbox")
    op.drop_index(op.f("ix_notification_outbox_idempotency_key"), table_name="notification_outbox")
    op.drop_index(op.f("ix_notification_outbox_status"), table_name="notification_outbox")
    op.drop_index(op.f("ix_notification_outbox_event_type"), table_name="notification_outbox")
    op.drop_index(op.f("ix_notification_outbox_channel"), table_name="notification_outbox")
    op.drop_index(op.f("ix_notification_outbox_purchase_id"), table_name="notification_outbox")
    op.drop_index(op.f("ix_notification_outbox_lead_id"), table_name="notification_outbox")
    op.drop_index(op.f("ix_notification_outbox_user_id"), table_name="notification_outbox")
    op.drop_table("notification_outbox")

