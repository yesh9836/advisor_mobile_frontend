"""Add reviewed metadata columns to licenses

Revision ID: 4e2ad347ac11
Revises: c9f6d4a6f2b1
Create Date: 2026-02-10 18:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4e2ad347ac11"
down_revision: Union[str, None] = "c9f6d4a6f2b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("licenses", sa.Column("reviewed_by", sa.BigInteger(), nullable=True))
    op.add_column("licenses", sa.Column("reviewed_at", sa.DateTime(), nullable=True))
    op.create_index(op.f("ix_licenses_reviewed_by"), "licenses", ["reviewed_by"], unique=False)
    op.create_foreign_key(
        "fk_licenses_reviewed_by_users",
        "licenses",
        "users",
        ["reviewed_by"],
        ["id"],
        onupdate="CASCADE",
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_licenses_reviewed_by_users", "licenses", type_="foreignkey")
    op.drop_index(op.f("ix_licenses_reviewed_by"), table_name="licenses")
    op.drop_column("licenses", "reviewed_at")
    op.drop_column("licenses", "reviewed_by")
