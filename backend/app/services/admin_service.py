import logging
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import case, func, or_
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
    AuditLogItem,
    DashboardStats,
    ImportStats,
    LeadInventoryFilters,
    LeadInventoryItem,
    LicenseStatusSummaryItem,
    MonthlyRevenuePoint,
    PaginatedAuditLogs,
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
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)


class AdminService:
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
        query = (
            db.query(LeadPurchase, User, LeadPackage)
            .join(User, User.id == LeadPurchase.user_id)
            .outerjoin(LeadPackage, LeadPackage.id == LeadPurchase.package_id)
        )

        if status:
            query = query.filter(LeadPurchase.status == status)

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
