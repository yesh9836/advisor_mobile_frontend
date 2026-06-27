import pytest

from app.core.security import verify_password
from app.models.user import User
from scripts.create_demo_users import (
    DemoUserSpec,
    create_demo_users,
    validate_demo_user_specs,
)


@pytest.mark.unit
def test_create_demo_users_creates_only_requested_accounts(db):
    specs = (
        DemoUserSpec("admin", "Demo Admin", "admin.demo@example.com", "AdminPass123!", "+13055550100"),
        DemoUserSpec(
            "advisor",
            "Demo Advisor",
            "advisor.demo@example.com",
            "AdvisorPass123!",
            "+13055550101",
        ),
    )

    results = create_demo_users(db, specs)

    assert [created for _user, created in results] == [True, True]
    assert db.query(User).count() == 2
    assert {user.role for user in db.query(User).all()} == {"admin", "advisor"}


@pytest.mark.unit
def test_create_demo_users_refreshes_existing_account(db, user_factory):
    existing = user_factory(
        role="advisor",
        email="admin.demo@example.com",
        name="Old Demo User",
        password="OldPassword123!",
    )
    existing.is_active = False
    db.commit()
    spec = DemoUserSpec(
        "admin",
        "Demo Admin",
        "admin.demo@example.com",
        "NewPassword123!",
        "+13055550100",
    )

    results = create_demo_users(db, (spec,))

    refreshed = db.query(User).filter(User.email == spec.email).one()
    assert results[0][1] is False
    assert refreshed.id == existing.id
    assert refreshed.role == "admin"
    assert refreshed.name == "Demo Admin"
    assert refreshed.is_active is True
    assert verify_password("NewPassword123!", refreshed.password_hash)


@pytest.mark.unit
def test_validate_demo_user_specs_rejects_duplicate_emails():
    specs = (
        DemoUserSpec("admin", "Demo Admin", "same@example.com", "Password123!", None),
        DemoUserSpec("advisor", "Demo Advisor", "same@example.com", "Password123!", None),
    )

    with pytest.raises(ValueError, match="emails must be different"):
        validate_demo_user_specs(specs)
