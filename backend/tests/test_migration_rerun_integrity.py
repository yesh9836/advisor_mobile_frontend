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
def test_f6_lead_download_audit_upgrade_is_rerunnable_and_allows_duplicate_audit_rows():
    migration = _load_migration_module("f6a7b8c9d0e1_relax_lead_download_uniqueness_for_export_audit.py")
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")

    metadata = sa.MetaData()
    lead_downloads = sa.Table(
        "lead_downloads",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("lead_id", sa.Integer, nullable=False),
        sa.Column("downloaded_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("user_id", "lead_id", name="uq_lead_downloads_user_lead"),
        sa.UniqueConstraint("lead_id", name="uq_lead_downloads_global_lead"),
    )

    with engine.begin() as connection:
        metadata.create_all(connection)
        connection.execute(
            lead_downloads.insert(),
            [
                {
                    "id": 1,
                    "user_id": 101,
                    "lead_id": 100,
                    "downloaded_at": datetime(2026, 2, 10, 12, 0, tzinfo=timezone.utc),
                },
            ],
        )

        _run_migration(migration, "upgrade", connection)
        _run_migration(migration, "upgrade", connection)

        # Duplicate rows for the same user/lead are now valid for repeated export auditing.
        connection.execute(
            sa.text(
                "INSERT INTO lead_downloads (id, user_id, lead_id, downloaded_at) "
                "VALUES (2, 101, 100, '2026-02-10 12:10:00')"
            )
        )

        duplicate_count = connection.execute(
            sa.text(
                "SELECT COUNT(*) AS total FROM lead_downloads "
                "WHERE user_id = 101 AND lead_id = 100"
            )
        ).mappings().one()
        assert duplicate_count["total"] == 2

        inspector = sa.inspect(connection)
        unique_names = {
            constraint.get("name")
            for constraint in inspector.get_unique_constraints("lead_downloads")
            if constraint.get("name")
        }
        assert "uq_lead_downloads_user_lead" not in unique_names
        assert "uq_lead_downloads_global_lead" not in unique_names

        index_names = {
            index.get("name")
            for index in inspector.get_indexes("lead_downloads")
            if index.get("name")
        }
        assert "ix_lead_downloads_user_lead" in index_names


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


@pytest.mark.unit
def test_a7_delivery_settings_upgrade_is_rerunnable_and_backfills_advisors_with_off_defaults():
    migration = _load_migration_module("a7c3d9e1f2b4_add_advisor_delivery_settings.py")
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")

    metadata = sa.MetaData()
    users = sa.Table(
        "users",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("role", sa.String(20), nullable=False),
    )

    with engine.begin() as connection:
        metadata.create_all(connection)
        connection.execute(
            users.insert(),
            [
                {"id": 1, "role": "advisor"},
                {"id": 2, "role": "admin"},
                {"id": 3, "role": "advisor"},
            ],
        )

        _run_migration(migration, "upgrade", connection)
        _run_migration(migration, "upgrade", connection)

        rows = connection.execute(
            sa.text(
                "SELECT user_id, email_alerts_enabled, sms_alerts_enabled, version "
                "FROM advisor_delivery_settings ORDER BY user_id ASC"
            )
        ).mappings().all()
        assert rows == [
            {"user_id": 1, "email_alerts_enabled": 0, "sms_alerts_enabled": 0, "version": 1},
            {"user_id": 3, "email_alerts_enabled": 0, "sms_alerts_enabled": 0, "version": 1},
        ]

        with pytest.raises(IntegrityError):
            connection.execute(
                sa.text(
                    "INSERT INTO advisor_delivery_settings (user_id, email_alerts_enabled, sms_alerts_enabled, version) "
                    "VALUES (1, 1, 1, 1)"
                )
            )


@pytest.mark.unit
def test_b8_drop_legacy_subscription_tables_upgrade_is_rerunnable():
    migration = _load_migration_module("b8e1f2a3c4d5_drop_legacy_subscription_tables.py")
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")

    metadata = sa.MetaData()
    users = sa.Table(
        "users",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    )
    subscription_plans = sa.Table(
        "subscription_plans",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("price_cents", sa.Integer, nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("state_limit", sa.Integer, nullable=True),
        sa.Column("daily_download_limit", sa.Integer, nullable=False),
        sa.Column("features", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("stripe_price_id", sa.String(100), nullable=False),
    )
    subscriptions = sa.Table(
        "subscriptions",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("plan_id", sa.Integer, nullable=False),
        sa.Column("stripe_subscription_id", sa.String(100), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], onupdate="CASCADE", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["plan_id"], ["subscription_plans.id"], onupdate="CASCADE", ondelete="RESTRICT"),
    )
    lead_purchases = sa.Table(
        "lead_purchases",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
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
        connection.execute(users.insert(), [{"id": 1}])
        connection.execute(
            subscription_plans.insert(),
            [
                {
                    "id": 1,
                    "name": "Starter",
                    "price_cents": 10000,
                    "currency": "USD",
                    "state_limit": 1,
                    "daily_download_limit": 10,
                    "features": {"credits_total": 10},
                    "created_at": datetime(2026, 2, 18, 12, 0, tzinfo=timezone.utc),
                    "stripe_price_id": "price_starter_drop_legacy",
                },
            ],
        )
        connection.execute(
            subscriptions.insert(),
            [
                {
                    "id": 1,
                    "user_id": 1,
                    "plan_id": 1,
                    "stripe_subscription_id": "sub_drop_legacy_1",
                },
            ],
        )
        connection.execute(
            lead_purchases.insert(),
            [
                {
                    "id": 1,
                    "package_id": 1,
                },
            ],
        )

        _run_migration(migration, "upgrade", connection)
        _run_migration(migration, "upgrade", connection)

        inspector = sa.inspect(connection)
        table_names = set(inspector.get_table_names())
        assert "subscription_plans" not in table_names
        assert "subscriptions" not in table_names


@pytest.mark.unit
def test_e3_usd_currency_constraints_upgrade_is_rerunnable_and_enforced():
    migration = _load_migration_module("e3f4a5b6c7d8_enforce_usd_currency_constraints.py")
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")

    metadata = sa.MetaData()
    lead_packages = sa.Table(
        "lead_packages",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default=sa.text("'USD'")),
    )
    lead_purchases = sa.Table(
        "lead_purchases",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default=sa.text("'USD'")),
    )
    first_purchase_addon_offers = sa.Table(
        "first_purchase_addon_offers",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("offer_currency", sa.String(3), nullable=False, server_default=sa.text("'USD'")),
    )

    with engine.begin() as connection:
        metadata.create_all(connection)
        connection.execute(lead_packages.insert(), [{"id": 1, "currency": "USD"}])
        connection.execute(lead_purchases.insert(), [{"id": 1, "currency": "USD"}])
        connection.execute(first_purchase_addon_offers.insert(), [{"id": 1, "offer_currency": "USD"}])

        _run_migration(migration, "upgrade", connection)
        _run_migration(migration, "upgrade", connection)

        with pytest.raises(IntegrityError):
            connection.execute(
                sa.text("INSERT INTO lead_packages (id, currency) VALUES (2, 'EUR')")
            )

        with pytest.raises(IntegrityError):
            connection.execute(
                sa.text("INSERT INTO lead_purchases (id, currency) VALUES (2, 'CAD')")
            )

        with pytest.raises(IntegrityError):
            connection.execute(
                sa.text(
                    "INSERT INTO first_purchase_addon_offers (id, offer_currency) "
                    "VALUES (2, 'GBP')"
                )
            )


@pytest.mark.unit
def test_e3_usd_currency_constraints_upgrade_fails_when_non_usd_rows_exist():
    migration = _load_migration_module("e3f4a5b6c7d8_enforce_usd_currency_constraints.py")
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")

    metadata = sa.MetaData()
    lead_packages = sa.Table(
        "lead_packages",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default=sa.text("'USD'")),
    )
    sa.Table(
        "lead_purchases",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default=sa.text("'USD'")),
    )
    sa.Table(
        "first_purchase_addon_offers",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("offer_currency", sa.String(3), nullable=False, server_default=sa.text("'USD'")),
    )

    with engine.begin() as connection:
        metadata.create_all(connection)
        connection.execute(lead_packages.insert(), [{"id": 1, "currency": "EUR"}])

        with pytest.raises(RuntimeError, match="USD-only migration blocked"):
            _run_migration(migration, "upgrade", connection)
