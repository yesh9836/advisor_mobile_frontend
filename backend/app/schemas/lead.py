from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


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
    created_at: datetime

    model_config = {
        "from_attributes": True,
    }


class LeadListResponse(BaseModel):
    items: List[LeadResponse]
    total: int
    page: int
    size: int
