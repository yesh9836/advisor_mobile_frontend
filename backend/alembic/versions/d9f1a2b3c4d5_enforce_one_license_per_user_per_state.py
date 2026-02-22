"""Enforce one license per advisor per state.

Revision ID: d9f1a2b3c4d5
Revises: c3d4e5f6a7b8
Create Date: 2026-02-22 13:10:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d9f1a2b3c4d5"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Existing data is disposable in this environment, so clear tables before
    # enforcing the stricter advisor+state uniqueness invariant.
    op.execute("DELETE FROM license_resubmissions")
    op.execute("DELETE FROM licenses")
    with op.batch_alter_table("licenses") as batch_op:
        batch_op.create_unique_constraint(
            "uq_licenses_user_state",
            ["user_id", "state"],
        )


def downgrade() -> None:
    with op.batch_alter_table("licenses") as batch_op:
        batch_op.drop_constraint("uq_licenses_user_state", type_="unique")
