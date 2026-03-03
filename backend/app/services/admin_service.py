import csv
import io
import logging
from decimal import Decimal
from typing import Any, Dict, Generator, Optional

from fastapi import HTTPException
from sqlalchemy import case, func, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.timezone import utcnow
from app.models.audit_log import AuditLog
from app.models.lead import Lead, LeadDownload, LeadOwnership
from app.models.license import License
from app.models.purchase import LeadPackage, LeadPurchase
from app.models.user import User
from app.schemas.admin import (
    AdminAnalyticsOverview,
    AdminOrderItem,
    AuditLogFilters,
    DashboardStats,
    ImportStats,
    LeadInventoryFilters,
    LeadInventoryItem,
    LicenseStatusSummaryItem,
    AdminPlanArchiveRequest,
    AdminPlanCreateRequest,
    AdminPlanItem,
    AdminPlanListFilters,
    AdminPlanUpdateRequest,
    MonthlyRevenuePoint,
    PaginatedAuditLogs,
    PaginatedAdminPlans,
    PaginatedLeadInventory,
    PaginatedOrders,
    PaginatedUsers,
    PlanBreakdownItem,
    StateDistributionItem,
    UserDetails,
    UserDownloadHistoryItem,
    UserGrowthPoint,
    UserCreditSummary,
    UserLicenseItem,
    UserListFilters,
    UserListItem,
    UserPurchaseItem,
    UserRecentActivityItem,
)
from app.services.audit_service import AuditService
from app.services.admin_audit_service import AdminAuditService
from app.services.auth_service import AuthService
from app.services.payment_service import PaymentService
from app.services.stripe_plan_cleanup_outbox_service import StripePlanCleanupOutboxService

logger = logging.getLogger(__name__)


class AdminService:
    @staticmethod
    def _is_first_purchase_offer_managed_package(package: LeadPackage) -> bool:
        return isinstance(package.features, dict) and package.features.get("managed_by") == "first_purchase_offer"

    @staticmethod
    def _resolve_plan_credits_total(package: LeadPackage) -> int:
        if isinstance(package.features, dict):
            raw_credits = package.features.get("credits_total")
            if raw_credits is None:
                raw_credits = package.features.get("credits")
            try:
                if raw_credits is not None:
                    return max(int(raw_credits), 0)
            except (TypeError, ValueError):
                pass
        return max(int(package.daily_download_limit or 0), 0)

    @staticmethod
    def _resolve_plan_catalog_visible(package: LeadPackage) -> bool:
        if not isinstance(package.features, dict):
            return True
        return package.features.get("catalog_visible", True) is not False

    @staticmethod
    def _is_plan_effective_at(package: LeadPackage, at_time) -> bool:
        if package.effective_from is not None and at_time < package.effective_from:
            return False
        if package.effective_to is not None and at_time > package.effective_to:
            return False
        return True

    @staticmethod
    def _validate_effective_window(*, effective_from, effective_to) -> None:
        if effective_from is not None and effective_to is not None and effective_to < effective_from:
            raise HTTPException(
                status_code=400,
                detail="effective_to must be greater than or equal to effective_from",
            )

    @staticmethod
    def _raise_plan_lifecycle_write_error(
        *,
        operation: str,
        exc: Exception,
        plan_id: Optional[int],
        request_id: Optional[str],
        db_error_detail: str,
        unknown_error_detail: str,
    ) -> None:
        if isinstance(exc, SQLAlchemyError):
            logger.error(
                "Admin plan lifecycle write failed failure_class=db_write_error operation=%s plan_id=%s request_id=%s error=%s",
                operation,
                plan_id,
                request_id,
                exc,
            )
            raise HTTPException(status_code=500, detail=db_error_detail)

        logger.exception(
            "Admin plan lifecycle write failed failure_class=unexpected_error operation=%s plan_id=%s request_id=%s",
            operation,
            plan_id,
            request_id,
        )
        raise HTTPException(status_code=500, detail=unknown_error_detail)

    @staticmethod
    def _rollback_unarchive_after_db_failure(
        db: Session,
        *,
        plan_id: int,
        stripe_price_id: Optional[str],
        stripe_product_id: Optional[str],
        reason: Optional[str],
    ) -> None:
        db.rollback()
        try:
            PaymentService.deactivate_stripe_plan_artifacts(
                stripe_price_id=stripe_price_id,
                stripe_product_id=stripe_product_id,
            )
        except Exception as cleanup_exc:
            logger.warning(
                "Failed rollback Stripe deactivation after unarchive DB failure plan_id=%s: %s",
                plan_id,
                cleanup_exc,
            )
            try:
                StripePlanCleanupOutboxService.enqueue_cleanup(
                    db=db,
                    source="admin_plan_unarchive_rollback",
                    stripe_price_id=stripe_price_id,
                    stripe_product_id=stripe_product_id,
                    payload={
                        "plan_id": int(plan_id),
                        "reason": reason,
                        "rollback": True,
                    },
                )
            except Exception as outbox_exc:
                logger.error(
                    "Failed to enqueue rollback cleanup after unarchive DB failure plan_id=%s: %s",
                    plan_id,
                    outbox_exc,
                )

    @staticmethod
    def _schedule_stripe_cleanup_after_plan_write_failure(
        db: Session,
        *,
        source: str,
        stripe_refs: Optional[Dict[str, Optional[str]]],
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not stripe_refs:
            return

        stripe_price_id = str(stripe_refs.get("stripe_price_id") or "").strip() or None
        stripe_product_id = str(stripe_refs.get("stripe_product_id") or "").strip() or None
        if stripe_price_id is None and stripe_product_id is None:
            return

        try:
            PaymentService.deactivate_stripe_plan_artifacts(
                stripe_price_id=stripe_price_id,
                stripe_product_id=stripe_product_id,
            )
            return
        except Exception as cleanup_exc:
            logger.warning(
                "Immediate Stripe cleanup failed source=%s price_id=%s product_id=%s error=%s",
                source,
                stripe_price_id,
                stripe_product_id,
                cleanup_exc,
            )

        try:
            enqueued = StripePlanCleanupOutboxService.enqueue_cleanup(
                db=db,
                source=source,
                stripe_price_id=stripe_price_id,
                stripe_product_id=stripe_product_id,
                payload=payload,
            )
            if enqueued:
                logger.warning(
                    "Enqueued Stripe cleanup outbox row source=%s price_id=%s product_id=%s",
                    source,
                    stripe_price_id,
                    stripe_product_id,
                )
        except Exception as enqueue_exc:
            logger.exception(
                "Failed to enqueue Stripe cleanup outbox source=%s price_id=%s product_id=%s error=%s",
                source,
                stripe_price_id,
                stripe_product_id,
                enqueue_exc,
            )

    @staticmethod
    def _plan_has_purchases(db: Session, *, plan_id: int) -> bool:
        purchase_exists = (
            db.query(LeadPurchase.id)
            .filter(LeadPurchase.package_id == plan_id)
            .limit(1)
            .first()
        )
        return purchase_exists is not None

    @staticmethod
    def _serialize_plan_snapshot(
        package: LeadPackage,
        *,
        has_purchases: bool,
    ) -> Dict[str, Any]:
        return {
            "id": int(package.id),
            "name": str(package.name),
            "price_cents": int(package.price_cents or 0),
            "currency": str(package.currency or "USD").upper(),
            "stripe_product_id": package.stripe_product_id,
            "stripe_price_id": str(package.stripe_price_id),
            "state_limit": int(package.state_limit) if package.state_limit is not None else None,
            "credits_total": AdminService._resolve_plan_credits_total(package),
            "catalog_visible": AdminService._resolve_plan_catalog_visible(package),
            "is_archived": bool(package.is_archived),
            "archived_at": package.archived_at.isoformat() if package.archived_at is not None else None,
            "effective_from": package.effective_from.isoformat() if package.effective_from is not None else None,
            "effective_to": package.effective_to.isoformat() if package.effective_to is not None else None,
            "updated_by": int(package.updated_by) if package.updated_by is not None else None,
            "created_at": package.created_at.isoformat() if package.created_at is not None else None,
            "updated_at": package.updated_at.isoformat() if package.updated_at is not None else None,
            "has_purchases": bool(has_purchases),
        }

    @staticmethod
    def _to_admin_plan_item(
        package: LeadPackage,
        *,
        has_purchases: bool,
    ) -> AdminPlanItem:
        return AdminPlanItem(
            id=int(package.id),
            name=str(package.name),
            price_cents=int(package.price_cents or 0),
            currency=str(package.currency or "USD").upper(),
            stripe_product_id=package.stripe_product_id,
            stripe_price_id=str(package.stripe_price_id),
            state_limit=int(package.state_limit) if package.state_limit is not None else None,
            credits_total=AdminService._resolve_plan_credits_total(package),
            catalog_visible=AdminService._resolve_plan_catalog_visible(package),
            is_archived=bool(package.is_archived),
            archived_at=package.archived_at,
            effective_from=package.effective_from,
            effective_to=package.effective_to,
            created_at=package.created_at,
            updated_at=package.updated_at,
            updated_by=int(package.updated_by) if package.updated_by is not None else None,
            has_purchases=bool(has_purchases),
        )

    @staticmethod
    def _get_manageable_plan_or_404(db: Session, *, plan_id: int) -> LeadPackage:
        package = db.query(LeadPackage).filter(LeadPackage.id == plan_id).first()
        if package is None:
            raise HTTPException(status_code=404, detail="Plan not found")
        if AdminService._is_first_purchase_offer_managed_package(package):
            raise HTTPException(status_code=404, detail="Plan not found")
        return package

    @staticmethod
    def _managed_by_value_expression(db: Session):
        bind = db.get_bind()
        dialect_name = bind.dialect.name if bind is not None else ""
        if dialect_name == "mysql":
            return func.json_unquote(func.json_extract(LeadPackage.features, "$.managed_by"))
        return func.json_extract(LeadPackage.features, "$.managed_by")

    @staticmethod
    def _build_plan_listing_query(
        db: Session,
        *,
        filters: AdminPlanListFilters,
    ):
        query = db.query(LeadPackage)
        managed_by = AdminService._managed_by_value_expression(db)
        query = query.filter(or_(managed_by.is_(None), managed_by != "first_purchase_offer"))

        if filters.search:
            query = query.filter(LeadPackage.name.ilike(f"%{filters.search}%"))

        if filters.archived == "archived":
            query = query.filter(LeadPackage.is_archived.is_(True))
        elif filters.archived == "unarchived":
            query = query.filter(LeadPackage.is_archived.is_(False))

        if filters.effective_at is not None:
            query = query.filter(
                or_(
                    LeadPackage.effective_from.is_(None),
                    LeadPackage.effective_from <= filters.effective_at,
                )
            ).filter(
                or_(
                    LeadPackage.effective_to.is_(None),
                    LeadPackage.effective_to >= filters.effective_at,
                )
            )

        return query

    @staticmethod
    def list_plans(
        db: Session,
        *,
        page: int,
        size: int,
        filters: AdminPlanListFilters,
    ) -> PaginatedAdminPlans:
        filtered_query = AdminService._build_plan_listing_query(db, filters=filters)
        offset = max(0, (page - 1) * size)
        total = filtered_query.with_entities(func.count(LeadPackage.id)).scalar() or 0
        rows = (
            filtered_query
            .order_by(LeadPackage.created_at.desc(), LeadPackage.id.desc())
            .offset(offset)
            .limit(size)
            .all()
        )

        purchase_counts: Dict[int, int] = {}
        row_ids = [int(package.id) for package in rows]
        if row_ids:
            purchase_counts = {
                int(package_id): int(purchase_count or 0)
                for package_id, purchase_count in (
                    db.query(
                        LeadPurchase.package_id.label("package_id"),
                        func.count(LeadPurchase.id).label("purchase_count"),
                    )
                    .filter(LeadPurchase.package_id.in_(row_ids))
                    .group_by(LeadPurchase.package_id)
                    .all()
                )
            }

        items = [
            AdminService._to_admin_plan_item(
                package,
                has_purchases=bool(purchase_counts.get(int(package.id), 0)),
            )
            for package in rows
        ]
        return PaginatedAdminPlans(items=items, total=total, page=page, size=size)

    @staticmethod
    def create_plan(
        db: Session,
        *,
        admin_user: User,
        payload: AdminPlanCreateRequest,
    ) -> AdminPlanItem:
        AdminService._validate_effective_window(
            effective_from=payload.effective_from,
            effective_to=payload.effective_to,
        )

        duplicate = db.query(LeadPackage).filter(LeadPackage.name == payload.name).first()
        if duplicate is not None:
            raise HTTPException(status_code=409, detail="Plan name already exists")

        stripe_refs = PaymentService.create_stripe_price_for_plan(
            request_id=payload.request_id,
            plan_name=payload.name,
            price_cents=payload.price_cents,
            metadata={
                "source": "admin_plan_create",
                "admin_user_id": str(admin_user.id),
                "request_id": payload.request_id,
            },
        )

        package = LeadPackage(
            name=payload.name,
            price_cents=int(payload.price_cents),
            currency="USD",
            stripe_product_id=stripe_refs.get("stripe_product_id"),
            stripe_price_id=str(stripe_refs["stripe_price_id"]),
            state_limit=payload.state_limit,
            daily_download_limit=int(payload.credits_total),
            features={
                "credits_total": int(payload.credits_total),
                "catalog_visible": bool(payload.catalog_visible),
            },
            effective_from=payload.effective_from,
            effective_to=payload.effective_to,
            is_archived=False,
            archived_at=None,
            updated_by=int(admin_user.id),
        )
        db.add(package)
        try:
            db.commit()
            db.refresh(package)
        except SQLAlchemyError as exc:
            db.rollback()
            AdminService._schedule_stripe_cleanup_after_plan_write_failure(
                db,
                source="admin_plan_create",
                stripe_refs=stripe_refs,
                payload={
                    "plan_name": payload.name,
                    "request_id": payload.request_id,
                },
            )
            AdminService._raise_plan_lifecycle_write_error(
                operation="create",
                exc=exc,
                plan_id=None,
                request_id=payload.request_id,
                db_error_detail="Failed to persist plan creation",
                unknown_error_detail="Failed to create plan",
            )
        except Exception as exc:
            db.rollback()
            AdminService._schedule_stripe_cleanup_after_plan_write_failure(
                db,
                source="admin_plan_create",
                stripe_refs=stripe_refs,
                payload={
                    "plan_name": payload.name,
                    "request_id": payload.request_id,
                },
            )
            AdminService._raise_plan_lifecycle_write_error(
                operation="create",
                exc=exc,
                plan_id=None,
                request_id=payload.request_id,
                db_error_detail="Failed to persist plan creation",
                unknown_error_detail="Failed to create plan",
            )

        snapshot = AdminService._serialize_plan_snapshot(package, has_purchases=False)
        AuditService.log_event(
            actor_user_id=admin_user.id,
            action="admin_plan_created",
            entity_type="LeadPackage",
            entity_id=int(package.id),
            meta_data={
                "before": None,
                "after": snapshot,
            },
        )
        return AdminService._to_admin_plan_item(package, has_purchases=False)

    @staticmethod
    def update_plan(
        db: Session,
        *,
        admin_user: User,
        plan_id: int,
        payload: AdminPlanUpdateRequest,
    ) -> AdminPlanItem:
        package = AdminService._get_manageable_plan_or_404(db, plan_id=plan_id)
        fields_set = set(payload.model_fields_set)

        has_purchases = AdminService._plan_has_purchases(db, plan_id=int(package.id))
        before_snapshot = AdminService._serialize_plan_snapshot(package, has_purchases=has_purchases)

        current_credits_total = AdminService._resolve_plan_credits_total(package)
        next_price_cents = int(package.price_cents or 0)
        if "price_cents" in fields_set and payload.price_cents is not None:
            next_price_cents = int(payload.price_cents)

        next_credits_total = int(current_credits_total)
        if "credits_total" in fields_set and payload.credits_total is not None:
            next_credits_total = int(payload.credits_total)

        commercial_changed = (
            next_price_cents != int(package.price_cents or 0)
            or next_credits_total != current_credits_total
        )

        if commercial_changed and has_purchases:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Commercial fields are immutable after activation. "
                    "Create a new plan version instead."
                ),
            )

        next_effective_from = package.effective_from
        next_effective_to = package.effective_to
        if "effective_from" in fields_set:
            next_effective_from = payload.effective_from
        if "effective_to" in fields_set:
            next_effective_to = payload.effective_to
        AdminService._validate_effective_window(
            effective_from=next_effective_from,
            effective_to=next_effective_to,
        )

        next_name = str(package.name)
        if "name" in fields_set:
            if payload.name is None:
                raise HTTPException(status_code=400, detail="name must not be empty")
            next_name = payload.name

        duplicate_name = (
            db.query(LeadPackage.id)
            .filter(
                LeadPackage.id != package.id,
                LeadPackage.name == next_name,
            )
            .first()
        )
        if duplicate_name is not None:
            raise HTTPException(status_code=409, detail="Plan name already exists")

        if "name" in fields_set:
            package.name = next_name

        if "state_limit" in fields_set:
            package.state_limit = payload.state_limit

        if "effective_from" in fields_set:
            package.effective_from = payload.effective_from
        if "effective_to" in fields_set:
            package.effective_to = payload.effective_to

        features_payload: Dict[str, Any] = package.features if isinstance(package.features, dict) else {}
        if "catalog_visible" in fields_set:
            if payload.catalog_visible is None:
                raise HTTPException(status_code=400, detail="catalog_visible must be true or false")
            features_payload = {
                **features_payload,
                "catalog_visible": bool(payload.catalog_visible),
            }

        stripe_refs: Optional[Dict[str, Optional[str]]] = None
        if commercial_changed:
            if payload.request_id is None:
                raise HTTPException(
                    status_code=400,
                    detail="request_id is required when updating price_cents or credits_total",
                )
            stripe_refs = PaymentService.create_stripe_price_for_plan(
                request_id=payload.request_id,
                plan_name=next_name,
                price_cents=next_price_cents,
                metadata={
                    "source": "admin_plan_update",
                    "admin_user_id": str(admin_user.id),
                    "plan_id": str(package.id),
                    "request_id": payload.request_id,
                },
            )
            package.price_cents = next_price_cents
            package.daily_download_limit = next_credits_total
            package.stripe_price_id = str(stripe_refs["stripe_price_id"])
            package.stripe_product_id = stripe_refs.get("stripe_product_id")
            features_payload = {
                **features_payload,
                "credits_total": next_credits_total,
            }

        if features_payload != package.features:
            package.features = features_payload

        package.updated_by = int(admin_user.id)
        db.add(package)
        try:
            db.commit()
            db.refresh(package)
        except SQLAlchemyError as exc:
            db.rollback()
            AdminService._schedule_stripe_cleanup_after_plan_write_failure(
                db,
                source="admin_plan_update",
                stripe_refs=stripe_refs,
                payload={
                    "plan_id": int(package.id),
                    "request_id": payload.request_id,
                },
            )
            AdminService._raise_plan_lifecycle_write_error(
                operation="update",
                exc=exc,
                plan_id=int(package.id),
                request_id=payload.request_id,
                db_error_detail="Failed to persist plan update",
                unknown_error_detail="Failed to update plan",
            )
        except Exception as exc:
            db.rollback()
            AdminService._schedule_stripe_cleanup_after_plan_write_failure(
                db,
                source="admin_plan_update",
                stripe_refs=stripe_refs,
                payload={
                    "plan_id": int(package.id),
                    "request_id": payload.request_id,
                },
            )
            AdminService._raise_plan_lifecycle_write_error(
                operation="update",
                exc=exc,
                plan_id=int(package.id),
                request_id=payload.request_id,
                db_error_detail="Failed to persist plan update",
                unknown_error_detail="Failed to update plan",
            )

        has_purchases_after = AdminService._plan_has_purchases(db, plan_id=int(package.id))
        after_snapshot = AdminService._serialize_plan_snapshot(package, has_purchases=has_purchases_after)
        if before_snapshot != after_snapshot:
            AuditService.log_event(
                actor_user_id=admin_user.id,
                action="admin_plan_updated",
                entity_type="LeadPackage",
                entity_id=int(package.id),
                meta_data={
                    "before": before_snapshot,
                    "after": after_snapshot,
                },
            )

        return AdminService._to_admin_plan_item(package, has_purchases=has_purchases_after)

    @staticmethod
    def archive_plan(
        db: Session,
        *,
        admin_user: User,
        plan_id: int,
        payload: AdminPlanArchiveRequest,
    ) -> AdminPlanItem:
        package = AdminService._get_manageable_plan_or_404(db, plan_id=plan_id)
        has_purchases = AdminService._plan_has_purchases(db, plan_id=int(package.id))
        before_snapshot = AdminService._serialize_plan_snapshot(package, has_purchases=has_purchases)

        if not package.is_archived:
            package.is_archived = True
            package.archived_at = utcnow()
            package.updated_by = int(admin_user.id)
            db.add(package)
            try:
                db.commit()
                db.refresh(package)
            except SQLAlchemyError as exc:
                db.rollback()
                AdminService._raise_plan_lifecycle_write_error(
                    operation="archive",
                    exc=exc,
                    plan_id=int(package.id),
                    request_id=None,
                    db_error_detail="Failed to persist plan archive",
                    unknown_error_detail="Failed to archive plan",
                )
            except Exception as exc:
                db.rollback()
                AdminService._raise_plan_lifecycle_write_error(
                    operation="archive",
                    exc=exc,
                    plan_id=int(package.id),
                    request_id=None,
                    db_error_detail="Failed to persist plan archive",
                    unknown_error_detail="Failed to archive plan",
                )

            stripe_refs = {
                "stripe_price_id": package.stripe_price_id,
                "stripe_product_id": package.stripe_product_id,
            }
            try:
                PaymentService.deactivate_stripe_plan_artifacts(
                    stripe_price_id=stripe_refs.get("stripe_price_id"),
                    stripe_product_id=stripe_refs.get("stripe_product_id"),
                )
            except Exception as exc:
                logger.warning(
                    "Stripe archive deactivation failed for plan id=%s, scheduling retry: %s",
                    package.id,
                    exc,
                )
                AdminService._schedule_stripe_cleanup_after_plan_write_failure(
                    db,
                    source="admin_plan_archive",
                    stripe_refs=stripe_refs,
                    payload={
                        "plan_id": int(package.id),
                        "reason": payload.reason,
                    },
                )

        after_snapshot = AdminService._serialize_plan_snapshot(package, has_purchases=has_purchases)
        if before_snapshot != after_snapshot:
            AuditService.log_event(
                actor_user_id=admin_user.id,
                action="admin_plan_archived",
                entity_type="LeadPackage",
                entity_id=int(package.id),
                meta_data={
                    "reason": payload.reason,
                    "before": before_snapshot,
                    "after": after_snapshot,
                },
            )

        return AdminService._to_admin_plan_item(package, has_purchases=has_purchases)

    @staticmethod
    def unarchive_plan(
        db: Session,
        *,
        admin_user: User,
        plan_id: int,
        payload: AdminPlanArchiveRequest,
    ) -> AdminPlanItem:
        package = AdminService._get_manageable_plan_or_404(db, plan_id=plan_id)
        has_purchases = AdminService._plan_has_purchases(db, plan_id=int(package.id))
        before_snapshot = AdminService._serialize_plan_snapshot(package, has_purchases=has_purchases)

        if package.is_archived:
            stripe_price_id = package.stripe_price_id
            stripe_product_id = package.stripe_product_id
            try:
                PaymentService.activate_stripe_plan_artifacts(
                    stripe_price_id=stripe_price_id,
                    stripe_product_id=stripe_product_id,
                )
            except Exception as exc:
                logger.error(
                    "Failed to reactivate Stripe artifacts before plan unarchive id=%s: %s",
                    package.id,
                    exc,
                )
                raise HTTPException(status_code=502, detail="Failed to reactivate Stripe plan artifacts")

            package.is_archived = False
            package.archived_at = None
            package.updated_by = int(admin_user.id)
            db.add(package)
            try:
                db.commit()
                db.refresh(package)
            except SQLAlchemyError as exc:
                AdminService._rollback_unarchive_after_db_failure(
                    db,
                    plan_id=int(package.id),
                    stripe_price_id=stripe_price_id,
                    stripe_product_id=stripe_product_id,
                    reason=payload.reason,
                )
                AdminService._raise_plan_lifecycle_write_error(
                    operation="unarchive",
                    exc=exc,
                    plan_id=int(package.id),
                    request_id=None,
                    db_error_detail="Failed to persist plan unarchive",
                    unknown_error_detail="Failed to unarchive plan",
                )
            except Exception as exc:
                AdminService._rollback_unarchive_after_db_failure(
                    db,
                    plan_id=int(package.id),
                    stripe_price_id=stripe_price_id,
                    stripe_product_id=stripe_product_id,
                    reason=payload.reason,
                )
                AdminService._raise_plan_lifecycle_write_error(
                    operation="unarchive",
                    exc=exc,
                    plan_id=int(package.id),
                    request_id=None,
                    db_error_detail="Failed to persist plan unarchive",
                    unknown_error_detail="Failed to unarchive plan",
                )

        after_snapshot = AdminService._serialize_plan_snapshot(package, has_purchases=has_purchases)
        if before_snapshot != after_snapshot:
            AuditService.log_event(
                actor_user_id=admin_user.id,
                action="admin_plan_unarchived",
                entity_type="LeadPackage",
                entity_id=int(package.id),
                meta_data={
                    "reason": payload.reason,
                    "before": before_snapshot,
                    "after": after_snapshot,
                },
            )

        return AdminService._to_admin_plan_item(package, has_purchases=has_purchases)

    @staticmethod
    def _month_label(year_value: float, month_value: float) -> str:
        year = int(year_value)
        month = int(month_value)
        return f"{year:04d}-{month:02d}"

    @staticmethod
    def _resolve_purchase_reference(
        *,
        purchase_id: Optional[int],
        stripe_checkout_session_id: Optional[str],
        stripe_payment_intent_id: Optional[str],
    ) -> Optional[str]:
        if stripe_checkout_session_id:
            return stripe_checkout_session_id
        if stripe_payment_intent_id:
            return stripe_payment_intent_id
        if purchase_id is not None:
            return f"purchase-{purchase_id}"
        return None

    @staticmethod
    def get_dashboard_stats(db: Session) -> DashboardStats:
        total_users = db.query(func.count(User.id)).scalar() or 0
        pending_licenses = (
            db.query(func.count(License.id))
            .filter(License.verification_status == "pending")
            .scalar()
            or 0
        )
        total_leads = db.query(func.count(Lead.id)).scalar() or 0

        completed_purchases = (
            db.query(func.count(LeadPurchase.id))
            .filter(LeadPurchase.status == "completed")
            .scalar()
            or 0
        )

        advisors_with_credits = (
            db.query(func.count(func.distinct(LeadPurchase.user_id)))
            .filter(
                LeadPurchase.status == "completed",
                LeadPurchase.credits_remaining > 0,
            )
            .scalar()
            or 0
        )

        revenue_row = (
            db.query(
                func.coalesce(func.sum(LeadPurchase.amount_cents), 0),
                func.min(LeadPurchase.currency),
            )
            .filter(LeadPurchase.status == "completed")
            .first()
        )

        total_revenue_cents = int(revenue_row[0] if revenue_row else 0)
        currency = str(revenue_row[1] if revenue_row and revenue_row[1] else "USD")

        return DashboardStats(
            total_users=total_users,
            completed_purchases=completed_purchases,
            advisors_with_credits=advisors_with_credits,
            pending_licenses=pending_licenses,
            total_leads=total_leads,
            total_revenue_cents=total_revenue_cents,
            currency=currency,
        )

    @staticmethod
    def get_analytics_overview(db: Session) -> AdminAnalyticsOverview:
        monthly_revenue_rows = (
            db.query(
                func.extract("year", LeadPurchase.purchased_at).label("year"),
                func.extract("month", LeadPurchase.purchased_at).label("month"),
                func.coalesce(func.sum(LeadPurchase.amount_cents), 0).label("revenue_cents"),
            )
            .filter(LeadPurchase.status == "completed")
            .group_by("year", "month")
            .order_by("year", "month")
            .all()
        )

        monthly_revenue = [
            MonthlyRevenuePoint(
                month=AdminService._month_label(year_value, month_value),
                revenue_cents=int(revenue_cents or 0),
            )
            for year_value, month_value, revenue_cents in monthly_revenue_rows
        ]

        plan_breakdown_rows = (
            db.query(
                LeadPackage.name.label("package_name"),
                func.count(LeadPurchase.id).label("purchases"),
                func.coalesce(func.sum(LeadPurchase.credits_total), 0).label("credits_granted"),
                func.coalesce(func.sum(LeadPurchase.credits_remaining), 0).label("credits_remaining"),
                func.coalesce(func.sum(LeadPurchase.amount_cents), 0).label("revenue_cents"),
            )
            .join(LeadPurchase, LeadPurchase.package_id == LeadPackage.id)
            .filter(LeadPurchase.status == "completed")
            .group_by(LeadPackage.id, LeadPackage.name)
            .order_by(func.count(LeadPurchase.id).desc(), LeadPackage.name.asc())
            .all()
        )

        plan_breakdown = [
            PlanBreakdownItem(
                package_name=str(package_name),
                purchases=int(purchases or 0),
                credits_granted=int(credits_granted or 0),
                credits_remaining=int(credits_remaining or 0),
                revenue_cents=int(revenue_cents or 0),
            )
            for package_name, purchases, credits_granted, credits_remaining, revenue_cents in plan_breakdown_rows
        ]

        state_distribution_rows = (
            db.query(
                Lead.state_code.label("state_code"),
                func.count(Lead.id).label("lead_count"),
            )
            .group_by(Lead.state_code)
            .order_by(func.count(Lead.id).desc(), Lead.state_code.asc())
            .all()
        )

        state_distribution = [
            StateDistributionItem(
                state_code=state_code,
                lead_count=int(lead_count or 0),
            )
            for state_code, lead_count in state_distribution_rows
        ]

        user_growth_rows = (
            db.query(
                func.extract("year", User.created_at).label("year"),
                func.extract("month", User.created_at).label("month"),
                func.count(User.id).label("new_users"),
            )
            .filter(User.role == "advisor")
            .group_by("year", "month")
            .order_by("year", "month")
            .all()
        )

        user_growth = [
            UserGrowthPoint(
                month=AdminService._month_label(year_value, month_value),
                new_users=int(new_users or 0),
            )
            for year_value, month_value, new_users in user_growth_rows
        ]

        return AdminAnalyticsOverview(
            monthly_revenue=monthly_revenue,
            plan_breakdown=plan_breakdown,
            state_distribution=state_distribution,
            user_growth=user_growth,
        )

    @staticmethod
    def get_users(
        db: Session,
        page: int,
        size: int,
        filters: UserListFilters,
    ) -> PaginatedUsers:
        license_counts = (
            db.query(
                License.user_id.label("user_id"),
                func.count(License.id).label("license_count"),
            )
            .group_by(License.user_id)
            .subquery()
        )

        purchase_aggregates = (
            db.query(
                LeadPurchase.user_id.label("user_id"),
                func.coalesce(
                    func.sum(
                        case(
                            (LeadPurchase.status == "completed", LeadPurchase.credits_remaining),
                            else_=0,
                        )
                    ),
                    0,
                ).label("current_credits"),
                func.coalesce(func.count(LeadPurchase.id), 0).label("total_purchases"),
            )
            .group_by(LeadPurchase.user_id)
            .subquery()
        )

        query = (
            db.query(
                User,
                func.coalesce(license_counts.c.license_count, 0).label("license_count"),
                func.coalesce(purchase_aggregates.c.current_credits, 0).label("current_credits"),
                func.coalesce(purchase_aggregates.c.total_purchases, 0).label("total_purchases"),
            )
            .outerjoin(license_counts, license_counts.c.user_id == User.id)
            .outerjoin(purchase_aggregates, purchase_aggregates.c.user_id == User.id)
        )

        if filters.search:
            search_pattern = f"%{filters.search}%"
            query = query.filter(
                or_(
                    User.name.ilike(search_pattern),
                    User.email.ilike(search_pattern),
                )
            )

        if filters.role:
            query = query.filter(User.role == filters.role)

        if filters.status == "active":
            query = query.filter(User.is_active.is_(True))
        elif filters.status == "inactive":
            query = query.filter(User.is_active.is_(False))

        total = query.with_entities(func.count(User.id)).scalar() or 0

        offset = max(0, (page - 1) * size)
        rows = (
            query.order_by(User.created_at.desc(), User.id.desc())
            .offset(offset)
            .limit(size)
            .all()
        )

        items = [
            UserListItem(
                id=row_user.id,
                name=row_user.name,
                email=row_user.email,
                role=row_user.role,
                is_active=row_user.is_active,
                created_at=row_user.created_at,
                license_count=int(license_count or 0),
                current_credits=int(current_credits or 0),
                total_purchases=int(total_purchases or 0),
            )
            for row_user, license_count, current_credits, total_purchases in rows
        ]

        return PaginatedUsers(items=items, total=total, page=page, size=size)

    @staticmethod
    def get_orders(
        db: Session,
        page: int,
        size: int,
        status: Optional[str] = None,
    ) -> PaginatedOrders:
        query = AdminService._build_orders_query(db=db, status=status)

        total = query.with_entities(func.count(LeadPurchase.id)).scalar() or 0

        offset = max(0, (page - 1) * size)
        rows = (
            query.order_by(LeadPurchase.purchased_at.desc(), LeadPurchase.id.desc())
            .offset(offset)
            .limit(size)
            .all()
        )

        items = [
            AdminOrderItem(
                id=purchase.id,
                order_reference=(
                    purchase.stripe_checkout_session_id
                    or purchase.stripe_payment_intent_id
                    or f"purchase-{purchase.id}"
                ),
                advisor_name=user.name,
                advisor_email=user.email,
                package_name=plan.name if plan else None,
                quantity=purchase.credits_total,
                remaining_credits=purchase.credits_remaining,
                status=purchase.status,
                created_at=purchase.purchased_at,
                amount_cents=purchase.amount_cents,
                currency=(purchase.currency or "USD").upper(),
            )
            for purchase, user, plan in rows
        ]

        return PaginatedOrders(items=items, total=total, page=page, size=size)

    @staticmethod
    def _build_orders_query(
        *,
        db: Session,
        status: Optional[str] = None,
    ):
        query = (
            db.query(LeadPurchase, User, LeadPackage)
            .join(User, User.id == LeadPurchase.user_id)
            .outerjoin(LeadPackage, LeadPackage.id == LeadPurchase.package_id)
        )

        if status:
            query = query.filter(LeadPurchase.status == status)
        return query

    @staticmethod
    def stream_orders_csv(
        *,
        db: Session,
        status: Optional[str] = None,
    ) -> Generator[str, None, None]:
        headers = [
            "order_reference",
            "advisor_name",
            "advisor_email",
            "package_name",
            "quantity",
            "remaining_credits",
            "status",
            "created_at",
            "amount_dollars",
            "currency",
        ]
        csv_buffer = io.StringIO(newline="")
        writer = csv.DictWriter(csv_buffer, fieldnames=headers)
        writer.writeheader()
        yield csv_buffer.getvalue()
        csv_buffer.seek(0)
        csv_buffer.truncate(0)

        rows = (
            AdminService._build_orders_query(db=db, status=status)
            .order_by(LeadPurchase.purchased_at.desc(), LeadPurchase.id.desc())
            .yield_per(200)
        )
        for purchase, user, plan in rows:
            amount_cents = int(purchase.amount_cents or 0)
            amount_dollars = (Decimal(amount_cents) / Decimal("100")).quantize(Decimal("0.01"))
            writer.writerow(
                {
                    "order_reference": (
                        purchase.stripe_checkout_session_id
                        or purchase.stripe_payment_intent_id
                        or f"purchase-{purchase.id}"
                    ),
                    "advisor_name": user.name,
                    "advisor_email": user.email,
                    "package_name": plan.name if plan else "",
                    "quantity": int(purchase.credits_total or 0),
                    "remaining_credits": int(purchase.credits_remaining or 0),
                    "status": purchase.status,
                    "created_at": purchase.purchased_at.isoformat() if purchase.purchased_at else "",
                    "amount_dollars": f"{amount_dollars:.2f}",
                    "currency": str(purchase.currency or "USD").upper(),
                }
            )
            yield csv_buffer.getvalue()
            csv_buffer.seek(0)
            csv_buffer.truncate(0)

    @staticmethod
    def get_lead_inventory(
        db: Session,
        page: int,
        size: int,
        filters: LeadInventoryFilters,
    ) -> PaginatedLeadInventory:
        download_counts = (
            db.query(
                LeadDownload.lead_id.label("lead_id"),
                func.count(LeadDownload.id).label("download_count"),
            )
            .group_by(LeadDownload.lead_id)
            .subquery()
        )

        download_count_expr = func.coalesce(download_counts.c.download_count, 0)
        ownership_details = (
            db.query(
                LeadOwnership.lead_id.label("lead_id"),
                LeadOwnership.user_id.label("assigned_advisor_id"),
                User.name.label("assigned_advisor_name"),
                User.email.label("assigned_advisor_email"),
                LeadOwnership.purchase_id.label("purchase_id"),
                LeadPurchase.stripe_checkout_session_id.label("stripe_checkout_session_id"),
                LeadPurchase.stripe_payment_intent_id.label("stripe_payment_intent_id"),
            )
            .outerjoin(User, User.id == LeadOwnership.user_id)
            .outerjoin(LeadPurchase, LeadPurchase.id == LeadOwnership.purchase_id)
            .subquery()
        )
        sold_condition = or_(
            ownership_details.c.lead_id.isnot(None),
            download_count_expr > 0,
        )

        query = (
            db.query(
                Lead,
                download_count_expr.label("download_count"),
                ownership_details.c.assigned_advisor_id,
                ownership_details.c.assigned_advisor_name,
                ownership_details.c.assigned_advisor_email,
                ownership_details.c.purchase_id,
                ownership_details.c.stripe_checkout_session_id,
                ownership_details.c.stripe_payment_intent_id,
            )
            .outerjoin(download_counts, download_counts.c.lead_id == Lead.id)
            .outerjoin(ownership_details, ownership_details.c.lead_id == Lead.id)
        )

        if filters.search:
            search_pattern = f"%{filters.search}%"
            query = query.filter(
                or_(
                    Lead.first_name.ilike(search_pattern),
                    Lead.last_name.ilike(search_pattern),
                    Lead.mobile_phone.ilike(search_pattern),
                    Lead.state_code.ilike(search_pattern),
                    Lead.source.ilike(search_pattern),
                )
            )

        if filters.state_code:
            query = query.filter(Lead.state_code == filters.state_code)

        if filters.source:
            query = query.filter(Lead.source == filters.source)

        if filters.delivery_status == "unsold":
            query = query.filter(~sold_condition)
        elif filters.delivery_status == "sold":
            query = query.filter(sold_condition)

        if filters.created_from is not None:
            query = query.filter(Lead.created_at >= filters.created_from)

        if filters.created_to is not None:
            query = query.filter(Lead.created_at <= filters.created_to)

        if (
            filters.created_from is not None
            and filters.created_to is not None
            and filters.created_to < filters.created_from
        ):
            raise HTTPException(
                status_code=400,
                detail="created_to must be greater than or equal to created_from",
            )

        total = query.with_entities(func.count(Lead.id)).scalar() or 0

        offset = max(0, (page - 1) * size)
        rows = (
            query.order_by(Lead.created_at.desc(), Lead.id.desc())
            .offset(offset)
            .limit(size)
            .all()
        )

        items = [
            LeadInventoryItem(
                id=lead.id,
                state_code=lead.state_code,
                first_name=lead.first_name,
                last_name=lead.last_name,
                mobile_phone=lead.mobile_phone,
                source=lead.source,
                created_at=lead.created_at,
                download_count=int(download_count),
                assigned_advisor_id=int(assigned_advisor_id) if assigned_advisor_id is not None else None,
                assigned_advisor_name=assigned_advisor_name,
                assigned_advisor_email=assigned_advisor_email,
                purchase_id=int(purchase_id) if purchase_id is not None else None,
                purchase_reference=AdminService._resolve_purchase_reference(
                    purchase_id=int(purchase_id) if purchase_id is not None else None,
                    stripe_checkout_session_id=stripe_checkout_session_id,
                    stripe_payment_intent_id=stripe_payment_intent_id,
                ),
            )
            for (
                lead,
                download_count,
                assigned_advisor_id,
                assigned_advisor_name,
                assigned_advisor_email,
                purchase_id,
                stripe_checkout_session_id,
                stripe_payment_intent_id,
            ) in rows
        ]

        return PaginatedLeadInventory(items=items, total=total, page=page, size=size)

    @staticmethod
    def get_license_status_summary(db: Session) -> list[LicenseStatusSummaryItem]:
        rows = (
            db.query(
                License.verification_status,
                func.count(License.id),
            )
            .group_by(License.verification_status)
            .all()
        )

        status_counts = {"pending": 0, "verified": 0, "rejected": 0}
        for status, count in rows:
            if status in status_counts:
                status_counts[status] = int(count or 0)

        return [
            LicenseStatusSummaryItem(status="pending", count=status_counts["pending"]),
            LicenseStatusSummaryItem(status="verified", count=status_counts["verified"]),
            LicenseStatusSummaryItem(status="rejected", count=status_counts["rejected"]),
        ]

    @staticmethod
    def get_user_details(db: Session, user_id: int) -> UserDetails:
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        licenses = (
            db.query(License)
            .filter(License.user_id == user_id)
            .order_by(License.created_at.desc(), License.id.desc())
            .all()
        )

        license_items = [
            UserLicenseItem(
                id=license.id,
                state=license.state,
                license_number=license.license_number,
                license_type=license.license_type,
                verification_status=license.verification_status,
                created_at=license.created_at,
                verified_at=license.verified_at,
                rejection_reason=license.rejection_reason,
            )
            for license in licenses
        ]

        credit_totals_row = (
            db.query(
                func.coalesce(
                    func.sum(
                        case(
                            (LeadPurchase.status == "completed", LeadPurchase.credits_total),
                            else_=0,
                        )
                    ),
                    0,
                ).label("total_credits"),
                func.coalesce(
                    func.sum(
                        case(
                            (LeadPurchase.status == "completed", LeadPurchase.credits_remaining),
                            else_=0,
                        )
                    ),
                    0,
                ).label("remaining_credits"),
                func.coalesce(
                    func.sum(
                        case(
                            (LeadPurchase.status == "completed", 1),
                            else_=0,
                        )
                    ),
                    0,
                ).label("completed_purchases"),
            )
            .filter(LeadPurchase.user_id == user_id)
            .first()
        )
        credit_summary = UserCreditSummary(
            total_credits=int((credit_totals_row[0] if credit_totals_row else 0) or 0),
            remaining_credits=int((credit_totals_row[1] if credit_totals_row else 0) or 0),
            completed_purchases=int((credit_totals_row[2] if credit_totals_row else 0) or 0),
        )

        purchase_rows = (
            db.query(LeadPurchase, LeadPackage)
            .outerjoin(LeadPackage, LeadPurchase.package_id == LeadPackage.id)
            .filter(LeadPurchase.user_id == user_id)
            .order_by(LeadPurchase.purchased_at.desc(), LeadPurchase.id.desc())
            .limit(100)
            .all()
        )
        purchase_history = [
            UserPurchaseItem(
                id=purchase.id,
                order_reference=(
                    purchase.stripe_checkout_session_id
                    or purchase.stripe_payment_intent_id
                    or f"purchase-{purchase.id}"
                ),
                status=purchase.status,
                package_name=package.name if package else None,
                amount_cents=purchase.amount_cents,
                currency=(purchase.currency or "USD").upper(),
                credits_total=purchase.credits_total,
                credits_remaining=purchase.credits_remaining,
                purchased_at=purchase.purchased_at,
            )
            for purchase, package in purchase_rows
        ]

        download_rows = (
            db.query(LeadDownload, Lead.state_code)
            .join(Lead, Lead.id == LeadDownload.lead_id)
            .filter(LeadDownload.user_id == user_id)
            .order_by(LeadDownload.downloaded_at.desc(), LeadDownload.id.desc())
            .limit(100)
            .all()
        )

        download_history = [
            UserDownloadHistoryItem(
                lead_id=download.lead_id,
                state_code=state_code,
                downloaded_at=download.downloaded_at,
                csv_batch_id=download.csv_batch_id,
            )
            for download, state_code in download_rows
        ]

        activity_rows = (
            db.query(AuditLog)
            .filter(AuditLog.actor_user_id == user_id)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(100)
            .all()
        )

        recent_activity = [
            UserRecentActivityItem(
                id=activity.id,
                actor_user_id=activity.actor_user_id,
                action=activity.action,
                entity_type=activity.entity_type,
                entity_id=activity.entity_id,
                meta_data=activity.meta_data,
                ip_address=activity.ip_address,
                created_at=activity.created_at,
            )
            for activity in activity_rows
        ]

        return UserDetails(
            id=user.id,
            name=user.name,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            deactivated_at=user.deactivated_at,
            deactivated_by=user.deactivated_by,
            licenses=license_items,
            credit_summary=credit_summary,
            purchase_history=purchase_history,
            download_history=download_history,
            recent_activity=recent_activity,
        )

    @staticmethod
    def deactivate_user(
        db: Session,
        user_id: int,
        admin_id: int,
        reason: Optional[str],
    ) -> None:
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        if admin_id == user_id:
            raise HTTPException(
                status_code=400,
                detail="Admins cannot deactivate their own account",
            )

        if user.role == "admin":
            raise HTTPException(
                status_code=400,
                detail="Admin accounts cannot be deactivated from this endpoint",
            )

        if not user.is_active:
            raise HTTPException(status_code=400, detail="User already inactive")

        user.is_active = False
        user.deactivated_at = utcnow()
        user.deactivated_by = admin_id
        AuthService.revoke_all_user_refresh_sessions(
            db,
            user_id=user.id,
            reason="user_deactivated",
        )

        try:
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.error("Failed to deactivate user_id=%s: %s", user_id, exc)
            raise HTTPException(status_code=500, detail="Failed to deactivate user")

        AuditService.log_event(
            actor_user_id=admin_id,
            action="user_deactivated",
            entity_type="User",
            entity_id=user.id,
            meta_data={
                "target_user_id": user.id,
                "target_email": user.email,
                "reason": reason,
            },
        )

    @staticmethod
    def get_audit_logs(
        db: Session,
        page: int,
        size: int,
        filters: AuditLogFilters,
    ) -> PaginatedAuditLogs:
        return AdminAuditService.get_audit_logs(
            db=db,
            page=page,
            size=size,
            filters=filters,
        )

    @staticmethod
    def sync_wordpress(db: Session, admin_id: int) -> ImportStats:
        _ = db
        _ = admin_id
        raise HTTPException(status_code=501, detail="WordPress sync not implemented yet")
