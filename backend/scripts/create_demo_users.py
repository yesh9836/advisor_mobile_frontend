from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import settings
from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.user import User


@dataclass(frozen=True)
class DemoUserSpec:
    role: str
    name: str
    email: str
    password: str
    phone: str | None


def _environment_value(name: str, default: str) -> str:
    value = os.getenv(name)
    return value if value not in {None, ""} else default


def load_demo_user_specs() -> tuple[DemoUserSpec, DemoUserSpec]:
    shared_password = _environment_value("DEMO_USER_PASSWORD", "Password123!")
    admin = DemoUserSpec(
        role="admin",
        name=_environment_value("DEMO_ADMIN_NAME", "Demo Admin").strip(),
        email=_environment_value("DEMO_ADMIN_EMAIL", "admin.demo@example.com").strip().lower(),
        password=_environment_value("DEMO_ADMIN_PASSWORD", shared_password),
        phone=_environment_value("DEMO_ADMIN_PHONE", "+13055550100").strip() or None,
    )
    advisor = DemoUserSpec(
        role="advisor",
        name=_environment_value("DEMO_ADVISOR_NAME", "Demo Advisor").strip(),
        email=_environment_value("DEMO_ADVISOR_EMAIL", "advisor.demo@example.com").strip().lower(),
        password=_environment_value("DEMO_ADVISOR_PASSWORD", shared_password),
        phone=_environment_value("DEMO_ADVISOR_PHONE", "+13055550101").strip() or None,
    )
    return admin, advisor


def validate_demo_user_specs(specs: tuple[DemoUserSpec, ...]) -> None:
    emails = set()
    for spec in specs:
        if not spec.name:
            raise ValueError(f"{spec.role} demo name cannot be empty")
        if "@" not in spec.email:
            raise ValueError(f"{spec.role} demo email is invalid")
        if spec.email in emails:
            raise ValueError("Demo admin and advisor emails must be different")
        if len(spec.password) < 8:
            raise ValueError(f"{spec.role} demo password must be at least 8 characters")
        emails.add(spec.email)


def upsert_demo_user(db: Session, spec: DemoUserSpec) -> tuple[User, bool]:
    user = db.query(User).filter(User.email == spec.email).first()
    created = user is None
    if user is None:
        user = User(email=spec.email)

    user.name = spec.name
    user.password_hash = get_password_hash(spec.password)
    user.phone = spec.phone
    user.role = spec.role
    user.is_active = True
    user.deactivated_at = None
    user.deactivated_by = None
    db.add(user)
    return user, created


def create_demo_users(db: Session, specs: tuple[DemoUserSpec, ...]) -> list[tuple[User, bool]]:
    validate_demo_user_specs(specs)
    results = [upsert_demo_user(db, spec) for spec in specs]
    db.commit()
    for user, _created in results:
        db.refresh(user)
    return results


def main() -> None:
    if settings.APP_ENV.strip().lower() == "production":
        raise SystemExit("Refusing to create demo users when APP_ENV=production")

    specs = load_demo_user_specs()
    db = SessionLocal()
    try:
        results = create_demo_users(db, specs)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print("Demo users are ready. Existing demo passwords were reset.")
    for spec, (_user, created) in zip(specs, results, strict=True):
        action = "created" if created else "updated"
        print(f"{spec.role.capitalize()} ({action}): {spec.email} / {spec.password}")


if __name__ == "__main__":
    main()
