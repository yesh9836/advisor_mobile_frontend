from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class DashboardStats(BaseModel):
    total_users: int
    completed_purchases: int
    advisors_with_credits: int
    pending_licenses: int
    total_leads: int
    total_revenue_cents: int
    currency: str


class MonthlyRevenuePoint(BaseModel):
    month: str
    revenue_cents: int


class PlanBreakdownItem(BaseModel):
    package_name: str
    purchases: int
    credits_granted: int
    credits_remaining: int
    revenue_cents: int


class StateDistributionItem(BaseModel):
    state_code: str
    lead_count: int


class UserGrowthPoint(BaseModel):
    month: str
    new_users: int


class AdminAnalyticsOverview(BaseModel):
    monthly_revenue: List[MonthlyRevenuePoint]
    plan_breakdown: List[PlanBreakdownItem]
    state_distribution: List[StateDistributionItem]
    user_growth: List[UserGrowthPoint]


class UserListItem(BaseModel):
    id: int
    name: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
    license_count: int
    current_credits: int
    total_purchases: int


class PaginatedUsers(BaseModel):
    items: List[UserListItem]
    total: int
    page: int
    size: int


class AdminOrderItem(BaseModel):
    id: int
    order_reference: str
    advisor_name: str
    advisor_email: str
    package_name: Optional[str] = None
    quantity: Optional[int] = None
    remaining_credits: Optional[int] = None
    status: str
    created_at: datetime
    amount_cents: int
    currency: str


class PaginatedOrders(BaseModel):
    items: List[AdminOrderItem]
    total: int
    page: int
    size: int


class LeadInventoryItem(BaseModel):
    id: int
    state_code: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    mobile_phone: Optional[str] = None
    source: Optional[str] = None
    created_at: datetime
    download_count: int


class PaginatedLeadInventory(BaseModel):
    items: List[LeadInventoryItem]
    total: int
    page: int
    size: int


class LicenseStatusSummaryItem(BaseModel):
    status: Literal["pending", "verified", "rejected"]
    count: int


class UserLicenseItem(BaseModel):
    id: int
    state: str
    license_number: str
    license_type: Optional[str] = None
    verification_status: Literal["pending", "verified", "rejected"]
    created_at: datetime
    verified_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None


class UserCreditSummary(BaseModel):
    total_credits: int
    remaining_credits: int
    completed_purchases: int


class UserPurchaseItem(BaseModel):
    id: int
    order_reference: str
    status: str
    package_name: Optional[str] = None
    amount_cents: int
    currency: str
    credits_total: int
    credits_remaining: int
    purchased_at: datetime


class UserDownloadHistoryItem(BaseModel):
    lead_id: int
    state_code: str
    downloaded_at: datetime
    csv_batch_id: Optional[str] = None


class UserRecentActivityItem(BaseModel):
    id: int
    action: str
    entity_type: str
    entity_id: Optional[int] = None
    meta_data: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    created_at: datetime


class UserDetails(BaseModel):
    id: int
    name: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
    deactivated_at: Optional[datetime] = None
    deactivated_by: Optional[int] = None
    licenses: List[UserLicenseItem]
    credit_summary: UserCreditSummary
    purchase_history: List[UserPurchaseItem]
    download_history: List[UserDownloadHistoryItem]
    recent_activity: List[UserRecentActivityItem]


class AuditLogItem(BaseModel):
    id: int
    actor_user_id: int
    action: str
    entity_type: str
    entity_id: Optional[int] = None
    meta_data: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    created_at: datetime


class PaginatedAuditLogs(BaseModel):
    items: List[AuditLogItem]
    total: int
    page: int
    size: int


class ImportStats(BaseModel):
    scanned: int
    inserted: int
    skipped_duplicates: int
    failed: int
    errors: List[Dict[str, Any]]


class UserListFilters(BaseModel):
    search: Optional[str] = None
    role: Optional[Literal["admin", "advisor"]] = None
    status: Optional[Literal["active", "inactive"]] = None

    @field_validator("search")
    @classmethod
    def normalize_search(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        clean = value.strip()
        return clean if clean else None


class AuditLogFilters(BaseModel):
    action: Optional[str] = None
    actor_user_id: Optional[int] = Field(default=None, ge=1)
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    created_from: Optional[datetime] = None
    created_to: Optional[datetime] = None

    @field_validator("action", "entity_type")
    @classmethod
    def normalize_string_filters(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        clean = value.strip()
        return clean if clean else None


class DeactivateUserRequest(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=500)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        clean = value.strip()
        return clean if clean else None


class LeadInventoryFilters(BaseModel):
    search: Optional[str] = None
    state_code: Optional[str] = Field(default=None, min_length=2, max_length=2)
    source: Optional[str] = None
    delivery_status: Optional[Literal["all", "unsold", "sold"]] = "all"
    created_from: Optional[datetime] = None
    created_to: Optional[datetime] = None

    @field_validator("search", "source")
    @classmethod
    def normalize_string_filters(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        clean = value.strip()
        return clean if clean else None

    @field_validator("state_code")
    @classmethod
    def normalize_state_code(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        clean = value.strip().upper()
        return clean if clean else None
