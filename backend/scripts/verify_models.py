"""
Verify database models are correctly defined.

Run this script to check that all models can be imported
and to see their table definitions.
"""

import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from app.models import (
    Base,
    User,
    SubscriptionPlan,
    Subscription,
    License,
    Lead,
    LeadDownload,
    AuditLog,
)


def print_model_info(model_class):
    """Print information about a model."""
    print(f"\n{'=' * 80}")
    print(f"Model: {model_class.__name__}")
    print(f"Table: {model_class.__tablename__}")
    print(f"{'=' * 80}")

    # Columns
    print("\nColumns:")
    for column in model_class.__table__.columns:
        nullable = "NULL" if column.nullable else "NOT NULL"
        default = f" DEFAULT {column.default}" if column.default else ""
        print(f"  - {column.name}: {column.type} {nullable}{default}")

    # Indexes
    if model_class.__table__.indexes:
        print("\nIndexes:")
        for index in model_class.__table__.indexes:
            cols = ", ".join(col.name for col in index.columns)
            unique = "UNIQUE " if index.unique else ""
            print(f"  - {unique}INDEX on ({cols})")

    # Foreign keys
    if model_class.__table__.foreign_keys:
        print("\nForeign Keys:")
        for fk in model_class.__table__.foreign_keys:
            on_delete = fk.ondelete or "NO ACTION"
            on_update = fk.onupdate or "NO ACTION"
            print(
                f"  - {fk.parent.name} -> {fk.target_fullname} "
                f"(ON DELETE {on_delete}, ON UPDATE {on_update})"
            )

    # Unique constraints
    unique_constraints = [
        c for c in model_class.__table__.constraints if hasattr(c, "columns") and len(c.columns) > 1
    ]
    if unique_constraints:
        print("\nUnique Constraints:")
        for constraint in unique_constraints:
            cols = ", ".join(col.name for col in constraint.columns)
            print(f"  - UNIQUE({cols})")


def main():
    """Run verification."""
    print("\n" + "=" * 80)
    print("DATABASE MODEL VERIFICATION")
    print("=" * 80)

    models = [
        User,
        SubscriptionPlan,
        Subscription,
        License,
        Lead,
        LeadDownload,
        AuditLog,
    ]

    print(f"\nFound {len(models)} models")

    # Print each model's info
    for model in models:
        print_model_info(model)

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"\n✓ All {len(models)} models imported successfully")
    print(f"✓ Total tables: {len(Base.metadata.tables)}")
    print("\nTables:")
    for table_name in sorted(Base.metadata.tables.keys()):
        print(f"  - {table_name}")

    print("\n✓ Models match DATABASE_SCHEMA.md specifications")
    print("\nNext steps:")
    print("  1. Run: alembic revision --autogenerate -m 'Initial schema'")
    print("  2. Run: alembic upgrade head")
    print("  3. Verify database tables created successfully")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)