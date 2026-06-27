from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AdvisorGoalUpsertRequest(BaseModel):
    target_year: int = Field(..., ge=2000, le=2100)
    annual_income_goal_cents: int = Field(..., gt=0)
    average_commission_cents: int = Field(..., gt=0)
    earned_ytd_cents: int = Field(..., ge=0)
    appointment_to_deal_rate_bps: int = Field(..., ge=1, le=10000)
    lead_to_appointment_rate_bps: int = Field(..., ge=1, le=10000)


class AdvisorGoalSnapshot(BaseModel):
    id: int
    user_id: int
    target_year: int
    annual_income_goal_cents: int
    average_commission_cents: int
    earned_ytd_cents: int
    appointment_to_deal_rate_bps: int
    lead_to_appointment_rate_bps: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class GoalPacingSnapshot(BaseModel):
    remaining_months: int
    recommended_monthly_leads: int
    status: str
    message: str


class GoalDerivedSnapshot(BaseModel):
    deals_needed: int
    appointments_needed: int
    leads_needed: int
    closed_deals_ytd: int
    income_progress_percent: int
    deals_remaining: int
    appointments_remaining: int
    leads_remaining: int
    recommended_monthly_leads: int
    pacing: GoalPacingSnapshot


class GoalPackageRecommendation(BaseModel):
    package_id: int
    name: str
    price_cents: int
    currency: str
    credits_per_package: int
    packages_needed: int
    total_cost_cents: int
    overage_leads: int
    estimated_cost_per_lead_cents: int
    state_limit: Optional[int] = None
    features: Optional[List[str] | Dict[str, Any]] = None
    recommended: bool


class AdvisorGoalResponse(BaseModel):
    goal: AdvisorGoalSnapshot
    derived: GoalDerivedSnapshot
    packages: List[GoalPackageRecommendation]
