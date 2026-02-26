"""Add replacement credit movement type to lead credit ledger enum.

Revision ID: e4f5a6b7c8d9
Revises: e3f4a5b6c7d8
Create Date: 2026-02-26 18:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e4f5a6b7c8d9"
down_revision: Union[str, None] = "e3f4a5b6c7d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_OLD_MOVEMENTS = (
    "purchase_grant",
    "lead_consumed",
    "refund_adjustment",
    "admin_adjustment",
)

_NEW_MOVEMENTS = (
    "purchase_grant",
    "lead_consumed",
    "refund_adjustment",
    "replacement_credit",
    "admin_adjustment",
)


def upgrade() -> None:
    with op.batch_alter_table("lead_credit_ledger") as batch_op:
        batch_op.alter_column(
            "movement_type",
            existing_type=sa.Enum(*_OLD_MOVEMENTS, name="lead_credit_movement_type_enum"),
            type_=sa.Enum(*_NEW_MOVEMENTS, name="lead_credit_movement_type_enum"),
            existing_nullable=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    existing_replacement_row = bind.execute(
        sa.text(
            "SELECT id FROM lead_credit_ledger "
            "WHERE movement_type = 'replacement_credit' "
            "LIMIT 1"
        )
    ).mappings().first()
    if existing_replacement_row:
        raise RuntimeError(
            (
                "Downgrade blocked: found lead_credit_ledger row using "
                "'replacement_credit' movement_type."
            )
        )

    with op.batch_alter_table("lead_credit_ledger") as batch_op:
        batch_op.alter_column(
            "movement_type",
            existing_type=sa.Enum(*_NEW_MOVEMENTS, name="lead_credit_movement_type_enum"),
            type_=sa.Enum(*_OLD_MOVEMENTS, name="lead_credit_movement_type_enum"),
            existing_nullable=False,
        )
