import logging
from datetime import datetime, timezone
from typing import Annotated, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin
from app.models.user import User
from app.schemas.admin import (
    AdminAnalyticsOverview,
    AuditLogFilters,
    DeactivateUserRequest,
    DashboardStats,
    ImportStats,
    LeadInventoryFilters,
    LicenseStatusSummaryItem,
    PaginatedAuditLogs,
    PaginatedLeadInventory,
    PaginatedOrders,
    PaginatedUsers,
    UserDetails,
    UserListFilters,
)
from app.schemas.purchase import (
    FirstPurchaseAddonOfferConfigResponse,
    FirstPurchaseAddonOfferUpdateRequest,
)
from app.services.admin_service import AdminService
from app.services.first_purchase_offer_service import FirstPurchaseOfferService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get(
    "/dashboard",
    response_model=DashboardStats,
    summary="Get admin dashboard stats",
)
def get_dashboard_stats(
    current_admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> DashboardStats:
    _ = current_admin
    return AdminService.get_dashboard_stats(db)


@router.get(
    "/analytics",
    response_model=AdminAnalyticsOverview,
    summary="Get admin analytics overview",
)
def get_analytics_overview(
    current_admin: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> AdminAnalyticsOverview:
    _ = current_admin
    return AdminService.get_analytics_overview(db)


@router.get(
    "/users",
    response_model=PaginatedUsers,
    summary="List users for admin management",
)
def get_users(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    filters: UserListFilters = Depends(),
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PaginatedUsers:
    _ = current_admin
    return AdminService.get_users(db=db, page=page, size=size, filters=filters)


@router.get(
    "/orders",
    response_model=PaginatedOrders,
    summary="List recent admin order records",
)
def get_orders(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(default=None),
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PaginatedOrders:
    _ = current_admin
    normalized_status = status.strip() if status else None
    if normalized_status == "":
        normalized_status = None

    return AdminService.get_orders(
        db=db,
        page=page,
        size=size,
        status=normalized_status,
    )


@router.get(
    "/orders/export",
    summary="Export admin orders as CSV",
    response_class=StreamingResponse,
)
def export_orders_csv(
    status: Optional[str] = Query(default=None),
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    _ = current_admin
    normalized_status = status.strip() if status else None
    if normalized_status == "":
        normalized_status = None

    csv_iterator = AdminService.stream_orders_csv(
        db=db,
        status=normalized_status,
    )
    filename = f"admin_orders_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        csv_iterator,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Cache-Control": "no-cache",
        },
    )


@router.get(
    "/lead-inventory",
    response_model=PaginatedLeadInventory,
    summary="List lead inventory for admin management",
)
def get_lead_inventory(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    filters: LeadInventoryFilters = Depends(),
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PaginatedLeadInventory:
    _ = current_admin
    return AdminService.get_lead_inventory(db=db, page=page, size=size, filters=filters)


@router.get(
    "/license-status-summary",
    response_model=List[LicenseStatusSummaryItem],
    summary="Get license status counts",
)
def get_license_status_summary(
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> List[LicenseStatusSummaryItem]:
    _ = current_admin
    return AdminService.get_license_status_summary(db=db)


@router.get(
    "/users/{user_id}",
    response_model=UserDetails,
    summary="Get user details",
)
def get_user_details(
    user_id: int,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserDetails:
    _ = current_admin
    return AdminService.get_user_details(db=db, user_id=user_id)


@router.post(
    "/users/{user_id}/deactivate",
    summary="Deactivate a user",
)
def deactivate_user(
    user_id: int,
    payload: DeactivateUserRequest,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Dict[str, str]:
    AdminService.deactivate_user(
        db=db,
        user_id=user_id,
        admin_id=current_admin.id,
        reason=payload.reason,
    )
    return {"detail": "User deactivated"}


@router.get(
    "/audit-logs",
    response_model=PaginatedAuditLogs,
    summary="List audit logs",
)
def get_audit_logs(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    filters: AuditLogFilters = Depends(),
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PaginatedAuditLogs:
    _ = current_admin
    return AdminService.get_audit_logs(db=db, page=page, size=size, filters=filters)


@router.post(
    "/sync/wordpress",
    response_model=ImportStats,
    summary="Trigger WordPress sync (placeholder)",
)
def sync_wordpress(
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ImportStats:
    return AdminService.sync_wordpress(db=db, admin_id=current_admin.id)


@router.get(
    "/first-purchase-offer",
    response_model=FirstPurchaseAddonOfferConfigResponse,
    summary="Get first-purchase add-on offer config",
)
def get_first_purchase_offer_config(
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> FirstPurchaseAddonOfferConfigResponse:
    _ = current_admin
    return FirstPurchaseOfferService.get_offer_config(db=db)


@router.put(
    "/first-purchase-offer",
    response_model=FirstPurchaseAddonOfferConfigResponse,
    summary="Upsert first-purchase add-on offer config",
)
def upsert_first_purchase_offer_config(
    payload: FirstPurchaseAddonOfferUpdateRequest,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> FirstPurchaseAddonOfferConfigResponse:
    return FirstPurchaseOfferService.update_offer_config(
        db=db,
        admin_user=current_admin,
        payload=payload,
    )
