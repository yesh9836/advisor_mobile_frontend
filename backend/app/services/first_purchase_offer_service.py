import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.currency import USD_CURRENCY, require_usd_currency
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
from app.services.lead_service import LeadService

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


@dataclass(frozen=True)
class OfferEligibilityDecision:
    allowed: bool
    code: Optional[str] = None
    message: Optional[str] = None
    available_count: Optional[int] = None
    required_count: Optional[int] = None

    def to_error_detail(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "code": str(self.code or "UNKNOWN"),
            "message": str(self.message or "Package is not available for this account"),
        }
        if self.available_count is not None:
            payload["available_count"] = int(self.available_count)
        if self.required_count is not None:
            payload["required_count"] = int(self.required_count)
        return payload


class FirstPurchaseOfferService:
    REJECTION_OFFER_DISABLED = "OFFER_DISABLED"
    REJECTION_OFFER_WINDOW_CLOSED = "OFFER_WINDOW_CLOSED"
    REJECTION_OFFER_NOT_CONFIGURED = "OFFER_NOT_CONFIGURED"
    REJECTION_OFFER_PACKAGE_MISMATCH = "OFFER_PACKAGE_MISMATCH"
    REJECTION_OFFER_NOT_FIRST_PURCHASE = "OFFER_NOT_FIRST_PURCHASE"
    REJECTION_OFFER_TRIGGER_MISMATCH = "OFFER_TRIGGER_MISMATCH"
    REJECTION_OFFER_CHECKOUT_MISMATCH = "OFFER_CHECKOUT_MISMATCH"
    REJECTION_LICENSE_STATES_UNAVAILABLE = "LICENSE_STATES_UNAVAILABLE"
    REJECTION_INVENTORY_UNAVAILABLE = "INVENTORY_UNAVAILABLE"
    _MANAGED_PACKAGE_NAME_CONFLICT_DETAIL = (
        "Managed first-purchase add-on package name is already in use by another plan"
    )

    @staticmethod
    def _require_offer_currency(value: Optional[str]) -> str:
        try:
            return require_usd_currency(value, field_name="offer_currency")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

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
    def _build_internal_offer_package_name(
        *,
        config_id: int,
        offer_credits_total: int,
    ) -> str:
        return f"First Purchase Add-on {int(config_id)} (+{int(offer_credits_total)} leads)"

    @staticmethod
    def _build_internal_offer_package_name_prefix(*, config_id: int) -> str:
        return f"First Purchase Add-on {int(config_id)} ("

    @staticmethod
    def _build_internal_offer_package_fallback_name(*, config_id: int) -> str:
        return f"First Purchase Add-on {int(config_id)} (managed {uuid4().hex[:6]})"

    @staticmethod
    def _is_duplicate_managed_package_name_integrity_error(exc: IntegrityError) -> bool:
        details = " ".join(
            [
                str(exc).lower(),
                str(getattr(exc, "orig", "")).lower(),
                str(getattr(exc, "statement", "")).lower(),
                str(getattr(exc, "params", "")).lower(),
            ]
        )
        has_duplicate_marker = any(
            marker in details
            for marker in (
                "duplicate",
                "duplicate entry",
                "duplicate key value",
                "unique constraint",
                "unique constraint failed",
            )
        )
        has_package_name_marker = any(
            marker in details
            for marker in (
                "lead_packages",
                "ix_lead_packages_name",
                "lead_packages.name",
            )
        )
        return has_duplicate_marker and has_package_name_marker

    @staticmethod
    def _resolve_managed_package_when_link_missing(
        db: Session,
        *,
        config: FirstPurchaseAddonOffer,
        expected_name: str,
    ) -> Optional[LeadPackage]:
        exact_name_row = db.query(LeadPackage).filter(LeadPackage.name == expected_name).first()
        if exact_name_row is not None:
            if FirstPurchaseOfferService._is_managed_internal_offer_package(exact_name_row):
                return exact_name_row

        name_prefix = FirstPurchaseOfferService._build_internal_offer_package_name_prefix(config_id=int(config.id))
        prefix_rows = (
            db.query(LeadPackage)
            .filter(LeadPackage.name.like(f"{name_prefix}%"))
            .order_by(LeadPackage.id.desc())
            .all()
        )
        managed_candidates = [
            row for row in prefix_rows if FirstPurchaseOfferService._is_managed_internal_offer_package(row)
        ]
        if not managed_candidates:
            return None

        for row in managed_candidates:
            features = row.features if isinstance(row.features, dict) else {}
            if int(features.get("managed_config_id") or 0) == int(config.id):
                return row
        return managed_candidates[0]

    @staticmethod
    def _apply_managed_offer_package_values(
        *,
        offer_package: LeadPackage,
        config: FirstPurchaseAddonOffer,
        trigger_package: LeadPackage,
        offer_currency: str,
        expected_name: str,
    ) -> None:
        offer_package.price_cents = int(config.offer_price_cents or 0)
        offer_package.currency = offer_currency
        offer_package.daily_download_limit = int(config.offer_credits_total or 0)
        if not str(offer_package.name or "").strip():
            offer_package.name = expected_name
        offer_package.state_limit = trigger_package.state_limit
        existing_features = offer_package.features if isinstance(offer_package.features, dict) else {}
        offer_package.features = {
            **existing_features,
            "managed_by": "first_purchase_offer",
            "managed_config_id": int(config.id),
            "catalog_visible": False,
            "trigger_package_id": int(trigger_package.id),
        }

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

        offer_currency = FirstPurchaseOfferService._require_offer_currency(config.offer_currency)
        expected_name = FirstPurchaseOfferService._build_internal_offer_package_name(
            config_id=int(config.id),
            offer_credits_total=int(config.offer_credits_total),
        )
        if offer_package is None:
            offer_package = FirstPurchaseOfferService._resolve_managed_package_when_link_missing(
                db,
                config=config,
                expected_name=expected_name,
            )
        if offer_package is None:
            new_offer_package = LeadPackage(
                name=expected_name,
                price_cents=int(config.offer_price_cents),
                currency=offer_currency,
                stripe_price_id=f"dynamic_addon_{uuid4().hex[:24]}",
                state_limit=trigger_package.state_limit,
                daily_download_limit=int(config.offer_credits_total),
                features={
                    "managed_by": "first_purchase_offer",
                    "managed_config_id": int(config.id),
                    "catalog_visible": False,
                    "trigger_package_id": int(trigger_package.id),
                },
            )
            try:
                # Savepoint keeps parent transaction alive for duplicate-name races.
                with db.begin_nested():
                    db.add(new_offer_package)
                    db.flush()
                return new_offer_package
            except IntegrityError as exc:
                if not FirstPurchaseOfferService._is_duplicate_managed_package_name_integrity_error(exc):
                    raise
                offer_package = FirstPurchaseOfferService._resolve_managed_package_when_link_missing(
                    db,
                    config=config,
                    expected_name=expected_name,
                )
                if offer_package is None:
                    fallback_offer_package = LeadPackage(
                        name=FirstPurchaseOfferService._build_internal_offer_package_fallback_name(
                            config_id=int(config.id)
                        ),
                        price_cents=int(config.offer_price_cents),
                        currency=offer_currency,
                        stripe_price_id=f"dynamic_addon_{uuid4().hex[:24]}",
                        state_limit=trigger_package.state_limit,
                        daily_download_limit=int(config.offer_credits_total),
                        features={
                            "managed_by": "first_purchase_offer",
                            "managed_config_id": int(config.id),
                            "catalog_visible": False,
                            "trigger_package_id": int(trigger_package.id),
                        },
                    )
                    try:
                        with db.begin_nested():
                            db.add(fallback_offer_package)
                            db.flush()
                        return fallback_offer_package
                    except IntegrityError:
                        raise HTTPException(
                            status_code=409,
                            detail=FirstPurchaseOfferService._MANAGED_PACKAGE_NAME_CONFLICT_DETAIL,
                        ) from exc

        FirstPurchaseOfferService._apply_managed_offer_package_values(
            offer_package=offer_package,
            config=config,
            trigger_package=trigger_package,
            offer_currency=offer_currency,
            expected_name=expected_name,
        )
        db.add(offer_package)
        db.flush()
        return offer_package

    @staticmethod
    def _build_config_response(
        db: Session,
        config: Optional[FirstPurchaseAddonOffer],
    ) -> FirstPurchaseAddonOfferConfigResponse:
        inventory_gate = FirstPurchaseOfferService._build_admin_inventory_gate_snapshot(
            db=db,
            config=config,
        )
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
                inventory_ready=inventory_gate["inventory_ready"],
                inventory_available_count=inventory_gate["inventory_available_count"],
                inventory_required_count=inventory_gate["inventory_required_count"],
                inventory_gate_code=inventory_gate["inventory_gate_code"],
                inventory_gate_message=inventory_gate["inventory_gate_message"],
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
            offer_currency=USD_CURRENCY,
            offer_credits_total=(int(config.offer_credits_total) if config.offer_credits_total is not None else None),
            headline=config.headline,
            message=config.message,
            cta_label=config.cta_label,
            starts_at=config.starts_at,
            ends_at=config.ends_at,
            updated_at=config.updated_at,
            updated_by=(int(config.updated_by) if config.updated_by is not None else None),
            inventory_ready=inventory_gate["inventory_ready"],
            inventory_available_count=inventory_gate["inventory_available_count"],
            inventory_required_count=inventory_gate["inventory_required_count"],
            inventory_gate_code=inventory_gate["inventory_gate_code"],
            inventory_gate_message=inventory_gate["inventory_gate_message"],
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
        config.offer_currency = FirstPurchaseOfferService._require_offer_currency(payload.offer_currency)
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

            db.add(config)
            db.commit()
            db.refresh(config)
        except HTTPException:
            db.rollback()
            raise
        except IntegrityError as exc:
            db.rollback()
            if FirstPurchaseOfferService._is_duplicate_managed_package_name_integrity_error(exc):
                raise HTTPException(
                    status_code=409,
                    detail=FirstPurchaseOfferService._MANAGED_PACKAGE_NAME_CONFLICT_DETAIL,
                ) from exc
            logger.error("Failed to update first-purchase add-on offer config with integrity error: %s", exc)
            raise HTTPException(status_code=500, detail="Failed to save first-purchase add-on offer")
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
    def _resolve_offer_required_inventory_count(
        *,
        config: FirstPurchaseAddonOffer,
        offer_package: Optional[LeadPackage],
    ) -> int:
        if config.offer_credits_total is not None:
            return max(int(config.offer_credits_total), 1)
        if offer_package is not None:
            return max(int(FirstPurchaseOfferService._resolve_package_credits(offer_package)), 1)
        return 1

    @staticmethod
    def _decision_denied(
        *,
        code: str,
        message: str,
        available_count: Optional[int] = None,
        required_count: Optional[int] = None,
    ) -> OfferEligibilityDecision:
        return OfferEligibilityDecision(
            allowed=False,
            code=code,
            message=message,
            available_count=available_count,
            required_count=required_count,
        )

    @staticmethod
    def _resolve_offer_purchase_eligibility(
        db: Session,
        *,
        user: User,
        offer_package_id: int,
        required_trigger_checkout_session_id: Optional[str] = None,
    ) -> OfferEligibilityDecision:
        config = FirstPurchaseOfferService._get_singleton_config(db)
        if config is None or not config.is_enabled:
            return FirstPurchaseOfferService._decision_denied(
                code=FirstPurchaseOfferService.REJECTION_OFFER_DISABLED,
                message="First-purchase add-on offer is not enabled",
            )

        if config.trigger_package_id is None:
            return FirstPurchaseOfferService._decision_denied(
                code=FirstPurchaseOfferService.REJECTION_OFFER_NOT_CONFIGURED,
                message="First-purchase add-on trigger package is not configured",
            )

        if config.offer_package_id is None:
            return FirstPurchaseOfferService._decision_denied(
                code=FirstPurchaseOfferService.REJECTION_OFFER_NOT_CONFIGURED,
                message="First-purchase add-on offer package is not configured",
            )

        if not FirstPurchaseOfferService._is_offer_window_active(config):
            return FirstPurchaseOfferService._decision_denied(
                code=FirstPurchaseOfferService.REJECTION_OFFER_WINDOW_CLOSED,
                message="First-purchase add-on offer is currently outside its active window",
            )

        if int(config.offer_package_id) != int(offer_package_id):
            return FirstPurchaseOfferService._decision_denied(
                code=FirstPurchaseOfferService.REJECTION_OFFER_PACKAGE_MISMATCH,
                message="Requested package does not match the configured first-purchase add-on offer",
            )

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
            return FirstPurchaseOfferService._decision_denied(
                code=FirstPurchaseOfferService.REJECTION_OFFER_NOT_FIRST_PURCHASE,
                message="First-purchase add-on is only available after exactly one completed purchase",
            )

        first_completed_purchase = completed_purchases[0]
        if int(first_completed_purchase.package_id) != int(config.trigger_package_id):
            return FirstPurchaseOfferService._decision_denied(
                code=FirstPurchaseOfferService.REJECTION_OFFER_TRIGGER_MISMATCH,
                message="First completed purchase does not match the configured trigger package",
            )

        if (
            required_trigger_checkout_session_id is not None
            and first_completed_purchase.stripe_checkout_session_id != required_trigger_checkout_session_id
        ):
            return FirstPurchaseOfferService._decision_denied(
                code=FirstPurchaseOfferService.REJECTION_OFFER_CHECKOUT_MISMATCH,
                message="Offer request is not tied to the triggering checkout session",
            )

        offer_package = (
            db.query(LeadPackage)
            .filter(LeadPackage.id == int(config.offer_package_id))
            .first()
        )
        required_count = FirstPurchaseOfferService._resolve_offer_required_inventory_count(
            config=config,
            offer_package=offer_package,
        )
        inventory_snapshot = LeadService.get_unsold_inventory_snapshot_for_user(db=db, user=user)
        scoped_states = inventory_snapshot.get("state_codes") or []
        available_count = int(inventory_snapshot.get("available_count") or 0)
        if not scoped_states:
            return FirstPurchaseOfferService._decision_denied(
                code=FirstPurchaseOfferService.REJECTION_LICENSE_STATES_UNAVAILABLE,
                message="No verified license states available for offer inventory eligibility",
                available_count=available_count,
                required_count=required_count,
            )
        if available_count < required_count:
            return FirstPurchaseOfferService._decision_denied(
                code=FirstPurchaseOfferService.REJECTION_INVENTORY_UNAVAILABLE,
                message="Add-on inventory is temporarily unavailable for your licensed states",
                available_count=available_count,
                required_count=required_count,
            )

        return OfferEligibilityDecision(
            allowed=True,
            available_count=available_count,
            required_count=required_count,
        )

    @staticmethod
    def get_offer_purchase_eligibility_decision(
        db: Session,
        *,
        user: User,
        offer_package_id: int,
        required_trigger_checkout_session_id: Optional[str] = None,
    ) -> OfferEligibilityDecision:
        return FirstPurchaseOfferService._resolve_offer_purchase_eligibility(
            db=db,
            user=user,
            offer_package_id=offer_package_id,
            required_trigger_checkout_session_id=required_trigger_checkout_session_id,
        )

    @staticmethod
    def _build_admin_inventory_gate_snapshot(
        db: Session,
        *,
        config: Optional[FirstPurchaseAddonOffer],
    ) -> Dict[str, Any]:
        if config is None or not config.is_enabled:
            return {
                "inventory_ready": None,
                "inventory_available_count": None,
                "inventory_required_count": None,
                "inventory_gate_code": None,
                "inventory_gate_message": None,
            }

        required_count = max(int(config.offer_credits_total or 0), 1)
        available_count = LeadService.get_global_unsold_inventory_count(db=db)
        if available_count < required_count:
            return {
                "inventory_ready": False,
                "inventory_available_count": available_count,
                "inventory_required_count": required_count,
                "inventory_gate_code": FirstPurchaseOfferService.REJECTION_INVENTORY_UNAVAILABLE,
                "inventory_gate_message": "Global add-on inventory is currently below the required threshold",
            }

        return {
            "inventory_ready": True,
            "inventory_available_count": available_count,
            "inventory_required_count": required_count,
            "inventory_gate_code": None,
            "inventory_gate_message": None,
        }

    @staticmethod
    def can_user_purchase_offer_package(
        db: Session,
        *,
        user: User,
        offer_package_id: int,
    ) -> bool:
        return FirstPurchaseOfferService._resolve_offer_purchase_eligibility(
            db,
            user=user,
            offer_package_id=offer_package_id,
            required_trigger_checkout_session_id=None,
        ).allowed

    @staticmethod
    def get_advisor_offer_eligibility(
        db: Session,
        *,
        user: User,
        checkout_session_id: str,
    ) -> FirstPurchaseAddonOfferEligibilityResponse:
        config = FirstPurchaseOfferService._get_singleton_config(db)
        if config is None or config.offer_package_id is None:
            return FirstPurchaseAddonOfferEligibilityResponse(
                eligible=False,
                offer=None,
                rejection_code=FirstPurchaseOfferService.REJECTION_OFFER_NOT_CONFIGURED,
                rejection_message="First-purchase add-on offer is not configured",
                inventory_available_count=None,
                inventory_required_count=None,
            )

        decision = FirstPurchaseOfferService._resolve_offer_purchase_eligibility(
            db,
            user=user,
            offer_package_id=int(config.offer_package_id),
            required_trigger_checkout_session_id=checkout_session_id,
        )
        if not decision.allowed:
            return FirstPurchaseAddonOfferEligibilityResponse(
                eligible=False,
                offer=None,
                rejection_code=decision.code,
                rejection_message=decision.message,
                inventory_available_count=decision.available_count,
                inventory_required_count=decision.required_count,
            )

        offer_package = (
            db.query(LeadPackage)
            .filter(LeadPackage.id == config.offer_package_id)
            .first()
        )
        if offer_package is None:
            return FirstPurchaseAddonOfferEligibilityResponse(
                eligible=False,
                offer=None,
                rejection_code=FirstPurchaseOfferService.REJECTION_OFFER_NOT_CONFIGURED,
                rejection_message="Configured first-purchase add-on package was not found",
                inventory_available_count=decision.available_count,
                inventory_required_count=decision.required_count,
            )

        offer = FirstPurchaseAddonOfferAdvisorResponse(
            trigger_package_id=int(config.trigger_package_id),
            offer_package_id=int(offer_package.id),
            offer_package_name=str(offer_package.name),
            offer_price_cents=int(config.offer_price_cents or offer_package.price_cents),
            offer_currency=USD_CURRENCY,
            offer_credits_total=int(
                config.offer_credits_total
                if config.offer_credits_total is not None
                else FirstPurchaseOfferService._resolve_package_credits(offer_package)
            ),
            headline=str(config.headline or _DEFAULT_HEADLINE),
            message=str(config.message or _DEFAULT_MESSAGE),
            cta_label=str(config.cta_label or _DEFAULT_CTA_LABEL),
        )
        return FirstPurchaseAddonOfferEligibilityResponse(
            eligible=True,
            offer=offer,
            rejection_code=None,
            rejection_message=None,
            inventory_available_count=decision.available_count,
            inventory_required_count=decision.required_count,
        )
