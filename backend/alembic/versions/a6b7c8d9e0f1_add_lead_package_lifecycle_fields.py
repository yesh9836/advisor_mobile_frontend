"""Add lead package lifecycle and effective-window fields.

Revision ID: a6b7c8d9e0f1
Revises: e4f5a6b7c8d9
Create Date: 2026-02-26 20:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a6b7c8d9e0f1"
down_revision: Union[str, None] = "e4f5a6b7c8d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(column.get("name") == column_name for column in inspector.get_columns(table_name))


def _index_exists(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(index.get("name") == index_name for index in inspector.get_indexes(table_name))


def _check_constraint_exists(table_name: str, constraint_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(
        constraint.get("name") == constraint_name
        for constraint in inspector.get_check_constraints(table_name)
    )


def _get_fk_name(
    table_name: str,
    *,
    constrained_column: str,
    referred_table: str,
) -> Union[str, None]:
    inspector = sa.inspect(op.get_bind())
    for fk in inspector.get_foreign_keys(table_name):
        constrained_columns = fk.get("constrained_columns") or []
        if fk.get("referred_table") == referred_table and constrained_column in constrained_columns:
            return fk.get("name")
    return None


def upgrade() -> None:
    with op.batch_alter_table("lead_packages") as batch_op:
        if not _column_exists("lead_packages", "stripe_product_id"):
            batch_op.add_column(sa.Column("stripe_product_id", sa.String(length=100), nullable=True))
        if not _column_exists("lead_packages", "effective_from"):
            batch_op.add_column(sa.Column("effective_from", sa.DateTime(), nullable=True))
        if not _column_exists("lead_packages", "effective_to"):
            batch_op.add_column(sa.Column("effective_to", sa.DateTime(), nullable=True))
        if not _column_exists("lead_packages", "is_archived"):
            batch_op.add_column(
                sa.Column(
                    "is_archived",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text("0"),
                )
            )
        if not _column_exists("lead_packages", "archived_at"):
            batch_op.add_column(sa.Column("archived_at", sa.DateTime(), nullable=True))
        if not _column_exists("lead_packages", "updated_by"):
            batch_op.add_column(sa.Column("updated_by", sa.BigInteger(), nullable=True))
        if not _column_exists("lead_packages", "updated_at"):
            batch_op.add_column(
                sa.Column(
                    "updated_at",
                    sa.DateTime(),
                    nullable=False,
                    server_default=sa.text("CURRENT_TIMESTAMP"),
                )
            )

    fk_name = _get_fk_name(
        "lead_packages",
        constrained_column="updated_by",
        referred_table="users",
    )
    if fk_name is None and _column_exists("lead_packages", "updated_by"):
        with op.batch_alter_table("lead_packages") as batch_op:
            batch_op.create_foreign_key(
                "fk_lead_packages_updated_by_users",
                "users",
                ["updated_by"],
                ["id"],
                onupdate="CASCADE",
                ondelete="SET NULL",
            )

    lifecycle_indexes = (
        ("ix_lead_packages_stripe_product_id", ["stripe_product_id"]),
        ("ix_lead_packages_effective_from", ["effective_from"]),
        ("ix_lead_packages_effective_to", ["effective_to"]),
        ("ix_lead_packages_is_archived", ["is_archived"]),
        ("ix_lead_packages_archived_at", ["archived_at"]),
        ("ix_lead_packages_updated_by", ["updated_by"]),
    )
    for index_name, columns in lifecycle_indexes:
        if not _index_exists("lead_packages", index_name):
            op.create_index(index_name, "lead_packages", columns, unique=False)

    if not _check_constraint_exists("lead_packages", "ck_lead_packages_effective_window_valid"):
        with op.batch_alter_table("lead_packages") as batch_op:
            batch_op.create_check_constraint(
                "ck_lead_packages_effective_window_valid",
                "effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from",
            )

    if not _check_constraint_exists("lead_packages", "ck_lead_packages_archive_consistency"):
        with op.batch_alter_table("lead_packages") as batch_op:
            batch_op.create_check_constraint(
                "ck_lead_packages_archive_consistency",
                "(is_archived = 0 AND archived_at IS NULL) OR (is_archived = 1 AND archived_at IS NOT NULL)",
            )


def downgrade() -> None:
    if _check_constraint_exists("lead_packages", "ck_lead_packages_archive_consistency"):
        with op.batch_alter_table("lead_packages") as batch_op:
            batch_op.drop_constraint("ck_lead_packages_archive_consistency", type_="check")

    if _check_constraint_exists("lead_packages", "ck_lead_packages_effective_window_valid"):
        with op.batch_alter_table("lead_packages") as batch_op:
            batch_op.drop_constraint("ck_lead_packages_effective_window_valid", type_="check")

    for index_name in (
        "ix_lead_packages_updated_by",
        "ix_lead_packages_archived_at",
        "ix_lead_packages_is_archived",
        "ix_lead_packages_effective_to",
        "ix_lead_packages_effective_from",
        "ix_lead_packages_stripe_product_id",
    ):
        if _index_exists("lead_packages", index_name):
            op.drop_index(index_name, table_name="lead_packages")

    fk_name = _get_fk_name(
        "lead_packages",
        constrained_column="updated_by",
        referred_table="users",
    )
    if fk_name:
        with op.batch_alter_table("lead_packages") as batch_op:
            batch_op.drop_constraint(fk_name, type_="foreignkey")

    with op.batch_alter_table("lead_packages") as batch_op:
        if _column_exists("lead_packages", "updated_at"):
            batch_op.drop_column("updated_at")
        if _column_exists("lead_packages", "updated_by"):
            batch_op.drop_column("updated_by")
        if _column_exists("lead_packages", "archived_at"):
            batch_op.drop_column("archived_at")
        if _column_exists("lead_packages", "is_archived"):
            batch_op.drop_column("is_archived")
        if _column_exists("lead_packages", "effective_to"):
            batch_op.drop_column("effective_to")
        if _column_exists("lead_packages", "effective_from"):
            batch_op.drop_column("effective_from")
        if _column_exists("lead_packages", "stripe_product_id"):
            batch_op.drop_column("stripe_product_id")
