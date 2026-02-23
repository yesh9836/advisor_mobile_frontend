import hashlib
import logging
import re
from typing import Optional
from uuid import uuid4

import stripe
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User

logger = logging.getLogger(__name__)


class PaymentService:
    """Service for Stripe payment interactions."""

    _initialized: bool = False
    _CHECKOUT_RETRY_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9:_-]{8,128}$")

    @staticmethod
    def _customer_create_idempotency_key(user: User) -> str:
        """Build a deterministic idempotency key for Stripe customer creation."""
        if user.id is not None:
            identity = str(user.id)
        else:
            identity = (user.email or "").strip().lower()
        return f"customer-create:{identity}:v1"

    @staticmethod
    def checkout_session_idempotency_key(
        *,
        user_id: int,
        package_id: int,
        retry_token: Optional[str] = None,
    ) -> str:
        """Build an intent-scoped idempotency key for checkout creation retries."""
        normalized_retry_token = PaymentService._normalize_checkout_retry_token(retry_token)
        if normalized_retry_token is None:
            normalized_retry_token = f"new:{uuid4().hex}"
        token_hash = hashlib.sha256(normalized_retry_token.encode("utf-8")).hexdigest()[:24]
        return f"checkout-create:{int(user_id)}:{int(package_id)}:{token_hash}:v2"

    @staticmethod
    def _normalize_checkout_retry_token(retry_token: Optional[str]) -> Optional[str]:
        if retry_token is None:
            return None
        cleaned = str(retry_token).strip()
        if not cleaned:
            return None
        if not PaymentService._CHECKOUT_RETRY_TOKEN_PATTERN.fullmatch(cleaned):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid checkout retry token",
            )
        return cleaned

    @staticmethod
    def _stripe_http_client_candidates() -> list[tuple[str, object]]:
        candidates: list[tuple[str, object]] = []
        seen_ids: set[int] = set()
        namespaces = (
            stripe,
            getattr(stripe, "http_client", None),
            getattr(stripe, "_http_client", None),
        )

        for namespace in namespaces:
            if namespace is None:
                continue
            for class_name in ("RequestsClient", "HTTPXClient"):
                client_cls = getattr(namespace, class_name, None)
                if client_cls is None:
                    continue
                identity = id(client_cls)
                if identity in seen_ids:
                    continue
                seen_ids.add(identity)
                candidates.append((class_name, client_cls))

        return candidates

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
        stripe.max_network_retries = max(int(settings.STRIPE_MAX_NETWORK_RETRIES or 0), 0)

        timeout_seconds = max(float(settings.STRIPE_REQUEST_TIMEOUT_SECONDS or 0), 1.0)
        timeout_applied = False
        for client_name, client_cls in cls._stripe_http_client_candidates():
            try:
                stripe.default_http_client = client_cls(timeout=timeout_seconds)
                timeout_applied = True
                logger.info(
                    "Stripe timeout policy applied via %s(timeout=%s)",
                    client_name,
                    timeout_seconds,
                )
                break
            except Exception as exc:  # pragma: no cover - defensive across Stripe SDK versions
                logger.debug("Stripe %s unavailable for timeout policy: %s", client_name, exc)

        if not timeout_applied:
            logger.warning("Stripe timeout policy not applied; using Stripe SDK default HTTP client")
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
