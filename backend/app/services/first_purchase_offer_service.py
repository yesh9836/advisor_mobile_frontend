import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.timezone import utcnow
from app.models.purchase import FirstPurchaseAddonOffer, LeadPackage, LeadPurchase
from app.models.user import User
from app.schemas.purchase import (
    FirstPurchaseAddonOfferAdvisorResponse,
    FirstPurchaseAddonOfferConfigResponse,
    FirstPurchaseAddonOfferEligibilityResponse,
    FirstPurchaseAddonOfferUpdateRequest,
)
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

_DEFAULT_HEADLINE = "First purchase bonus"
_DEFAULT_MESSAGE = "Upgrade this order to get extra lead credits right away."
_DEFAULT_CTA_LABEL = "Upgrade package"


@dataclass
class _OfferSnapshot:
    is_enabled: bool
    trigger_package_id: Optional[int]
    offer_package_id: Optional[int]
    offer_credits_total: Optional[int]
    offer_price_cents: Optional[int]
    offer_currency: Optional[str]
    headline: Optional[str]
    message: Optional[str]
    cta_label: Optional[str]
    starts_at: Optional[datetime]
    ends_at: Optional[datetime]


class FirstPurchaseOfferService:
    @staticmethod
    def _get_singleton_config(db: Session) -> Optional[FirstPurchaseAddonOffer]:
        return (
            db.query(FirstPurchaseAddonOffer)
            .order_by(FirstPurchaseAddonOffer.id.asc())
            .first()
        )

    @staticmethod
    def _resolve_package_credits(package: LeadPackage) -> int:
        # Reuse purchase credit semantics so package UI and fulfillment agree.
        from app.services.subscription_service import SubscriptionService

        return SubscriptionService._resolve_package_credits(package)

    @staticmethod
    def _snapshot_config(config: FirstPurchaseAddonOffer) -> _OfferSnapshot:
        return _OfferSnapshot(
            is_enabled=bool(config.is_enabled),
            trigger_package_id=(int(config.trigger_package_id) if config.trigger_package_id is not None else None),
            offer_package_id=(int(config.offer_package_id) if config.offer_package_id is not None else None),
            offer_credits_total=(int(config.offer_credits_total) if config.offer_credits_total is not None else None),
            offer_price_cents=(int(config.offer_price_cents) if config.offer_price_cents is not None else None),
            offer_currency=(str(config.offer_currency).upper() if config.offer_currency else None),
            headline=config.headline,
            message=config.message,
            cta_label=config.cta_label,
            starts_at=config.starts_at,
            ends_at=config.ends_at,
        )

    @staticmethod
    def _serialize_snapshot_for_audit(snapshot: _OfferSnapshot) -> Dict[str, Any]:
        payload: Dict[str, Any] = asdict(snapshot)
        for key in ("starts_at", "ends_at"):
            value = payload.get(key)
            if isinstance(value, datetime):
                payload[key] = value.isoformat()
        return payload

    @staticmethod
    def _resolve_packages(
        db: Session,
        *,
        trigger_package_id: Optional[int],
        offer_package_id: Optional[int],
    ) -> Dict[int, LeadPackage]:
        package_ids = {
            int(package_id)
            for package_id in [trigger_package_id, offer_package_id]
            if package_id is not None
        }
        if not package_ids:
            return {}

        rows = (
            db.query(LeadPackage)
            .filter(LeadPackage.id.in_(package_ids))
            .all()
        )
        return {int(row.id): row for row in rows}

    @staticmethod
    def _is_managed_internal_offer_package(package: LeadPackage) -> bool:
        if not isinstance(package.features, dict):
            return False
        return package.features.get("managed_by") == "first_purchase_offer"

    @staticmethod
    def _upsert_internal_offer_package(
        db: Session,
        *,
        config: FirstPurchaseAddonOffer,
        trigger_package: LeadPackage,
    ) -> LeadPackage:
        if config.offer_credits_total is None or config.offer_price_cents is None:
            raise HTTPException(
                status_code=400,
                detail="offer_credits_total and offer_price_cents are required",
            )

        offer_package: Optional[LeadPackage] = None
        if config.offer_package_id is not None:
            offer_package = (
                db.query(LeadPackage)
                .filter(LeadPackage.id == config.offer_package_id)
                .first()
            )
            if offer_package is not None and not FirstPurchaseOfferService._is_managed_internal_offer_package(offer_package):
                raise HTTPException(
                    status_code=400,
                    detail="Configured offer_package_id is not a managed first-purchase add-on package",
                )

        if offer_package is None:
            offer_package = LeadPackage(
                name=f"First Purchase Add-on {int(config.id)} (+{int(config.offer_credits_total)} leads)",
                price_cents=int(config.offer_price_cents),
                currency=str((config.offer_currency or "USD")).upper(),
                stripe_price_id=f"dynamic_addon_{uuid4().hex[:24]}",
                state_limit=trigger_package.state_limit,
                daily_download_limit=int(config.offer_credits_total),
                features={
                    "managed_by": "first_purchase_offer",
                    "catalog_visible": False,
                    "trigger_package_id": int(trigger_package.id),
                },
            )
            db.add(offer_package)
            db.flush()
            return offer_package

        offer_package.price_cents = int(config.offer_price_cents)
        offer_package.currency = str((config.offer_currency or "USD")).upper()
        offer_package.daily_download_limit = int(config.offer_credits_total)
        offer_package.name = f"First Purchase Add-on {int(config.id)} (+{int(config.offer_credits_total)} leads)"
        offer_package.state_limit = trigger_package.state_limit
        existing_features = offer_package.features if isinstance(offer_package.features, dict) else {}
        offer_package.features = {
            **existing_features,
            "managed_by": "first_purchase_offer",
            "catalog_visible": False,
            "trigger_package_id": int(trigger_package.id),
        }
        db.add(offer_package)
        db.flush()
        return offer_package

    @staticmethod
    def _build_config_response(
        db: Session,
        config: Optional[FirstPurchaseAddonOffer],
    ) -> FirstPurchaseAddonOfferConfigResponse:
        if config is None:
            return FirstPurchaseAddonOfferConfigResponse(
                id=None,
                is_enabled=False,
                trigger_package_id=None,
                trigger_package_name=None,
                offer_package_id=None,
                offer_package_name=None,
                offer_price_cents=None,
                offer_currency=None,
                offer_credits_total=None,
            headline=None,
            message=None,
            cta_label=None,
                starts_at=None,
                ends_at=None,
                updated_at=None,
                updated_by=None,
            )

        trigger_package_id = int(config.trigger_package_id) if config.trigger_package_id is not None else None
        offer_package_id = int(config.offer_package_id) if config.offer_package_id is not None else None
        packages = FirstPurchaseOfferService._resolve_packages(
            db,
            trigger_package_id=trigger_package_id,
            offer_package_id=offer_package_id,
        )
        trigger_package = packages.get(trigger_package_id) if trigger_package_id is not None else None
        offer_package = packages.get(offer_package_id) if offer_package_id is not None else None

        return FirstPurchaseAddonOfferConfigResponse(
            id=int(config.id),
            is_enabled=bool(config.is_enabled),
            trigger_package_id=trigger_package_id,
            trigger_package_name=(trigger_package.name if trigger_package else None),
            offer_package_id=offer_package_id,
            offer_package_name=(offer_package.name if offer_package else None),
            offer_price_cents=(int(config.offer_price_cents) if config.offer_price_cents is not None else None),
            offer_currency=(str((config.offer_currency or "USD")).upper() if config.offer_currency else "USD"),
            offer_credits_total=(int(config.offer_credits_total) if config.offer_credits_total is not None else None),
            headline=config.headline,
            message=config.message,
            cta_label=config.cta_label,
            starts_at=config.starts_at,
            ends_at=config.ends_at,
            updated_at=config.updated_at,
            updated_by=(int(config.updated_by) if config.updated_by is not None else None),
        )

    @staticmethod
    def get_offer_config(db: Session) -> FirstPurchaseAddonOfferConfigResponse:
        config = FirstPurchaseOfferService._get_singleton_config(db)
        return FirstPurchaseOfferService._build_config_response(db, config)

    @staticmethod
    def update_offer_config(
        db: Session,
        *,
        admin_user: User,
        payload: FirstPurchaseAddonOfferUpdateRequest,
    ) -> FirstPurchaseAddonOfferConfigResponse:
        if payload.starts_at and payload.ends_at and payload.ends_at < payload.starts_at:
            raise HTTPException(status_code=400, detail="ends_at must be greater than or equal to starts_at")

        if payload.is_enabled:
            if (
                payload.trigger_package_id is None
                or payload.offer_credits_total is None
                or payload.offer_price_cents is None
            ):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Enabled offer requires trigger_package_id, "
                        "offer_credits_total, and offer_price_cents"
                    ),
                )

        trigger_package = None
        if payload.trigger_package_id is not None:
            trigger_package = (
                db.query(LeadPackage)
                .filter(LeadPackage.id == payload.trigger_package_id)
                .first()
            )
        if payload.trigger_package_id is not None and trigger_package is None:
            raise HTTPException(status_code=404, detail="Trigger package not found")

        config = FirstPurchaseOfferService._get_singleton_config(db)
        if config is None:
            config = FirstPurchaseAddonOffer()
            db.add(config)
            db.flush()

        before = FirstPurchaseOfferService._snapshot_config(config)

        config.is_enabled = bool(payload.is_enabled)
        config.trigger_package_id = payload.trigger_package_id
        config.offer_credits_total = payload.offer_credits_total
        config.offer_price_cents = payload.offer_price_cents
        config.offer_currency = str((payload.offer_currency or "USD")).upper()
        config.headline = payload.headline
        config.message = payload.message
        config.cta_label = payload.cta_label
        config.starts_at = payload.starts_at
        config.ends_at = payload.ends_at
        config.updated_by = int(admin_user.id)

        try:
            if config.is_enabled and config.trigger_package_id is not None and trigger_package is not None:
                managed_offer_package = FirstPurchaseOfferService._upsert_internal_offer_package(
                    db,
                    config=config,
                    trigger_package=trigger_package,
                )
                config.offer_package_id = int(managed_offer_package.id)
            elif not config.is_enabled:
                config.offer_package_id = None

            db.add(config)
            db.commit()
            db.refresh(config)
        except HTTPException:
            db.rollback()
            raise
        except Exception as exc:
            db.rollback()
            logger.error("Failed to update first-purchase add-on offer config: %s", exc)
            raise HTTPException(status_code=500, detail="Failed to save first-purchase add-on offer")

        after = FirstPurchaseOfferService._snapshot_config(config)
        if asdict(before) != asdict(after):
            AuditService.log_event(
                actor_user_id=admin_user.id,
                action="first_purchase_addon_offer_updated",
                entity_type="FirstPurchaseAddonOffer",
                entity_id=int(config.id),
                meta_data={
                    "before": FirstPurchaseOfferService._serialize_snapshot_for_audit(before),
                    "after": FirstPurchaseOfferService._serialize_snapshot_for_audit(after),
                },
            )

        return FirstPurchaseOfferService._build_config_response(db, config)

    @staticmethod
    def _is_offer_window_active(config: FirstPurchaseAddonOffer) -> bool:
        now = utcnow()
        if config.starts_at is not None and now < config.starts_at:
            return False
        if config.ends_at is not None and now > config.ends_at:
            return False
        return True

    @staticmethod
    def _is_user_eligible_for_offer_package(
        db: Session,
        *,
        user: User,
        offer_package_id: int,
        required_trigger_checkout_session_id: Optional[str] = None,
    ) -> bool:
        config = FirstPurchaseOfferService._get_singleton_config(db)
        if config is None or not config.is_enabled:
            return False

        if config.trigger_package_id is None:
            return False

        if config.offer_package_id is None or not FirstPurchaseOfferService._is_offer_window_active(config):
            return False

        if int(config.offer_package_id) != int(offer_package_id):
            return False

        # Limit=2 lets us verify "exactly one completed purchase" with a single query.
        completed_purchases = (
            db.query(LeadPurchase)
            .filter(
                LeadPurchase.user_id == user.id,
                LeadPurchase.status == "completed",
            )
            .order_by(LeadPurchase.purchased_at.asc(), LeadPurchase.id.asc())
            .limit(2)
            .all()
        )
        if len(completed_purchases) != 1:
            return False

        first_completed_purchase = completed_purchases[0]
        if int(first_completed_purchase.package_id) != int(config.trigger_package_id):
            return False

        if (
            required_trigger_checkout_session_id is not None
            and first_completed_purchase.stripe_checkout_session_id != required_trigger_checkout_session_id
        ):
            return False

        return True

    @staticmethod
    def can_user_purchase_offer_package(
        db: Session,
        *,
        user: User,
        offer_package_id: int,
    ) -> bool:
        return FirstPurchaseOfferService._is_user_eligible_for_offer_package(
            db,
            user=user,
            offer_package_id=offer_package_id,
            required_trigger_checkout_session_id=None,
        )

    @staticmethod
    def get_advisor_offer_eligibility(
        db: Session,
        *,
        user: User,
        checkout_session_id: str,
    ) -> FirstPurchaseAddonOfferEligibilityResponse:
        config = FirstPurchaseOfferService._get_singleton_config(db)
        if config is None or config.offer_package_id is None:
            return FirstPurchaseAddonOfferEligibilityResponse(eligible=False, offer=None)

        if not FirstPurchaseOfferService._is_user_eligible_for_offer_package(
            db,
            user=user,
            offer_package_id=int(config.offer_package_id),
            required_trigger_checkout_session_id=checkout_session_id,
        ):
            return FirstPurchaseAddonOfferEligibilityResponse(eligible=False, offer=None)

        offer_package = (
            db.query(LeadPackage)
            .filter(LeadPackage.id == config.offer_package_id)
            .first()
        )
        if offer_package is None:
            return FirstPurchaseAddonOfferEligibilityResponse(eligible=False, offer=None)

        offer = FirstPurchaseAddonOfferAdvisorResponse(
            trigger_package_id=int(config.trigger_package_id),
            offer_package_id=int(offer_package.id),
            offer_package_name=str(offer_package.name),
            offer_price_cents=int(config.offer_price_cents or offer_package.price_cents),
            offer_currency=str((config.offer_currency or offer_package.currency or "USD")).upper(),
            offer_credits_total=int(
                config.offer_credits_total
                if config.offer_credits_total is not None
                else FirstPurchaseOfferService._resolve_package_credits(offer_package)
            ),
            headline=str(config.headline or _DEFAULT_HEADLINE),
            message=str(config.message or _DEFAULT_MESSAGE),
            cta_label=str(config.cta_label or _DEFAULT_CTA_LABEL),
        )
        return FirstPurchaseAddonOfferEligibilityResponse(eligible=True, offer=offer)
