import logging

import stripe
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User

logger = logging.getLogger(__name__)


class PaymentService:
    """Service for Stripe payment interactions."""
    
    _initialized: bool = False

    @staticmethod
    def _customer_create_idempotency_key(user: User) -> str:
        """Build a deterministic idempotency key for Stripe customer creation."""
        if user.id is not None:
            identity = str(user.id)
        else:
            identity = (user.email or "").strip().lower()
        return f"customer-create:{identity}:v1"

    @classmethod
    def _init_stripe(cls) -> None:
        """Initialize Stripe client with API key and version."""
        if cls._initialized:
            return

        if not settings.STRIPE_SECRET_KEY:
            logger.error("Stripe secret key is not configured")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Stripe configuration error",
            )

        stripe.api_key = settings.STRIPE_SECRET_KEY
        stripe.api_version = settings.STRIPE_API_VERSION
        cls._initialized = True
        logger.info("Stripe client initialized")

    @staticmethod
    def create_or_get_stripe_customer(db: Session, user: User) -> str:
        """
        Create or retrieve Stripe customer for user.

        If user.stripe_customer_id exists, return it.
        Otherwise create Stripe customer, save it to user, and return ID.
        """
        PaymentService._init_stripe()

        if user.stripe_customer_id:
            return user.stripe_customer_id

        if db is None:
            logger.error("User is not attached to an active DB session")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database session error",
            )

        try:
            customer = stripe.Customer.create(
                email=user.email,
                name=user.name,
                phone=user.phone,
                metadata={"user_id": str(user.id)},
                idempotency_key=PaymentService._customer_create_idempotency_key(user),
            )

            user.stripe_customer_id = customer["id"]
            db.add(user)
            db.commit()
            db.refresh(user)

            logger.info(f"Stripe customer created for user_id={user.id}: {customer['id']}")
            return customer["id"]

        except stripe.error.StripeError as e:
            logger.error(f"Stripe customer creation failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Stripe customer creation failed",
            )
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to save Stripe customer ID: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save Stripe customer ID",
            )
