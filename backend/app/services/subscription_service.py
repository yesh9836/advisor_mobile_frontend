import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import stripe
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.core.config import settings
from app.models.license import License
from app.models.subscription import Subscription, SubscriptionPlan
from app.models.user import User
from app.services.payment_service import PaymentService

logger = logging.getLogger(__name__)


def _to_datetime(timestamp: Optional[int]) -> Optional[datetime]:
    """Convert Stripe UNIX timestamp to UTC datetime."""
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


class SubscriptionService:
    """Service class for subscription management and Stripe webhooks."""

    @staticmethod
    def get_available_plans(db: Session) -> List[SubscriptionPlan]:
        """Return all available subscription plans."""
        return db.query(SubscriptionPlan).order_by(SubscriptionPlan.price_cents.asc()).all()

    @staticmethod
    def create_checkout_session(db: Session, user: User, plan_id: int) -> Dict[str, str]:
        """
        Create Stripe checkout session for subscription purchase.
        """
        customer_id = PaymentService.create_or_get_stripe_customer(db, user)

        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == plan_id).first()
        if not plan:
            raise HTTPException(status_code=404, detail="Subscription plan not found")

        # Validate verified license
        verified_license = (
            db.query(License)
            .filter(
                and_(
                    License.user_id == user.id,
                    License.verification_status == "verified",
                )
            )
            .first()
        )
        if not verified_license:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one verified license is required",
            )

        # Validate no active subscription
        active_subscription = (
            db.query(Subscription)
            .filter(
                and_(
                    Subscription.user_id == user.id,
                    Subscription.status == "active",
                )
            )
            .first()
        )
        if active_subscription:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You already have an active subscription",
            )

        try:
            session = stripe.checkout.Session.create(
                customer=customer_id,
                mode="subscription",
                line_items=[{"price": plan.stripe_price_id, "quantity": 1}],
                subscription_data={
                    "metadata": {
                        "user_id": str(user.id),
                        "plan_id": str(plan.id),
                    },
                    "cancel_at_period_end": True
                },
                success_url=f"{settings.FRONTEND_URL}/advisor/subscription/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{settings.FRONTEND_URL}/advisor/subscription/cancel",
            )

            logger.info(
                f"Checkout session created user_id={user.id}, plan_id={plan.id}, session_id={session['id']}"
            )

            return {"session_id": session["id"], "url": session["url"]}

        except stripe.error.StripeError as e:
            logger.error(f"Stripe checkout session creation failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Stripe checkout session creation failed",
            )

    @staticmethod
    def handle_webhook_event(db: Session, event: Dict[str, Any]) -> None:
        """
        Handle Stripe webhook events for subscription lifecycle.
        """
        PaymentService._init_stripe()

        event_type = event.get("type")
        event_id = event.get("id")
        data_object = event.get("data", {}).get("object", {})

        logger.info(f"Stripe webhook received: type={event_type} id={event_id}")

        if event_type == "checkout.session.completed":
            session = data_object
            stripe_subscription_id = session.get("subscription")
            if not stripe_subscription_id:
                logger.warning("checkout.session.completed missing subscription ID")
                return

            try:
                stripe_subscription = stripe.Subscription.retrieve(
                    stripe_subscription_id,
                    expand=["items.data.price", "customer"],
                )
            except stripe.error.StripeError as e:
                logger.error(f"Failed to retrieve Stripe subscription: {e}")
                return

            metadata = stripe_subscription.get("metadata", {}) or {}
            user_id = metadata.get("user_id") or session.get("metadata", {}).get("user_id") or session.get("client_reference_id")
            plan_id = metadata.get("plan_id") or session.get("metadata", {}).get("plan_id")

            if not user_id or not plan_id:
                logger.error("Missing user_id or plan_id metadata on subscription")
                return

            # Idempotency check
            existing = (
                db.query(Subscription)
                .filter(Subscription.stripe_subscription_id == stripe_subscription_id)
                .first()
            )
            if existing:
                logger.info(f"Subscription already exists for stripe_subscription_id={stripe_subscription_id}")
                return

            plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == int(plan_id)).first()
            if not plan:
                logger.error(f"Plan not found for plan_id={plan_id}")
                return

            try:
                subscription = Subscription(
                        user_id=int(user_id),
                        plan_id=int(plan_id),
                        stripe_subscription_id=stripe_subscription_id,
                        status=stripe_subscription.get("status", "active"),
                        current_period_start=_to_datetime(stripe_subscription.get("current_period_start")),
                        current_period_end=_to_datetime(stripe_subscription.get("current_period_end")),
                )
                db.add(subscription)
                db.commit()

                logger.info(f"Subscription created: stripe_subscription_id={stripe_subscription_id}")

            except Exception as e:
                db.rollback()
                logger.error(f"Failed to create subscription record: {e}")
                raise e

        elif event_type == "customer.subscription.updated":
            stripe_subscription_id = data_object.get("id")
            if not stripe_subscription_id:
                logger.warning("customer.subscription.updated missing subscription ID")
                return

            subscription = (
                db.query(Subscription)
                .filter(Subscription.stripe_subscription_id == stripe_subscription_id)
                .first()
            )
            if not subscription:
                logger.warning(f"No local subscription found for {stripe_subscription_id}")
                return

            try:
                subscription.status = data_object.get("status", subscription.status)
                subscription.current_period_start = _to_datetime(data_object.get("current_period_start"))
                subscription.current_period_end = _to_datetime(data_object.get("current_period_end"))

                db.add(subscription)
                db.commit()

                logger.info(f"Subscription updated: stripe_subscription_id={stripe_subscription_id}")

            except Exception as e:
                db.rollback()
                logger.error(f"Failed to update subscription: {e}")
                raise e

        elif event_type == "customer.subscription.deleted":
            stripe_subscription_id = data_object.get("id")
            if not stripe_subscription_id:
                logger.warning("customer.subscription.deleted missing subscription ID")
                return

            subscription = (
                db.query(Subscription)
                .filter(Subscription.stripe_subscription_id == stripe_subscription_id)
                .first()
            )
            if not subscription:
                logger.warning(f"No local subscription found for {stripe_subscription_id}")
                return

            try:
                subscription.status = "canceled"
                subscription.current_period_end = _to_datetime(data_object.get("current_period_end"))

                db.add(subscription)
                db.commit()

                logger.info(f"Subscription canceled: stripe_subscription_id={stripe_subscription_id}")

            except Exception as e:
                db.rollback()
                logger.error(f"Failed to cancel subscription: {e}")
                raise e

        elif event_type == "invoice.payment_succeeded":
            stripe_subscription_id = data_object.get("subscription")
            if not stripe_subscription_id:
                logger.warning("invoice.payment_succeeded missing subscription ID")
                return

            subscription = (
                db.query(Subscription)
                .filter(Subscription.stripe_subscription_id == stripe_subscription_id)
                .first()
            )
            if not subscription:
                logger.warning(f"No local subscription found for {stripe_subscription_id}")
                return

            try:
                stripe_subscription = stripe.Subscription.retrieve(stripe_subscription_id)
            except stripe.error.StripeError as e:
                logger.error(f"Failed to retrieve Stripe subscription: {e}")
                return

            try:
                subscription.status = "active"
                subscription.current_period_end = _to_datetime(stripe_subscription.get("current_period_end"))

                db.add(subscription)
                db.commit()

                logger.info(f"Payment succeeded: stripe_subscription_id={stripe_subscription_id}")

            except Exception as e:
                db.rollback()
                logger.error(f"Failed to update subscription after payment success: {e}")
                raise e

        elif event_type == "invoice.payment_failed":
            stripe_subscription_id = data_object.get("subscription")
            if not stripe_subscription_id:
                logger.warning("invoice.payment_failed missing subscription ID")
                return

            subscription = (
                db.query(Subscription)
                .filter(Subscription.stripe_subscription_id == stripe_subscription_id)
                .first()
            )
            if not subscription:
                logger.warning(f"No local subscription found for {stripe_subscription_id}")
                return

            try:
                subscription.status = "past_due"

                db.add(subscription)
                db.commit()

                logger.info(f"Payment failed: stripe_subscription_id={stripe_subscription_id}")

            except Exception as e:
                db.rollback()
                logger.error(f"Failed to update subscription after payment failure: {e}")
                raise e

        else:
            logger.info(f"Unhandled Stripe event type: {event_type}")

    @staticmethod
    def cancel_subscription(db: Session, user: User) -> Subscription:
        """
        Cancel user's subscription at period end in Stripe and update local record.
        """
        PaymentService._init_stripe()

        subscription = (
            db.query(Subscription)
            .filter(Subscription.user_id == user.id)
            .order_by(Subscription.created_at.desc())
            .first()
        )
        if not subscription:
            raise HTTPException(status_code=404, detail="No subscription found")

        try:
            stripe_subscription = stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                cancel_at_period_end=True,
            )
        except stripe.error.StripeError as e:
            logger.error(f"Stripe subscription cancel failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Stripe cancellation failed",
            )

        try:
            subscription.status = stripe_subscription.get("status", subscription.status)
            subscription.current_period_end = _to_datetime(stripe_subscription.get("current_period_end"))
            db.add(subscription)
            db.commit()
            db.refresh(subscription)

            logger.info(
                f"Subscription marked for cancel at period end: "
                f"stripe_subscription_id={subscription.stripe_subscription_id}"
            )
            return subscription

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to update local subscription after cancel: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to cancel subscription locally",
            )
