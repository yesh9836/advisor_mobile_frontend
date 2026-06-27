import pytest

from app.core.security import verify_password
from app.models.user import User
from scripts.create_initial_admin import create_initial_admin, validate_initial_admin


@pytest.mark.unit
def test_create_initial_admin_creates_admin(db):
    admin, created = create_initial_admin(
        db,
        email="ADMIN@example.com",
        password="AdminPassword123!",
        name="Initial Admin",
    )

    assert created is True
    assert db.query(User).count() == 1
    assert admin.email == "admin@example.com"
    assert admin.role == "admin"
    assert admin.is_active is True
    assert verify_password("AdminPassword123!", admin.password_hash)


@pytest.mark.unit
def test_create_initial_admin_is_idempotent_without_resetting_password(db):
    original, _created = create_initial_admin(
        db,
        email="admin@example.com",
        password="OriginalPassword123!",
        name="Initial Admin",
    )

    existing, created = create_initial_admin(
        db,
        email="admin@example.com",
        password="DifferentPassword123!",
        name="Different Name",
    )

    assert created is False
    assert existing.id == original.id
    assert existing.name == "Initial Admin"
    assert verify_password("OriginalPassword123!", existing.password_hash)
    assert not verify_password("DifferentPassword123!", existing.password_hash)


@pytest.mark.unit
def test_create_initial_admin_does_not_promote_existing_advisor(db, user_factory):
    user_factory(role="advisor", email="admin@example.com")

    with pytest.raises(ValueError, match="non-admin account"):
        create_initial_admin(
            db,
            email="admin@example.com",
            password="AdminPassword123!",
            name="Initial Admin",
        )


@pytest.mark.unit
def test_validate_initial_admin_rejects_weak_password():
    with pytest.raises(ValueError, match="at least 12 characters"):
        validate_initial_admin("admin@example.com", "password", "Initial Admin")
