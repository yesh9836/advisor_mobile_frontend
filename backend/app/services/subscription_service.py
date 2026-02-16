import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import stripe
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.core.config import settings
from app.models.license import License
from app.models.purchase import LeadCreditLedger, LeadPurchase
from app.models.subscription import Subscription, SubscriptionPlan
from app.models.user import User
from app.services.payment_service import PaymentService
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


class StripeWebhookProcessingError(Exception):
    """Raised when webhook processing fails and Stripe should retry delivery."""


def _to_datetime(timestamp: Optional[int]) -> Optional[datetime]:
    """Convert Stripe UNIX timestamp to UTC datetime."""
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


class SubscriptionService:
    """Service class for subscription management and Stripe webhooks."""

    @staticmethod
    def _resolve_package_credits(plan: SubscriptionPlan) -> int:
        """
        Resolve package credits from plan metadata.

        For first release migration compatibility, we treat `daily_download_limit`
        as the default package credit amount when explicit feature metadata is absent.
        """
        raw_credits: Optional[object] = None
        if isinstance(plan.features, dict):
            raw_credits = plan.features.get("credits_total")
            if raw_credits is None:
                raw_credits = plan.features.get("credits")

        if raw_credits is None:
            return max(int(plan.daily_download_limit or 0), 0)

        if isinstance(raw_credits, (int, float)):
            return max(int(raw_credits), 0)

        if isinstance(raw_credits, str) and raw_credits.isdigit():
            return int(raw_credits)

        return max(int(plan.daily_download_limit or 0), 0)

    @staticmethod
    def handle_webhook_event_threadsafe(event: Dict[str, Any]) -> None:
        """Create an isolated DB session for background-thread webhook work."""
        db = SessionLocal()
        try:
            SubscriptionService.handle_webhook_event(db=db, event=event)
        finally:
            db.close()

    @staticmethod
    def get_available_plans(db: Session) -> List[SubscriptionPlan]:
        """Return all available subscription plans."""
        return db.query(SubscriptionPlan).order_by(SubscriptionPlan.price_cents.asc()).all()

    @staticmethod
    def create_checkout_session(db: Session, user: User, plan_id: int) -> Dict[str, str]:
        """
        Create Stripe checkout session for one-time package purchase.
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

        frontend_base_url = settings.FRONTEND_URL.rstrip("/")
        success_url = (
            f"{frontend_base_url}/subscription"
            f"?checkout=success&session_id={{CHECKOUT_SESSION_ID}}"
        )
        cancel_url = f"{frontend_base_url}/subscription?checkout=cancel"

        try:
            session = stripe.checkout.Session.create(
                customer=customer_id,
                mode="payment",
                line_items=[{"price": plan.stripe_price_id, "quantity": 1}],
                client_reference_id=str(user.id),
                metadata={
                    "user_id": str(user.id),
                    "package_id": str(plan.id),
                },
                payment_intent_data={
                    "metadata": {
                        "user_id": str(user.id),
                        "package_id": str(plan.id),
                    }
                },
                success_url=success_url,
                cancel_url=cancel_url,
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
    def get_billing_summary(db: Session, user: User) -> Dict[str, Any]:
        if not settings.STRIPE_SECRET_KEY or not user.stripe_customer_id:
            return {
                "payment_method": None,
                "invoices": [],
            }

        PaymentService._init_stripe()

        payment_method: Optional[Dict[str, Any]] = None
        invoices: List[Dict[str, Any]] = []

        try:
            customer = stripe.Customer.retrieve(
                user.stripe_customer_id,
                expand=["invoice_settings.default_payment_method"],
            )

            default_pm = (customer.get("invoice_settings") or {}).get("default_payment_method")
            pm_obj: Optional[Dict[str, Any]] = None

            if isinstance(default_pm, str) and default_pm:
                pm_obj = stripe.PaymentMethod.retrieve(default_pm)
            elif isinstance(default_pm, dict):
                pm_obj = default_pm

            if pm_obj and pm_obj.get("type") == "card":
                card = pm_obj.get("card", {}) or {}
                payment_method = {
                    "brand": (card.get("brand") or "card").lower(),
                    "last4": card.get("last4") or "0000",
                    "exp_month": int(card.get("exp_month") or 1),
                    "exp_year": int(card.get("exp_year") or datetime.now(timezone.utc).year),
                    "funding": card.get("funding"),
                    "country": card.get("country"),
                    "is_placeholder": False,
                }

            invoice_result = stripe.Invoice.list(
                customer=user.stripe_customer_id,
                limit=10,
            )

            for inv in invoice_result.get("data", []):
                invoices.append(
                    {
                        "stripe_invoice_id": inv.get("id", ""),
                        "amount_paid_cents": int(inv.get("amount_paid") or 0),
                        "currency": str(inv.get("currency") or "usd").upper(),
                        "status": str(inv.get("status") or "unknown"),
                        "created_at": _to_datetime(inv.get("created")) or datetime.now(timezone.utc),
                        "hosted_invoice_url": inv.get("hosted_invoice_url"),
                        "invoice_pdf": inv.get("invoice_pdf"),
                        "description": inv.get("description"),
                    }
                )

        except stripe.error.StripeError as exc:
            logger.error("Failed to fetch billing summary from Stripe for user_id=%s: %s", user.id, exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Stripe billing provider unavailable",
            )

        return {
            "payment_method": payment_method,
            "invoices": invoices,
        }

    @staticmethod
    def get_credit_summary(db: Session, user: User) -> Dict[str, int]:
        total_credits = (
            db.query(func.coalesce(func.sum(LeadPurchase.credits_total), 0))
            .filter(
                LeadPurchase.user_id == user.id,
                LeadPurchase.status == "completed",
            )
            .scalar()
        )
        remaining_credits = (
            db.query(func.coalesce(func.sum(LeadPurchase.credits_remaining), 0))
            .filter(
                LeadPurchase.user_id == user.id,
                LeadPurchase.status == "completed",
            )
            .scalar()
        )
        completed_purchases = (
            db.query(LeadPurchase)
            .filter(
                LeadPurchase.user_id == user.id,
                LeadPurchase.status == "completed",
            )
            .count()
        )
        return {
            "total_credits": int(total_credits or 0),
            "remaining_credits": int(remaining_credits or 0),
            "completed_purchases": int(completed_purchases),
        }

    @staticmethod
    def _extract_payment_intent_id(checkout_session: Dict[str, Any]) -> Optional[str]:
        payment_intent = checkout_session.get("payment_intent")
        if isinstance(payment_intent, dict):
            return payment_intent.get("id")
        if isinstance(payment_intent, str):
            return payment_intent
        return None

    @staticmethod
    def _create_or_update_purchase_from_checkout_session(
        db: Session,
        checkout_session: Dict[str, Any],
    ) -> None:
        session_id = checkout_session.get("id")
        if not session_id:
            raise StripeWebhookProcessingError("checkout.session.completed missing session ID")

        metadata = checkout_session.get("metadata", {}) or {}
        user_id = metadata.get("user_id") or checkout_session.get("client_reference_id")
        package_id = metadata.get("package_id") or metadata.get("plan_id")

        if not user_id or not package_id:
            raise StripeWebhookProcessingError(
                f"checkout.session.completed missing purchase metadata for session_id={session_id}"
            )

        try:
            parsed_user_id = int(user_id)
            parsed_package_id = int(package_id)
        except (TypeError, ValueError) as exc:
            raise StripeWebhookProcessingError(
                f"checkout.session.completed invalid purchase metadata for session_id={session_id}"
            ) from exc

        plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == parsed_package_id).first()
        if not plan:
            raise StripeWebhookProcessingError(f"Package not found for package_id={parsed_package_id}")

        payment_status = str(checkout_session.get("payment_status") or "unpaid").lower()
        purchase_status = "completed" if payment_status == "paid" else "pending"
        credits_total = SubscriptionService._resolve_package_credits(plan)
        credits_remaining = credits_total if purchase_status == "completed" else 0
        payment_intent_id = SubscriptionService._extract_payment_intent_id(checkout_session)
        amount_cents = int(checkout_session.get("amount_total") or plan.price_cents or 0)
        currency = str(checkout_session.get("currency") or plan.currency or "USD").upper()
        purchased_at = _to_datetime(checkout_session.get("created")) or datetime.now(timezone.utc)

        purchase = (
            db.query(LeadPurchase)
            .filter(LeadPurchase.stripe_checkout_session_id == session_id)
            .first()
        )

        if purchase:
            purchase.status = purchase_status
            purchase.amount_cents = amount_cents
            purchase.currency = currency
            if payment_intent_id:
                purchase.stripe_payment_intent_id = payment_intent_id
            purchase.credits_total = credits_total
            purchase.credits_remaining = credits_remaining
            purchase.purchased_at = purchased_at
        else:
            purchase = LeadPurchase(
                user_id=parsed_user_id,
                package_id=parsed_package_id,
                stripe_checkout_session_id=session_id,
                stripe_payment_intent_id=payment_intent_id,
                amount_cents=amount_cents,
                currency=currency,
                credits_total=credits_total,
                credits_remaining=credits_remaining,
                status=purchase_status,
                purchased_at=purchased_at,
            )
            db.add(purchase)
            db.flush()

        if purchase_status == "completed":
            existing_grant = (
                db.query(LeadCreditLedger)
                .filter(
                    LeadCreditLedger.purchase_id == purchase.id,
                    LeadCreditLedger.movement_type == "purchase_grant",
                )
                .first()
            )
            if not existing_grant:
                db.add(
                    LeadCreditLedger(
                        user_id=purchase.user_id,
                        purchase_id=purchase.id,
                        movement_type="purchase_grant",
                        credits_delta=credits_total,
                        note=f"Checkout session {session_id}",
                    )
                )

        db.add(purchase)
        db.commit()

        logger.info(
            "Lead purchase fulfilled from checkout session: session_id=%s user_id=%s package_id=%s status=%s credits=%s",
            session_id,
            parsed_user_id,
            parsed_package_id,
            purchase_status,
            credits_total,
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

            # Backward-compatible handling for legacy subscription checkouts.
            if stripe_subscription_id:
                try:
                    stripe_subscription = stripe.Subscription.retrieve(
                        stripe_subscription_id,
                        expand=["items.data.price", "customer"],
                    )
                except stripe.error.StripeError as e:
                    message = (
                        f"Failed to retrieve Stripe subscription "
                        f"for stripe_subscription_id={stripe_subscription_id}: {e}"
                    )
                    logger.error(message)
                    raise StripeWebhookProcessingError(message) from e

                metadata = stripe_subscription.get("metadata", {}) or {}
                user_id = (
                    metadata.get("user_id")
                    or session.get("metadata", {}).get("user_id")
                    or session.get("client_reference_id")
                )
                plan_id = metadata.get("plan_id") or session.get("metadata", {}).get("plan_id")

                if not user_id or not plan_id:
                    message = (
                        "Missing user_id or plan_id metadata on subscription "
                        f"stripe_subscription_id={stripe_subscription_id}"
                    )
                    logger.error(message)
                    raise StripeWebhookProcessingError(message)

                existing = (
                    db.query(Subscription)
                    .filter(Subscription.stripe_subscription_id == stripe_subscription_id)
                    .first()
                )
                if existing:
                    logger.info(
                        "Subscription already exists for stripe_subscription_id=%s",
                        stripe_subscription_id,
                    )
                    return

                plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == int(plan_id)).first()
                if not plan:
                    message = f"Plan not found for plan_id={plan_id}"
                    logger.error(message)
                    raise StripeWebhookProcessingError(message)

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
                    logger.info("Subscription created: stripe_subscription_id=%s", stripe_subscription_id)
                except Exception as e:
                    db.rollback()
                    logger.error("Failed to create subscription record: %s", e)
                    raise e
            else:
                try:
                    SubscriptionService._create_or_update_purchase_from_checkout_session(
                        db=db,
                        checkout_session=session,
                    )
                except Exception:
                    db.rollback()
                    raise

        elif event_type == "payment_intent.succeeded":
            payment_intent_id = data_object.get("id")
            if not payment_intent_id:
                logger.warning("payment_intent.succeeded missing payment intent ID")
                return

            purchase = (
                db.query(LeadPurchase)
                .filter(LeadPurchase.stripe_payment_intent_id == payment_intent_id)
                .first()
            )
            if not purchase:
                logger.warning("No local lead purchase found for payment_intent_id=%s", payment_intent_id)
                return

            if purchase.status == "completed":
                logger.info("Lead purchase already completed for payment_intent_id=%s", payment_intent_id)
                return

            purchase.status = "completed"
            purchase.credits_remaining = purchase.credits_total
            db.add(purchase)

            existing_grant = (
                db.query(LeadCreditLedger)
                .filter(
                    LeadCreditLedger.purchase_id == purchase.id,
                    LeadCreditLedger.movement_type == "purchase_grant",
                )
                .first()
            )
            if not existing_grant:
                db.add(
                    LeadCreditLedger(
                        user_id=purchase.user_id,
                        purchase_id=purchase.id,
                        movement_type="purchase_grant",
                        credits_delta=purchase.credits_total,
                        note=f"Payment intent {payment_intent_id}",
                    )
                )

            db.commit()
            logger.info("Lead purchase marked completed for payment_intent_id=%s", payment_intent_id)

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
                message = (
                    "Failed to retrieve Stripe subscription during invoice.payment_succeeded "
                    f"for stripe_subscription_id={stripe_subscription_id}: {e}"
                )
                logger.error(message)
                raise StripeWebhookProcessingError(message) from e

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
