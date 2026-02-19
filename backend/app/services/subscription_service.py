import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import stripe
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, or_
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.models.lead import LeadOwnership
from app.models.license import License
from app.models.purchase import (
    LeadCreditLedger,
    LeadPackage,
    LeadPurchase,
    ProcessedStripeEvent,
    StripePoisonEvent,
)
from app.models.user import User
from app.services.audit_service import AuditService
from app.services.lead_service import LeadService
from app.services.metrics_service import MetricsService
from app.services.notification_service import NotificationService
from app.services.payment_service import PaymentService
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


class StripeWebhookProcessingError(Exception):
    """Raised when webhook processing fails and Stripe should retry delivery."""


class StripeWebhookNonRetryableError(Exception):
    """Raised when webhook processing fails permanently and should be acknowledged."""

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        normalized_reason = str(reason or "").strip().lower()
        self.reason = normalized_reason or "unknown"


def _to_datetime(timestamp: Optional[int]) -> Optional[datetime]:
    """Convert Stripe UNIX timestamp to UTC datetime."""
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


class SubscriptionService:
    """Service class for one-time purchases and Stripe webhooks."""

    _TERMINAL_PURCHASE_STATUSES = frozenset({"failed", "canceled", "refunded"})
    _IMMUTABLE_PURCHASE_STATUSES = frozenset({"canceled", "refunded"})

    @staticmethod
    def _normalize_purchase_status(status: Optional[str]) -> str:
        return str(status or "").strip().lower()

    @staticmethod
    def _resolve_purchase_status_transition(
        *,
        purchase: LeadPurchase,
        requested_status: str,
        source_event: str,
        checkout_session_id: Optional[str] = None,
        payment_intent_id: Optional[str] = None,
    ) -> str:
        current_status = SubscriptionService._normalize_purchase_status(purchase.status)
        desired_status = SubscriptionService._normalize_purchase_status(requested_status)

        if (
            current_status in SubscriptionService._IMMUTABLE_PURCHASE_STATUSES
            and desired_status != current_status
        ):
            logger.warning(
                (
                    "Ignoring immutable purchase status transition: purchase_id=%s source_event=%s "
                    "checkout_session_id=%s payment_intent_id=%s current_status=%s requested_status=%s"
                ),
                purchase.id,
                source_event,
                checkout_session_id,
                payment_intent_id,
                current_status,
                desired_status,
            )
            return current_status

        if current_status == "completed" and desired_status != "completed":
            logger.info(
                (
                    "Ignoring downgrade for completed purchase: purchase_id=%s source_event=%s "
                    "checkout_session_id=%s payment_intent_id=%s requested_status=%s"
                ),
                purchase.id,
                source_event,
                checkout_session_id,
                payment_intent_id,
                desired_status,
            )
            return "completed"

        return desired_status

    @staticmethod
    def _is_purchase_checkout_enabled_for_user(user: User) -> bool:
        if settings.ONE_TIME_PURCHASES_ENABLED:
            return True

        # Admins can always validate purchase flows during staged rollout.
        if user.role == "admin":
            return True

        if user.id in settings.ONE_TIME_PURCHASES_ROLLOUT_USER_IDS:
            return True

        user_email = (user.email or "").strip().lower()
        if user_email and user_email in settings.ONE_TIME_PURCHASES_ROLLOUT_EMAILS:
            return True

        return False

    @staticmethod
    def _resolve_package_credits(package: LeadPackage) -> int:
        """
        Resolve package credits from package metadata.

        For first release migration compatibility, we treat `daily_download_limit`
        as the default package credit amount when explicit feature metadata is absent.
        """
        raw_credits: Optional[object] = None
        if isinstance(package.features, dict):
            raw_credits = package.features.get("credits_total")
            if raw_credits is None:
                raw_credits = package.features.get("credits")

        if raw_credits is None:
            return max(int(package.daily_download_limit or 0), 0)

        if isinstance(raw_credits, (int, float)):
            return max(int(raw_credits), 0)

        if isinstance(raw_credits, str) and raw_credits.isdigit():
            return int(raw_credits)

        return max(int(package.daily_download_limit or 0), 0)

    @staticmethod
    def _build_purchase_terms_snapshot(package: LeadPackage) -> Dict[str, Any]:
        return {
            "amount_cents": max(int(package.price_cents or 0), 0),
            "currency": str((package.currency or "USD")).upper(),
            "credits_total": SubscriptionService._resolve_package_credits(package),
        }

    @staticmethod
    def _build_checkout_purchase_metadata(
        *,
        user_id: int,
        package_id: int,
        purchase_terms: Dict[str, Any],
    ) -> Dict[str, str]:
        return {
            "user_id": str(user_id),
            "package_id": str(package_id),
            "purchase_amount_cents": str(max(int(purchase_terms.get("amount_cents") or 0), 0)),
            "purchase_currency": str(purchase_terms.get("currency") or "USD").upper(),
            "purchase_credits_total": str(max(int(purchase_terms.get("credits_total") or 0), 0)),
        }

    @staticmethod
    def _resolve_purchase_terms_from_metadata(metadata: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        amount_raw = metadata.get("purchase_amount_cents")
        credits_raw = metadata.get("purchase_credits_total")
        currency_raw = metadata.get("purchase_currency")

        if amount_raw is None or credits_raw is None or currency_raw is None:
            return None

        try:
            amount_cents = max(int(amount_raw), 0)
            credits_total = max(int(credits_raw), 0)
        except (TypeError, ValueError):
            return None

        currency = str(currency_raw).strip().upper()
        if not currency:
            return None

        return {
            "amount_cents": amount_cents,
            "currency": currency,
            "credits_total": credits_total,
        }

    @staticmethod
    def _is_catalog_visible_package(package: LeadPackage) -> bool:
        if not isinstance(package.features, dict):
            return True
        return package.features.get("catalog_visible", True) is not False

    @staticmethod
    def _build_checkout_line_item(package: LeadPackage) -> Dict[str, Any]:
        if isinstance(package.features, dict) and package.features.get("managed_by") == "first_purchase_offer":
            return {
                "price_data": {
                    "currency": str((package.currency or "USD")).lower(),
                    "unit_amount": int(package.price_cents or 0),
                    "product_data": {
                        "name": str(package.name or "First Purchase Add-on"),
                    },
                },
                "quantity": 1,
            }
        return {"price": package.stripe_price_id, "quantity": 1}

    @staticmethod
    def _is_first_purchase_offer_managed_package(package: LeadPackage) -> bool:
        return isinstance(package.features, dict) and package.features.get("managed_by") == "first_purchase_offer"

    @staticmethod
    def handle_webhook_event_threadsafe(event: Dict[str, Any]) -> None:
        """Create an isolated DB session for background-thread webhook work."""
        db = SessionLocal()
        try:
            SubscriptionService.handle_webhook_event(db=db, event=event)
        finally:
            db.close()

    @staticmethod
    def get_available_packages(db: Session) -> List[LeadPackage]:
        """Return all available one-time lead packages."""
        rows = db.query(LeadPackage).order_by(LeadPackage.price_cents.asc()).all()
        return [row for row in rows if SubscriptionService._is_catalog_visible_package(row)]

    @staticmethod
    def create_purchase_checkout_session(db: Session, user: User, package_id: int) -> Dict[str, str]:
        """
        Create Stripe checkout session for one-time package purchase.
        """
        if not SubscriptionService._is_purchase_checkout_enabled_for_user(user=user):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="One-time purchases are temporarily unavailable for this account",
            )

        package = db.query(LeadPackage).filter(LeadPackage.id == package_id).first()
        if not package:
            raise HTTPException(status_code=404, detail="Package not found")

        if SubscriptionService._is_first_purchase_offer_managed_package(package):
            from app.services.first_purchase_offer_service import FirstPurchaseOfferService

            if not FirstPurchaseOfferService.can_user_purchase_offer_package(
                db,
                user=user,
                offer_package_id=int(package.id),
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Package is not available for this account",
                )

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

        customer_id = PaymentService.create_or_get_stripe_customer(db, user)

        frontend_base_url = settings.FRONTEND_URL.rstrip("/")
        success_url = (
            f"{frontend_base_url}/subscription"
            f"?checkout=success&session_id={{CHECKOUT_SESSION_ID}}"
        )
        cancel_url = f"{frontend_base_url}/subscription?checkout=cancel"
        purchase_terms = SubscriptionService._build_purchase_terms_snapshot(package)
        checkout_metadata = SubscriptionService._build_checkout_purchase_metadata(
            user_id=int(user.id),
            package_id=int(package.id),
            purchase_terms=purchase_terms,
        )

        try:
            idempotency_key = PaymentService.checkout_session_idempotency_key(
                user_id=user.id,
                package_id=package.id,
            )
            session = stripe.checkout.Session.create(
                customer=customer_id,
                mode="payment",
                line_items=[SubscriptionService._build_checkout_line_item(package)],
                client_reference_id=str(user.id),
                metadata=checkout_metadata,
                payment_intent_data={
                    "metadata": checkout_metadata
                },
                success_url=success_url,
                cancel_url=cancel_url,
                idempotency_key=idempotency_key,
            )
            session_id = str(session["id"])
            payment_intent_id = SubscriptionService._extract_payment_intent_id(session)

            purchase = (
                db.query(LeadPurchase)
                .filter(LeadPurchase.stripe_checkout_session_id == session_id)
                .first()
            )
            if not purchase and payment_intent_id:
                purchase = (
                    db.query(LeadPurchase)
                    .filter(LeadPurchase.stripe_payment_intent_id == payment_intent_id)
                    .first()
                )

            if purchase:
                if not purchase.stripe_checkout_session_id:
                    purchase.stripe_checkout_session_id = session_id
                if payment_intent_id and not purchase.stripe_payment_intent_id:
                    purchase.stripe_payment_intent_id = payment_intent_id
            else:
                purchase = LeadPurchase(
                    user_id=int(user.id),
                    package_id=int(package.id),
                    stripe_checkout_session_id=session_id,
                    stripe_payment_intent_id=payment_intent_id,
                    amount_cents=int(purchase_terms["amount_cents"]),
                    currency=str(purchase_terms["currency"]),
                    credits_total=int(purchase_terms["credits_total"]),
                    credits_remaining=0,
                    status="pending",
                    purchased_at=datetime.now(timezone.utc),
                )
                db.add(purchase)

            db.add(purchase)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                purchase = (
                    db.query(LeadPurchase)
                    .filter(LeadPurchase.stripe_checkout_session_id == session_id)
                    .first()
                )
                if not purchase:
                    raise
            db.refresh(purchase)

            logger.info(
                "Checkout session created user_id=%s package_id=%s session_id=%s idempotency_key=%s",
                user.id,
                package.id,
                session_id,
                idempotency_key,
            )
            MetricsService.increment(
                "purchase_checkout_created_total",
                tags={
                    "provider": "stripe",
                    "package_id": str(package.id),
                },
            )
            AuditService.log_purchase_event(
                actor_user_id=user.id,
                action="purchase_initiated",
                purchase_id=purchase.id,
                amount_cents=int(purchase.amount_cents or 0),
                correlation_ids={
                    "checkout_session_id": session_id,
                    "payment_intent_id": payment_intent_id,
                    "idempotency_key": idempotency_key,
                },
                meta_data={
                    "package_id": package.id,
                    "currency": str((purchase.currency or "USD")).upper(),
                },
            )

            return {"session_id": session_id, "url": session["url"]}

        except stripe.error.StripeError as e:
            db.rollback()
            logger.error(f"Stripe checkout session creation failed: {e}")
            MetricsService.increment(
                "purchase_checkout_failed_total",
                tags={
                    "provider": "stripe",
                    "error_type": type(e).__name__,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Stripe checkout session creation failed",
            )
        except Exception:
            db.rollback()
            raise

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
    def get_purchase_balance(db: Session, user: User) -> Dict[str, int]:
        """Return advisor credit balance derived from completed purchases."""
        return SubscriptionService.get_credit_summary(db=db, user=user)

    @staticmethod
    def _get_assigned_counts_by_purchase_id(
        db: Session,
        purchase_ids: List[int],
    ) -> Dict[int, int]:
        if not purchase_ids:
            return {}

        rows = (
            db.query(
                LeadOwnership.purchase_id,
                func.count(LeadOwnership.id),
            )
            .filter(LeadOwnership.purchase_id.in_(purchase_ids))
            .group_by(LeadOwnership.purchase_id)
            .all()
        )
        return {
            int(purchase_id): int(assigned_count)
            for purchase_id, assigned_count in rows
            if purchase_id is not None
        }

    @staticmethod
    def _derive_fulfillment_status(
        *,
        purchase_status: str,
        credits_total: int,
        assigned_count: int,
        unfulfilled_count: int,
    ) -> str:
        normalized_status = str(purchase_status or "").lower()
        if normalized_status != "completed":
            if normalized_status == "pending":
                return "pending"
            return "not_completed"

        if credits_total <= 0 or unfulfilled_count <= 0:
            return "fulfilled"
        if assigned_count <= 0:
            return "pending_inventory"
        return "partially_fulfilled"

    @staticmethod
    def _build_purchase_item(
        purchase: LeadPurchase,
        package: Optional[LeadPackage],
        assigned_count: int,
    ) -> Dict[str, Any]:
        credits_total = int(purchase.credits_total or 0)
        unfulfilled_count = max(credits_total - max(int(assigned_count), 0), 0)
        return {
            "id": int(purchase.id),
            "order_reference": (
                purchase.stripe_checkout_session_id
                or purchase.stripe_payment_intent_id
                or f"purchase-{purchase.id}"
            ),
            "package_name": package.name if package else None,
            "amount_cents": int(purchase.amount_cents),
            "currency": str((purchase.currency or "USD")).upper(),
            "credits_total": credits_total,
            "credits_remaining": int(purchase.credits_remaining),
            "status": str(purchase.status),
            "assigned_count": max(int(assigned_count), 0),
            "unfulfilled_count": unfulfilled_count,
            "fulfillment_status": SubscriptionService._derive_fulfillment_status(
                purchase_status=str(purchase.status),
                credits_total=credits_total,
                assigned_count=max(int(assigned_count), 0),
                unfulfilled_count=unfulfilled_count,
            ),
            "purchased_at": purchase.purchased_at,
            "stripe_checkout_session_id": purchase.stripe_checkout_session_id,
            "stripe_payment_intent_id": purchase.stripe_payment_intent_id,
        }

    @staticmethod
    def get_purchase_orders(
        db: Session,
        user: User,
        page: int = 1,
        size: int = 20,
        status_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        query = (
            db.query(LeadPurchase, LeadPackage)
            .outerjoin(LeadPackage, LeadPackage.id == LeadPurchase.package_id)
            .filter(LeadPurchase.user_id == user.id)
        )
        if status_filter:
            query = query.filter(LeadPurchase.status == status_filter)

        total = query.with_entities(func.count(LeadPurchase.id)).scalar() or 0
        offset = max(0, (page - 1) * size)
        rows = (
            query.order_by(LeadPurchase.purchased_at.desc(), LeadPurchase.id.desc())
            .offset(offset)
            .limit(size)
            .all()
        )
        purchase_ids = [int(purchase.id) for purchase, _package in rows]
        assigned_counts = SubscriptionService._get_assigned_counts_by_purchase_id(
            db=db,
            purchase_ids=purchase_ids,
        )
        items: List[Dict[str, Any]] = [
            SubscriptionService._build_purchase_item(
                purchase=purchase,
                package=package,
                assigned_count=assigned_counts.get(int(purchase.id), 0),
            )
            for purchase, package in rows
        ]
        return {"items": items, "total": int(total), "page": page, "size": size}

    @staticmethod
    def get_purchase_history(db: Session, user: User, limit: int = 50) -> Dict[str, Any]:
        sanitized_limit = max(1, min(int(limit), 200))
        rows = (
            db.query(LeadPurchase, LeadPackage)
            .outerjoin(LeadPackage, LeadPackage.id == LeadPurchase.package_id)
            .filter(LeadPurchase.user_id == user.id)
            .order_by(LeadPurchase.purchased_at.desc(), LeadPurchase.id.desc())
            .limit(sanitized_limit)
            .all()
        )

        purchase_ids = [int(purchase.id) for purchase, _package in rows]
        assigned_counts = SubscriptionService._get_assigned_counts_by_purchase_id(
            db=db,
            purchase_ids=purchase_ids,
        )
        items: List[Dict[str, Any]] = [
            SubscriptionService._build_purchase_item(
                purchase=purchase,
                package=package,
                assigned_count=assigned_counts.get(int(purchase.id), 0),
            )
            for purchase, package in rows
        ]
        return {"items": items}

    @staticmethod
    def _extract_payment_intent_id(checkout_session: Dict[str, Any]) -> Optional[str]:
        payment_intent = checkout_session.get("payment_intent")
        if isinstance(payment_intent, dict):
            return payment_intent.get("id")
        if isinstance(payment_intent, str):
            return payment_intent
        return None

    @staticmethod
    def _build_purchase_grant_idempotency_key(*, purchase_id: int) -> str:
        return f"purchase_grant:{int(purchase_id)}"

    @staticmethod
    def _record_processed_stripe_event(
        db: Session,
        *,
        stripe_event_id: Optional[str],
        event_type: Optional[str],
    ) -> bool:
        normalized_event_id = str(stripe_event_id or "").strip()
        if not normalized_event_id:
            raise StripeWebhookProcessingError("Stripe webhook missing event ID")

        db.add(
            ProcessedStripeEvent(
                stripe_event_id=normalized_event_id,
                event_type=str(event_type or "unknown"),
            )
        )
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            duplicate = (
                db.query(ProcessedStripeEvent.id)
                .filter(ProcessedStripeEvent.stripe_event_id == normalized_event_id)
                .first()
            )
            if duplicate:
                logger.info("Ignoring duplicate Stripe webhook event_id=%s", normalized_event_id)
                return False
            raise

        return True

    @staticmethod
    def _build_poison_payload_excerpt(data_object: Any) -> Dict[str, Any]:
        if not isinstance(data_object, dict):
            return {"payload_type": type(data_object).__name__}
        metadata = data_object.get("metadata")
        metadata_keys: List[str] = []
        if isinstance(metadata, dict):
            metadata_keys = sorted(str(key) for key in metadata.keys())
        return {
            "object_id": data_object.get("id"),
            "object": data_object.get("object"),
            "mode": data_object.get("mode"),
            "payment_intent": data_object.get("payment_intent"),
            "client_reference_id": data_object.get("client_reference_id"),
            "metadata_keys": metadata_keys,
        }

    @staticmethod
    def _record_poison_stripe_event(
        db: Session,
        *,
        stripe_event_id: Optional[str],
        event_type: Optional[str],
        reason: str,
        detail: str,
        data_object: Any,
    ) -> bool:
        normalized_event_id = str(stripe_event_id or "").strip() or None
        if normalized_event_id:
            existing = (
                db.query(StripePoisonEvent.id)
                .filter(StripePoisonEvent.stripe_event_id == normalized_event_id)
                .first()
            )
            if existing:
                return False
        db.add(
            StripePoisonEvent(
                stripe_event_id=normalized_event_id,
                event_type=str(event_type or "unknown"),
                reason=str(reason or "unknown"),
                detail=str(detail or "non-retryable Stripe webhook error"),
                payload_excerpt=SubscriptionService._build_poison_payload_excerpt(data_object),
            )
        )
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            if normalized_event_id:
                duplicate = (
                    db.query(StripePoisonEvent.id)
                    .filter(StripePoisonEvent.stripe_event_id == normalized_event_id)
                    .first()
                )
                if duplicate:
                    return False
            raise
        return True

    @staticmethod
    def _commit_if_transaction_active(db: Session) -> None:
        if db.in_transaction():
            db.commit()

    @staticmethod
    def _grant_purchase_credits_if_needed(
        db: Session,
        purchase: LeadPurchase,
        credits_total: int,
        note: str,
    ) -> bool:
        if not settings.PURCHASE_WEBHOOK_CREDIT_GRANT_ENABLED:
            logger.warning(
                "Credit grant deferred by feature flag for purchase_id=%s user_id=%s",
                purchase.id,
                purchase.user_id,
            )
            return False

        if purchase.status != "completed":
            return False

        purchase_id = int(purchase.id or 0)
        if purchase_id <= 0:
            return False
        grant_idempotency_key = SubscriptionService._build_purchase_grant_idempotency_key(
            purchase_id=purchase_id
        )
        existing_grant = (
            db.query(LeadCreditLedger)
            .filter(
                or_(
                    LeadCreditLedger.idempotency_key == grant_idempotency_key,
                    and_(
                        LeadCreditLedger.purchase_id == purchase.id,
                        LeadCreditLedger.movement_type == "purchase_grant",
                    ),
                )
            )
            .first()
        )
        if existing_grant:
            return False

        try:
            with db.begin_nested():
                db.add(
                    LeadCreditLedger(
                        user_id=purchase.user_id,
                        purchase_id=purchase.id,
                        movement_type="purchase_grant",
                        credits_delta=credits_total,
                        note=note,
                        idempotency_key=grant_idempotency_key,
                    )
                )
                db.flush()
        except IntegrityError:
            logger.info(
                "Purchase credit grant already recorded: purchase_id=%s idempotency_key=%s",
                purchase.id,
                grant_idempotency_key,
            )
            return False

        purchase.credits_remaining = max(int(purchase.credits_remaining or 0), int(credits_total or 0))
        db.add(purchase)
        return True

    @staticmethod
    def _record_credit_grant_latency_metric(
        purchase: LeadPurchase,
        *,
        source_event: str,
    ) -> None:
        if not purchase.purchased_at:
            return
        latency_ms = max(
            (datetime.now(timezone.utc) - purchase.purchased_at).total_seconds() * 1000.0,
            0.0,
        )
        MetricsService.histogram(
            "credit_grant_latency_ms",
            latency_ms,
            tags={
                "source_event": source_event,
            },
        )

    @staticmethod
    def _build_purchase_correlation_ids(
        *,
        stripe_event_id: Optional[str],
        checkout_session_id: Optional[str],
        payment_intent_id: Optional[str],
        purchase_id: Optional[int],
    ) -> Dict[str, Any]:
        return {
            "stripe_event_id": stripe_event_id,
            "checkout_session_id": checkout_session_id,
            "payment_intent_id": payment_intent_id,
            "purchase_id": purchase_id,
        }

    @staticmethod
    def _mark_purchase_failed_by_payment_intent(
        db: Session,
        payment_intent_id: Optional[str],
        *,
        source_event: str,
    ) -> None:
        if not payment_intent_id:
            logger.warning("%s missing payment intent ID", source_event)
            return

        purchase = (
            db.query(LeadPurchase)
            .filter(LeadPurchase.stripe_payment_intent_id == payment_intent_id)
            .first()
        )
        if not purchase:
            logger.warning("No local lead purchase found for payment_intent_id=%s", payment_intent_id)
            return

        current_status = SubscriptionService._normalize_purchase_status(purchase.status)
        requested_status = "failed"
        resolved_status = SubscriptionService._resolve_purchase_status_transition(
            purchase=purchase,
            requested_status=requested_status,
            source_event=source_event,
            checkout_session_id=purchase.stripe_checkout_session_id,
            payment_intent_id=payment_intent_id,
        )
        if resolved_status != requested_status:
            logger.info(
                (
                    "Ignoring payment failure transition for purchase_id=%s payment_intent_id=%s "
                    "current_status=%s resolved_status=%s"
                ),
                purchase.id,
                payment_intent_id,
                current_status,
                resolved_status,
            )
            return

        if current_status == resolved_status:
            logger.info(
                "Lead purchase already in failed status for payment_intent_id=%s",
                payment_intent_id,
            )
            return

        purchase.status = resolved_status
        if purchase.credits_remaining < 0:
            purchase.credits_remaining = 0
        db.add(purchase)
        db.commit()
        logger.info("Lead purchase marked failed for payment_intent_id=%s", payment_intent_id)

    @staticmethod
    def _create_or_update_purchase_from_checkout_session(
        db: Session,
        checkout_session: Dict[str, Any],
        *,
        forced_status: Optional[str] = None,
        stripe_event_id: Optional[str] = None,
    ) -> None:
        session_id = checkout_session.get("id")
        if not session_id:
            raise StripeWebhookNonRetryableError(
                "checkout.session.completed missing session ID",
                reason="missing_session_id",
            )

        metadata = checkout_session.get("metadata", {}) or {}
        user_id = metadata.get("user_id") or checkout_session.get("client_reference_id")
        package_id = metadata.get("package_id") or metadata.get("plan_id")

        if not user_id or not package_id:
            raise StripeWebhookNonRetryableError(
                f"checkout.session.completed missing purchase metadata for session_id={session_id}",
                reason="missing_purchase_metadata",
            )

        try:
            parsed_user_id = int(user_id)
            parsed_package_id = int(package_id)
        except (TypeError, ValueError) as exc:
            raise StripeWebhookNonRetryableError(
                f"checkout.session.completed invalid purchase metadata for session_id={session_id}",
                reason="invalid_purchase_metadata",
            ) from exc

        payment_status = str(checkout_session.get("payment_status") or "unpaid").lower()
        purchase_status = forced_status or ("completed" if payment_status == "paid" else "pending")
        if purchase_status == "completed" and not settings.PURCHASE_WEBHOOK_CREDIT_GRANT_ENABLED:
            logger.warning(
                "Deferring completed purchase credit grant for checkout_session_id=%s due to feature flag",
                session_id,
            )
            purchase_status = "pending"
        payment_intent_id = SubscriptionService._extract_payment_intent_id(checkout_session)
        purchased_at = _to_datetime(checkout_session.get("created")) or datetime.now(timezone.utc)

        purchase = (
            db.query(LeadPurchase)
            .filter(LeadPurchase.stripe_checkout_session_id == session_id)
            .first()
        )
        if not purchase and payment_intent_id:
            purchase = (
                db.query(LeadPurchase)
                .filter(LeadPurchase.stripe_payment_intent_id == payment_intent_id)
                .first()
            )
        previous_status = purchase.status if purchase else None
        metadata_terms = SubscriptionService._resolve_purchase_terms_from_metadata(metadata)
        if purchase:
            credits_total = max(int(purchase.credits_total or 0), 0)
            amount_cents = max(int(purchase.amount_cents or 0), 0)
            currency = str((purchase.currency or "USD")).upper()
        elif metadata_terms:
            credits_total = int(metadata_terms["credits_total"])
            amount_cents = int(metadata_terms["amount_cents"])
            currency = str(metadata_terms["currency"])
        else:
            package = db.query(LeadPackage).filter(LeadPackage.id == parsed_package_id).first()
            if not package:
                raise StripeWebhookNonRetryableError(
                    f"Package not found for package_id={parsed_package_id}",
                    reason="missing_package",
                )
            credits_total = SubscriptionService._resolve_package_credits(package)
            amount_cents = int(checkout_session.get("amount_total") or package.price_cents or 0)
            currency = str(checkout_session.get("currency") or package.currency or "USD").upper()

        credits_remaining = credits_total if purchase_status == "completed" else 0

        if purchase:
            previous_status_normalized = SubscriptionService._normalize_purchase_status(previous_status)
            requested_status = purchase_status
            purchase_status = SubscriptionService._resolve_purchase_status_transition(
                purchase=purchase,
                requested_status=requested_status,
                source_event="checkout.session.lifecycle",
                checkout_session_id=session_id,
                payment_intent_id=payment_intent_id,
            )
            if previous_status_normalized == "completed" and purchase_status == "completed":
                # Success lifecycle replays must not resurrect spent credits.
                # Consumption/refund flows are the only allowed decrement paths.
                credits_remaining = max(int(purchase.credits_remaining or 0), 0)
            elif (
                previous_status_normalized in SubscriptionService._IMMUTABLE_PURCHASE_STATUSES
                and purchase_status == previous_status_normalized
            ):
                credits_remaining = max(int(purchase.credits_remaining or 0), 0)

        if purchase:
            purchase.status = purchase_status
            if not purchase.stripe_checkout_session_id:
                purchase.stripe_checkout_session_id = session_id
            if payment_intent_id:
                purchase.stripe_payment_intent_id = payment_intent_id
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

        grant_created = SubscriptionService._grant_purchase_credits_if_needed(
            db=db,
            purchase=purchase,
            credits_total=credits_total,
            note=f"Checkout session {session_id}",
        )
        allocation_summary = LeadService.allocate_unsold_leads_for_purchase(
            db=db,
            purchase=purchase,
        )
        newly_assigned_lead_ids = [
            int(lead_id)
            for lead_id in (allocation_summary.get("newly_assigned_lead_ids") or [])
        ]
        notification_summary = {"enqueued_total": 0, "enqueued_email": 0, "enqueued_sms": 0}
        if purchase.status == "completed" and newly_assigned_lead_ids:
            notification_summary = NotificationService.enqueue_lead_delivery_notifications(
                db=db,
                user_id=int(purchase.user_id),
                lead_ids=newly_assigned_lead_ids,
                purchase_id=int(purchase.id) if purchase.id is not None else None,
                source_event="purchase_checkout_session",
            )

        db.add(purchase)
        db.commit()
        correlation_ids = SubscriptionService._build_purchase_correlation_ids(
            stripe_event_id=stripe_event_id,
            checkout_session_id=purchase.stripe_checkout_session_id,
            payment_intent_id=purchase.stripe_payment_intent_id,
            purchase_id=purchase.id,
        )
        if purchase.status == "completed" and previous_status != "completed":
            AuditService.log_purchase_event(
                actor_user_id=purchase.user_id,
                action="purchase_confirmed",
                purchase_id=purchase.id,
                amount_cents=int(purchase.amount_cents or 0),
                correlation_ids=correlation_ids,
                meta_data={
                    "previous_status": previous_status,
                    "new_status": purchase.status,
                },
            )
        if grant_created:
            SubscriptionService._record_credit_grant_latency_metric(
                purchase,
                source_event="checkout_session",
            )
            AuditService.log_purchase_event(
                actor_user_id=purchase.user_id,
                action="purchase_credits_granted",
                purchase_id=purchase.id,
                credits_delta=credits_total,
                correlation_ids=correlation_ids,
                meta_data={
                    "grant_note": f"Checkout session {session_id}",
                },
            )
        if purchase.status == "completed":
            AuditService.log_purchase_event(
                actor_user_id=purchase.user_id,
                action="purchase_leads_allocated",
                purchase_id=purchase.id,
                correlation_ids=correlation_ids,
                meta_data={
                    "requested_count": int(allocation_summary.get("requested_count", 0)),
                    "assigned_count": int(allocation_summary.get("assigned_count", 0)),
                    "unfulfilled_count": int(allocation_summary.get("unfulfilled_count", 0)),
                    "assigned_lead_ids": allocation_summary.get("assigned_lead_ids", []),
                    "newly_assigned_lead_ids": newly_assigned_lead_ids,
                    "notification_enqueued_total": int(notification_summary["enqueued_total"]),
                    "notification_enqueued_email": int(notification_summary["enqueued_email"]),
                    "notification_enqueued_sms": int(notification_summary["enqueued_sms"]),
                },
            )

        logger.info(
            (
                "Lead purchase fulfilled from checkout session: session_id=%s user_id=%s "
                "package_id=%s status=%s credits=%s assigned=%s unfulfilled=%s"
            ),
            session_id,
            parsed_user_id,
            parsed_package_id,
            purchase_status,
            credits_total,
            int(allocation_summary.get("assigned_count", 0)),
            int(allocation_summary.get("unfulfilled_count", 0)),
        )


    @staticmethod
    def handle_webhook_event(db: Session, event: Dict[str, Any]) -> None:
        """
        Handle Stripe webhook events for one-time purchase lifecycle.
        """
        PaymentService._init_stripe()

        event_type = event.get("type")
        event_id = event.get("id")
        data_object = event.get("data", {}).get("object", {})

        logger.info(f"Stripe webhook received: type={event_type} id={event_id}")
        if not SubscriptionService._record_processed_stripe_event(
            db=db,
            stripe_event_id=event_id,
            event_type=event_type,
        ):
            return

        try:
            if event_type in {"checkout.session.completed", "checkout.session.async_payment_succeeded"}:
                session = data_object
                mode = str(session.get("mode") or "").lower()
                if mode == "subscription" or session.get("subscription"):
                    logger.info(
                        "Ignoring retired subscription checkout event: type=%s id=%s",
                        event_type,
                        event_id,
                    )
                    SubscriptionService._commit_if_transaction_active(db)
                    return
                try:
                    SubscriptionService._create_or_update_purchase_from_checkout_session(
                        db=db,
                        checkout_session=session,
                        stripe_event_id=event_id,
                    )
                except Exception:
                    db.rollback()
                    raise

            elif event_type == "checkout.session.async_payment_failed":
                session = data_object
                try:
                    SubscriptionService._create_or_update_purchase_from_checkout_session(
                        db=db,
                        checkout_session=session,
                        forced_status="failed",
                        stripe_event_id=event_id,
                    )
                except Exception:
                    db.rollback()
                    raise

            elif event_type == "payment_intent.succeeded":
                payment_intent_id = data_object.get("id")
                if not payment_intent_id:
                    logger.warning("payment_intent.succeeded missing payment intent ID")
                    SubscriptionService._commit_if_transaction_active(db)
                    return

                purchase = (
                    db.query(LeadPurchase)
                    .filter(LeadPurchase.stripe_payment_intent_id == payment_intent_id)
                    .first()
                )
                if not purchase:
                    logger.warning("No local lead purchase found for payment_intent_id=%s", payment_intent_id)
                    SubscriptionService._commit_if_transaction_active(db)
                    return

                if purchase.status == "completed":
                    logger.info("Lead purchase already completed for payment_intent_id=%s", payment_intent_id)
                    SubscriptionService._commit_if_transaction_active(db)
                    return

                previous_status = purchase.status
                requested_status = "pending" if not settings.PURCHASE_WEBHOOK_CREDIT_GRANT_ENABLED else "completed"
                resolved_status = SubscriptionService._resolve_purchase_status_transition(
                    purchase=purchase,
                    requested_status=requested_status,
                    source_event=event_type,
                    checkout_session_id=purchase.stripe_checkout_session_id,
                    payment_intent_id=payment_intent_id,
                )
                if resolved_status != requested_status:
                    SubscriptionService._commit_if_transaction_active(db)
                    return

                if not settings.PURCHASE_WEBHOOK_CREDIT_GRANT_ENABLED:
                    if purchase.status != "pending":
                        purchase.status = "pending"
                        db.add(purchase)
                        db.commit()
                    logger.warning(
                        "Deferring payment_intent fulfillment for payment_intent_id=%s due to feature flag",
                        payment_intent_id,
                    )
                    SubscriptionService._commit_if_transaction_active(db)
                    return

                purchase.status = "completed"
                purchase.credits_remaining = purchase.credits_total
                db.add(purchase)

                grant_created = SubscriptionService._grant_purchase_credits_if_needed(
                    db=db,
                    purchase=purchase,
                    credits_total=purchase.credits_total,
                    note=f"Payment intent {payment_intent_id}",
                )
                allocation_summary = LeadService.allocate_unsold_leads_for_purchase(
                    db=db,
                    purchase=purchase,
                )
                newly_assigned_lead_ids = [
                    int(lead_id)
                    for lead_id in (allocation_summary.get("newly_assigned_lead_ids") or [])
                ]
                notification_summary = {"enqueued_total": 0, "enqueued_email": 0, "enqueued_sms": 0}
                if newly_assigned_lead_ids:
                    notification_summary = NotificationService.enqueue_lead_delivery_notifications(
                        db=db,
                        user_id=int(purchase.user_id),
                        lead_ids=newly_assigned_lead_ids,
                        purchase_id=int(purchase.id) if purchase.id is not None else None,
                        source_event="payment_intent_succeeded",
                    )

                db.commit()
                correlation_ids = SubscriptionService._build_purchase_correlation_ids(
                    stripe_event_id=event_id,
                    checkout_session_id=purchase.stripe_checkout_session_id,
                    payment_intent_id=purchase.stripe_payment_intent_id,
                    purchase_id=purchase.id,
                )
                if previous_status != "completed":
                    AuditService.log_purchase_event(
                        actor_user_id=purchase.user_id,
                        action="purchase_confirmed",
                        purchase_id=purchase.id,
                        amount_cents=int(purchase.amount_cents or 0),
                        correlation_ids=correlation_ids,
                        meta_data={
                            "previous_status": previous_status,
                            "new_status": purchase.status,
                        },
                    )
                if grant_created:
                    SubscriptionService._record_credit_grant_latency_metric(
                        purchase,
                        source_event="payment_intent",
                    )
                    AuditService.log_purchase_event(
                        actor_user_id=purchase.user_id,
                        action="purchase_credits_granted",
                        purchase_id=purchase.id,
                        credits_delta=purchase.credits_total,
                        correlation_ids=correlation_ids,
                        meta_data={
                            "grant_note": f"Payment intent {payment_intent_id}",
                        },
                    )
                AuditService.log_purchase_event(
                    actor_user_id=purchase.user_id,
                    action="purchase_leads_allocated",
                    purchase_id=purchase.id,
                    correlation_ids=correlation_ids,
                    meta_data={
                        "requested_count": int(allocation_summary.get("requested_count", 0)),
                        "assigned_count": int(allocation_summary.get("assigned_count", 0)),
                        "unfulfilled_count": int(allocation_summary.get("unfulfilled_count", 0)),
                        "assigned_lead_ids": allocation_summary.get("assigned_lead_ids", []),
                        "newly_assigned_lead_ids": newly_assigned_lead_ids,
                        "notification_enqueued_total": int(notification_summary["enqueued_total"]),
                        "notification_enqueued_email": int(notification_summary["enqueued_email"]),
                        "notification_enqueued_sms": int(notification_summary["enqueued_sms"]),
                    },
                )
                logger.info("Lead purchase marked completed for payment_intent_id=%s", payment_intent_id)

            elif event_type == "payment_intent.payment_failed":
                SubscriptionService._mark_purchase_failed_by_payment_intent(
                    db=db,
                    payment_intent_id=data_object.get("id"),
                    source_event=event_type,
                )

            elif event_type == "charge.refunded":
                payment_intent = data_object.get("payment_intent")
                if isinstance(payment_intent, dict):
                    payment_intent_id = payment_intent.get("id")
                else:
                    payment_intent_id = payment_intent

                if not payment_intent_id:
                    logger.warning("charge.refunded missing payment intent ID")
                    SubscriptionService._commit_if_transaction_active(db)
                    return

                purchase = (
                    db.query(LeadPurchase)
                    .filter(LeadPurchase.stripe_payment_intent_id == payment_intent_id)
                    .first()
                )
                if not purchase:
                    logger.warning(
                        "No local lead purchase found for refunded payment_intent_id=%s",
                        payment_intent_id,
                    )
                    SubscriptionService._commit_if_transaction_active(db)
                    return

                previous_status = purchase.status
                refundable_credits = max(int(purchase.credits_remaining or 0), 0)
                existing_refund_adjustment = (
                    db.query(LeadCreditLedger)
                    .filter(
                        LeadCreditLedger.purchase_id == purchase.id,
                        LeadCreditLedger.movement_type == "refund_adjustment",
                    )
                    .first()
                )

                credits_reversed = 0
                if refundable_credits > 0 and not existing_refund_adjustment:
                    db.add(
                        LeadCreditLedger(
                            user_id=purchase.user_id,
                            purchase_id=purchase.id,
                            movement_type="refund_adjustment",
                            credits_delta=-refundable_credits,
                            note=f"Stripe refund for payment_intent {payment_intent_id}",
                        )
                    )
                    credits_reversed = refundable_credits

                purchase.status = "refunded"
                purchase.credits_remaining = 0
                db.add(purchase)
                db.commit()

                if credits_reversed > 0 or previous_status != "refunded":
                    AuditService.log_purchase_event(
                        actor_user_id=purchase.user_id,
                        action="purchase_refund_adjusted",
                        purchase_id=purchase.id,
                        credits_delta=-credits_reversed,
                        amount_cents=int(data_object.get("amount_refunded") or 0),
                        correlation_ids=SubscriptionService._build_purchase_correlation_ids(
                            stripe_event_id=event_id,
                            checkout_session_id=purchase.stripe_checkout_session_id,
                            payment_intent_id=purchase.stripe_payment_intent_id,
                            purchase_id=purchase.id,
                        ),
                        meta_data={
                            "previous_status": previous_status,
                            "new_status": purchase.status,
                            "refund_reason": data_object.get("reason"),
                        },
                    )

            elif event_type in {
                "customer.subscription.updated",
                "customer.subscription.deleted",
                "invoice.payment_succeeded",
                "invoice.payment_failed",
            }:
                logger.info(
                    "Ignoring retired Stripe subscription lifecycle event: type=%s id=%s",
                    event_type,
                    event_id,
                )

            else:
                logger.info(f"Unhandled Stripe event type: {event_type}")

            SubscriptionService._commit_if_transaction_active(db)
        except StripeWebhookNonRetryableError as exc:
            db.rollback()
            poison_recorded = SubscriptionService._record_poison_stripe_event(
                db=db,
                stripe_event_id=event_id,
                event_type=event_type,
                reason=exc.reason,
                detail=str(exc),
                data_object=data_object,
            )
            SubscriptionService._commit_if_transaction_active(db)
            MetricsService.increment(
                "purchase_webhook_non_retryable_total",
                tags={
                    "event_type": str(event_type or "unknown"),
                    "reason": exc.reason,
                    "poison_recorded": "true" if poison_recorded else "false",
                },
            )
            logger.warning(
                "Stripe webhook non-retryable failure acknowledged: type=%s id=%s reason=%s detail=%s",
                event_type,
                event_id,
                exc.reason,
                exc,
            )
            raise
