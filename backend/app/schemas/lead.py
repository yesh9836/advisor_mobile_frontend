from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

LeadOutcomeStatus = Literal["new", "contacted", "appointment_set"]


class LeadBase(BaseModel):
    state_code: Optional[str] = Field(None, min_length=2, max_length=2)
    zip_code: Optional[str] = Field(None, max_length=10)

    first_name: Optional[str] = Field(None, max_length=80)
    last_name: Optional[str] = Field(None, max_length=80)
    mobile_phone: Optional[str] = Field(None, max_length=20)
    preferred_follow_up_method: Optional[str] = Field(None, max_length=60)
    best_time_to_reach: Optional[str] = Field(None, max_length=20)

    retirement_timeline: Optional[str] = Field(None, max_length=40)
    confidence_in_long_term_plan: Optional[str] = Field(None, max_length=40)
    most_important_retirement_activity: Optional[str] = Field(None, max_length=80)
    planning_to_relocate_retirement: Optional[str] = Field(None, max_length=20)
    expected_retirement_income_source: Optional[str] = Field(None, max_length=120)

    overall_health: Optional[str] = Field(None, max_length=30)
    money_management_style: Optional[str] = Field(None, max_length=120)
    investor_profile_statement: Optional[str] = Field(None, max_length=200)
    investment_comfort_level: Optional[str] = Field(None, max_length=40)
    main_purpose_for_investing: Optional[List[str]] = None

    retirement_savings_range: Optional[str] = Field(None, max_length=40)
    annual_household_income_range: Optional[str] = Field(None, max_length=40)
    total_investable_assets_range: Optional[str] = Field(None, max_length=40)
    monthly_savings_range: Optional[str] = Field(None, max_length=40)
    wants_to_improve_strategy_timing: Optional[str] = Field(None, max_length=60)

    current_investment_strategies: Optional[List[str]] = None
    has_financial_advisor: Optional[str] = Field(None, max_length=80)
    advisor_local_preference: Optional[str] = Field(None, max_length=120)
    owns_annuity: Optional[str] = Field(None, max_length=10)

    additional_notes: Optional[str] = None

    @field_validator("state_code")
    @classmethod
    def normalize_state_code(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return v.strip().upper()


class LeadCreate(LeadBase):
    state_code: str = Field(..., min_length=2, max_length=2)
    source: str = Field("manual_entry", max_length=50)


class LeadUpdate(LeadBase):
    pass


class LeadResponse(LeadBase):
    id: int
    source: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    outcome_status: Optional[LeadOutcomeStatus] = None
    outcome_notes: Optional[str] = None
    outcome_updated_at: Optional[datetime] = None
    is_downloaded: bool = False
    downloaded_at: Optional[datetime] = None
    pii_unlocked: bool = False

    model_config = {
        "from_attributes": True,
    }


class LeadListResponse(BaseModel):
    items: List[LeadResponse]
    total: int
    page: int
    size: int

class LeadOutcomeUpdateRequest(BaseModel):
    status: LeadOutcomeStatus
    notes: Optional[str] = Field(None, max_length=2000)

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        clean = value.strip()
        return clean if clean else None


class LeadOutcomeResponse(BaseModel):
    id: int
    user_id: int
    lead_id: int
    status: LeadOutcomeStatus
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DashboardSettingsSnapshot(BaseModel):
    email_alerts_enabled: bool
    sms_alerts_enabled: bool
    target_states: List[str]
    min_assets: Optional[str] = None
    daily_download_limit: Optional[int] = None


class LeadDashboardSummaryResponse(BaseModel):
    leads_delivered_7_days: int
    appointments_set_7_days: int
    cost_per_appointment: float
    currency: str
    settings: DashboardSettingsSnapshot
