from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class DashboardStats(BaseModel):
    total_users: int
    active_subscriptions: int
    pending_licenses: int
    total_leads: int
    total_revenue_cents: int
    currency: str


class UserListItem(BaseModel):
    id: int
    name: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
    license_count: int
    subscription_status: Optional[str] = None


class PaginatedUsers(BaseModel):
    items: List[UserListItem]
    total: int
    page: int
    size: int


class UserLicenseItem(BaseModel):
    id: int
    state: str
    license_number: str
    license_type: Optional[str] = None
    verification_status: Literal["pending", "verified", "rejected"]
    created_at: datetime
    verified_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None


class UserSubscriptionItem(BaseModel):
    id: int
    status: str
    plan_name: Optional[str] = None
    price_cents: Optional[int] = None
    currency: Optional[str] = None
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    created_at: datetime


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
    subscription: Optional[UserSubscriptionItem] = None
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
