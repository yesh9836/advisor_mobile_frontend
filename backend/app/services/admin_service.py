import logging
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, aliased

from app.db.timezone import utcnow
from app.models.audit_log import AuditLog
from app.models.lead import Lead, LeadDownload
from app.models.license import License
from app.models.subscription import Subscription, SubscriptionPlan
from app.models.user import User
from app.schemas.admin import (
    AuditLogFilters,
    AuditLogItem,
    DashboardStats,
    ImportStats,
    PaginatedAuditLogs,
    PaginatedUsers,
    UserDetails,
    UserDownloadHistoryItem,
    UserLicenseItem,
    UserListFilters,
    UserListItem,
    UserRecentActivityItem,
    UserSubscriptionItem,
)
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


class AdminService:
    @staticmethod
    def _latest_subscription_ids_subquery(db: Session):
        return (
            db.query(
                Subscription.user_id.label("user_id"),
                func.max(Subscription.id).label("subscription_id"),
            )
            .group_by(Subscription.user_id)
            .subquery()
        )

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

        latest_subscription_ids = AdminService._latest_subscription_ids_subquery(db)

        active_subscriptions = (
            db.query(func.count(Subscription.id))
            .join(
                latest_subscription_ids,
                Subscription.id == latest_subscription_ids.c.subscription_id,
            )
            .filter(Subscription.status == "active")
            .scalar()
            or 0
        )

        revenue_row = (
            db.query(
                func.coalesce(func.sum(SubscriptionPlan.price_cents), 0),
                func.min(SubscriptionPlan.currency),
            )
            .join(Subscription, SubscriptionPlan.id == Subscription.plan_id)
            .join(
                latest_subscription_ids,
                Subscription.id == latest_subscription_ids.c.subscription_id,
            )
            .filter(Subscription.status == "active")
            .first()
        )

        total_revenue_cents = int(revenue_row[0] if revenue_row else 0)
        currency = str(revenue_row[1] if revenue_row and revenue_row[1] else "USD")

        return DashboardStats(
            total_users=total_users,
            active_subscriptions=active_subscriptions,
            pending_licenses=pending_licenses,
            total_leads=total_leads,
            total_revenue_cents=total_revenue_cents,
            currency=currency,
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

        latest_subscription_ids = AdminService._latest_subscription_ids_subquery(db)
        latest_subscription = aliased(Subscription)

        query = (
            db.query(
                User,
                func.coalesce(license_counts.c.license_count, 0).label("license_count"),
                latest_subscription.status.label("subscription_status"),
            )
            .outerjoin(license_counts, license_counts.c.user_id == User.id)
            .outerjoin(
                latest_subscription_ids,
                latest_subscription_ids.c.user_id == User.id,
            )
            .outerjoin(
                latest_subscription,
                latest_subscription.id == latest_subscription_ids.c.subscription_id,
            )
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
                subscription_status=subscription_status,
            )
            for row_user, license_count, subscription_status in rows
        ]

        return PaginatedUsers(items=items, total=total, page=page, size=size)

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

        latest_subscription_row = (
            db.query(Subscription, SubscriptionPlan)
            .outerjoin(SubscriptionPlan, Subscription.plan_id == SubscriptionPlan.id)
            .filter(Subscription.user_id == user_id)
            .order_by(Subscription.created_at.desc(), Subscription.id.desc())
            .first()
        )

        subscription_item: Optional[UserSubscriptionItem] = None
        if latest_subscription_row is not None:
            subscription, plan = latest_subscription_row
            subscription_item = UserSubscriptionItem(
                id=subscription.id,
                status=subscription.status,
                plan_name=plan.name if plan else None,
                price_cents=plan.price_cents if plan else None,
                currency=plan.currency if plan else None,
                current_period_start=subscription.current_period_start,
                current_period_end=subscription.current_period_end,
                created_at=subscription.created_at,
            )

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
            subscription=subscription_item,
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

        if not user.is_active:
            raise HTTPException(status_code=400, detail="User already inactive")

        user.is_active = False
        user.deactivated_at = utcnow()
        user.deactivated_by = admin_id

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
        query = db.query(AuditLog)

        if filters.action:
            query = query.filter(AuditLog.action == filters.action)

        if filters.actor_user_id:
            query = query.filter(AuditLog.actor_user_id == filters.actor_user_id)

        if filters.entity_type:
            query = query.filter(AuditLog.entity_type == filters.entity_type)

        if filters.entity_id is not None:
            query = query.filter(AuditLog.entity_id == filters.entity_id)

        if filters.created_from is not None:
            query = query.filter(AuditLog.created_at >= filters.created_from)

        if filters.created_to is not None:
            query = query.filter(AuditLog.created_at <= filters.created_to)

        if (
            filters.created_from is not None
            and filters.created_to is not None
            and filters.created_to < filters.created_from
        ):
            raise HTTPException(
                status_code=400,
                detail="created_to must be greater than or equal to created_from",
            )

        total = query.with_entities(func.count(AuditLog.id)).scalar() or 0

        offset = max(0, (page - 1) * size)
        rows = (
            query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .offset(offset)
            .limit(size)
            .all()
        )

        items = [
            AuditLogItem(
                id=row.id,
                actor_user_id=row.actor_user_id,
                action=row.action,
                entity_type=row.entity_type,
                entity_id=row.entity_id,
                meta_data=row.meta_data,
                ip_address=row.ip_address,
                created_at=row.created_at,
            )
            for row in rows
        ]

        return PaginatedAuditLogs(items=items, total=total, page=page, size=size)

    @staticmethod
    def sync_wordpress(db: Session, admin_id: int) -> ImportStats:
        _ = db
        _ = admin_id
        raise HTTPException(status_code=501, detail="WordPress sync not implemented yet")
