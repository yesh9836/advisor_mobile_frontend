import sys
import os
import logging

sys.path.append(os.getcwd())

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.session import SessionLocal
from app.core.config import settings
from app.core.security import get_password_hash
from app.models.purchase import LeadPackage
from app.models.user import User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _resolve_seed_stripe_price_id(plan_key: str, fallback: str) -> str:
    """Allow seed price IDs to be configured from env for real Stripe test accounts."""
    for env_key in (f"SEED_STRIPE_PRICE_ID_{plan_key}", f"STRIPE_PRICE_ID_{plan_key}"):
        value = os.getenv(env_key, "").strip()
        if value:
            return value
    return fallback


def _warn_if_placeholder_price_id(plan_name: str, plan_key: str, price_id: str) -> None:
    if price_id.startswith("price_fake_"):
        logger.warning(
            "Plan %s is using placeholder stripe_price_id=%s. Set %s (or STRIPE_PRICE_ID_%s) before running seed for Stripe checkout tests.",
            plan_name,
            price_id,
            f"SEED_STRIPE_PRICE_ID_{plan_key}",
            plan_key,
        )


def seed_data():
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        logger.info("Database connection successful.")

        seed_plans(db)
        seed_admin(db)
        logger.info("Seeding completed successfully!")
    except Exception as e:
        logger.error(f"Seeding failed: {e}")
        raise e
    finally:
        db.close()

def seed_plans(db: Session):
    """Create default one-time lead packages."""
    logger.info("Checking lead packages...")

    basic_price_id = _resolve_seed_stripe_price_id("BASIC", "price_fake_basic_123")
    pro_price_id = _resolve_seed_stripe_price_id("PRO", "price_fake_pro_456")
    unlimited_price_id = _resolve_seed_stripe_price_id("UNLIMITED", "price_fake_unlim_789")
    _warn_if_placeholder_price_id("Basic", "BASIC", basic_price_id)
    _warn_if_placeholder_price_id("Pro", "PRO", pro_price_id)
    _warn_if_placeholder_price_id("Unlimited", "UNLIMITED", unlimited_price_id)

    plans = [
        {
            "name": "Basic",
            "price_cents": 9900,  # $99.00
            "stripe_price_id": basic_price_id,
            "state_limit": 1,
            "daily_download_limit": 10,
            "features": {"support": "email"}
        },
        {
            "name": "Pro",
            "price_cents": 19900,  # $199.00
            "stripe_price_id": pro_price_id,
            "state_limit": 3,
            "daily_download_limit": 50,
            "features": {"support": "priority"}
        },
        {
            "name": "Unlimited",
            "price_cents": 29900,  # $299.00
            "stripe_price_id": unlimited_price_id,
            "state_limit": None,  # Unlimited states
            "daily_download_limit": 100,
            "features": {"support": "24/7"}
        }
    ]

    for plan_data in plans:
        existing_package = db.query(LeadPackage).filter(LeadPackage.name == plan_data["name"]).first()
        if not existing_package:
            package = LeadPackage(**plan_data)
            db.add(package)
            logger.info(f"Created plan: {plan_data['name']}")
        else:
            existing_package.price_cents = plan_data["price_cents"]
            existing_package.currency = plan_data.get("currency", "USD")
            existing_package.state_limit = plan_data["state_limit"]
            existing_package.daily_download_limit = plan_data["daily_download_limit"]
            existing_package.features = plan_data["features"]
            if existing_package.stripe_price_id != plan_data["stripe_price_id"]:
                existing_package.stripe_price_id = plan_data["stripe_price_id"]
            logger.info(f"Updated package: {plan_data['name']}")
    
    db.commit()

def seed_admin(db: Session):
    """Create the initial super admin user."""
    logger.info("Checking admin user...")
    
    admin_email = settings.INITIAL_ADMIN_EMAIL
    
    existing_admin = db.query(User).filter(User.email == admin_email).first()
    if not existing_admin:
        admin_user = User(
            name=settings.INITIAL_ADMIN_NAME,
            email=admin_email,
            password_hash=get_password_hash(settings.INITIAL_ADMIN_PASSWORD),
            role="admin",
            phone="555-0199"
        )
        db.add(admin_user)
        db.commit()
        logger.info(f"Created admin user: {admin_email}")
    else:
        logger.info(f"Admin user already exists: {admin_email}")

if __name__ == "__main__":
    seed_data()
