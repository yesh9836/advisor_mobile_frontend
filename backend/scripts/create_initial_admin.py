from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy.orm import Session

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import settings
from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.user import User


def validate_initial_admin(email: str, password: str, name: str) -> None:
    if not name.strip() or len(name.strip()) > 150:
        raise ValueError("Initial admin name must be between 1 and 150 characters")
    if "@" not in email or len(email) > 255:
        raise ValueError("Initial admin email is invalid")
    if (
        len(password) < 12
        or password.lower() == password
        or password.upper() == password
        or not any(character.isdigit() for character in password)
        or not any(not character.isalnum() for character in password)
    ):
        raise ValueError(
            "Initial admin password must be at least 12 characters and include uppercase, "
            "lowercase, numeric, and special characters"
        )


def create_initial_admin(
    db: Session,
    *,
    email: str,
    password: str,
    name: str,
) -> tuple[User, bool]:
    normalized_email = email.strip().lower()
    normalized_name = name.strip()
    validate_initial_admin(normalized_email, password, normalized_name)

    existing = db.query(User).filter(User.email == normalized_email).first()
    if existing is not None:
        if existing.role != "admin":
            raise ValueError("Initial admin email already belongs to a non-admin account")
        return existing, False

    admin = User(
        email=normalized_email,
        name=normalized_name,
        password_hash=get_password_hash(password),
        role="admin",
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin, True


def main() -> None:
    db = SessionLocal()
    try:
        admin, created = create_initial_admin(
            db,
            email=settings.INITIAL_ADMIN_EMAIL,
            password=settings.INITIAL_ADMIN_PASSWORD,
            name=settings.INITIAL_ADMIN_NAME,
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    if created:
        print(f"Initial admin created: {admin.email}")
    else:
        print(f"Initial admin already exists; password was not changed: {admin.email}")


if __name__ == "__main__":
    main()
