from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.exc import IntegrityError


def _load_migration_module(filename: str) -> ModuleType:
    versions_dir = Path(__file__).resolve().parents[1] / "alembic" / "versions"
    module_path = versions_dir / filename
    spec = importlib.util.spec_from_file_location(f"test_migration_{filename.replace('.', '_')}", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run_migration(module: ModuleType, fn_name: str, connection: sa.Connection) -> None:
    migration_context = MigrationContext.configure(connection=connection)
    operations = Operations(migration_context)
    original_op = module.op
    module.op = operations
    try:
        getattr(module, fn_name)()
    finally:
        module.op = original_op


@pytest.mark.unit
def test_c1_global_unique_lead_downloads_upgrade_is_deterministic_and_rerunnable():
    migration = _load_migration_module("c1a8e9f0d7b2_enforce_global_unique_lead_downloads.py")
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")

    metadata = sa.MetaData()
    lead_downloads = sa.Table(
        "lead_downloads",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("lead_id", sa.Integer, nullable=False),
        sa.Column("downloaded_at", sa.DateTime, nullable=False),
    )

    with engine.begin() as connection:
        metadata.create_all(connection)
        connection.execute(
            lead_downloads.insert(),
            [
                # lead_id=100 winner should be id=1 (earliest downloaded_at)
                {
                    "id": 1,
                    "user_id": 101,
                    "lead_id": 100,
                    "downloaded_at": datetime(2026, 2, 10, 12, 0, tzinfo=timezone.utc),
                },
                {
                    "id": 2,
                    "user_id": 102,
                    "lead_id": 100,
                    "downloaded_at": datetime(2026, 2, 10, 12, 10, tzinfo=timezone.utc),
                },
                # lead_id=101 winner should be id=3 (same timestamp, lower id)
                {
                    "id": 3,
                    "user_id": 201,
                    "lead_id": 101,
                    "downloaded_at": datetime(2026, 2, 11, 13, 0, tzinfo=timezone.utc),
                },
                {
                    "id": 4,
                    "user_id": 202,
                    "lead_id": 101,
                    "downloaded_at": datetime(2026, 2, 11, 13, 0, tzinfo=timezone.utc),
                },
                {
                    "id": 5,
                    "user_id": 301,
                    "lead_id": 102,
                    "downloaded_at": datetime(2026, 2, 12, 14, 0, tzinfo=timezone.utc),
                },
            ],
        )

        _run_migration(migration, "upgrade", connection)
        _run_migration(migration, "upgrade", connection)

        survivors = connection.execute(
            sa.text(
                "SELECT id, user_id, lead_id FROM lead_downloads ORDER BY lead_id ASC"
            )
        ).mappings().all()
        assert survivors == [
            {"id": 1, "user_id": 101, "lead_id": 100},
            {"id": 3, "user_id": 201, "lead_id": 101},
            {"id": 5, "user_id": 301, "lead_id": 102},
        ]

        with pytest.raises(IntegrityError):
            connection.execute(
                sa.text(
                    "INSERT INTO lead_downloads (id, user_id, lead_id, downloaded_at) "
                    "VALUES (99, 999, 100, '2026-02-13 15:00:00')"
                )
            )


@pytest.mark.unit
def test_d4_lead_packages_upgrade_rerun_preserves_backfill_and_fk_integrity():
    migration = _load_migration_module("d4e5f6a7b8c9_add_lead_packages_catalog.py")
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")

    metadata = sa.MetaData()
    subscription_plans = sa.Table(
        "subscription_plans",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("price_cents", sa.Integer, nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default=sa.text("'USD'")),
        sa.Column("stripe_price_id", sa.String(100), nullable=False),
        sa.Column("state_limit", sa.Integer, nullable=True),
        sa.Column("daily_download_limit", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("features", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    lead_purchases = sa.Table(
        "lead_purchases",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("package_id", sa.Integer, nullable=False),
        sa.ForeignKeyConstraint(
            ["package_id"],
            ["subscription_plans.id"],
            name="fk_lead_purchases_package_id_subscription_plans",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
    )

    with engine.begin() as connection:
        connection.execute(sa.text("PRAGMA foreign_keys = ON"))
        metadata.create_all(connection)

        connection.execute(
            subscription_plans.insert(),
            [
                {
                    "id": 1,
                    "name": "Starter",
                    "price_cents": 10000,
                    "currency": "USD",
                    "stripe_price_id": "price_starter",
                    "state_limit": 1,
                    "daily_download_limit": 10,
                    "features": {"credits_total": 10},
                    "created_at": datetime(2026, 2, 10, 12, 0, tzinfo=timezone.utc),
                },
                {
                    "id": 2,
                    "name": "Pro",
                    "price_cents": 25000,
                    "currency": "USD",
                    "stripe_price_id": "price_pro",
                    "state_limit": 2,
                    "daily_download_limit": 25,
                    "features": {"credits_total": 25},
                    "created_at": datetime(2026, 2, 11, 12, 0, tzinfo=timezone.utc),
                },
            ],
        )
        connection.execute(
            lead_purchases.insert(),
            [
                {"id": 10, "user_id": 1001, "package_id": 1},
                {"id": 11, "user_id": 1002, "package_id": 2},
            ],
        )

        _run_migration(migration, "upgrade", connection)
        _run_migration(migration, "upgrade", connection)

        package_counts = connection.execute(
            sa.text(
                "SELECT COUNT(*) AS total, COUNT(DISTINCT id) AS distinct_ids FROM lead_packages"
            )
        ).mappings().one()
        assert package_counts["total"] == 2
        assert package_counts["distinct_ids"] == 2

        orphaned_purchases = connection.execute(
            sa.text(
                "SELECT COUNT(*) AS total FROM lead_purchases lp "
                "LEFT JOIN lead_packages p ON p.id = lp.package_id "
                "WHERE p.id IS NULL"
            )
        ).mappings().one()
        assert orphaned_purchases["total"] == 0

        inspector = sa.inspect(connection)
        purchase_fks = inspector.get_foreign_keys("lead_purchases")
        referred_tables = {fk.get("referred_table") for fk in purchase_fks}
        assert "lead_packages" in referred_tables
        assert "subscription_plans" not in referred_tables
