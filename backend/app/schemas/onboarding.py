from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


class AdvisorOnboardingSaveRequest(BaseModel):
    annual_income_goal_cents: int = Field(..., ge=5_000_000, le=1_000_000_000)
    average_sale_cents: int = Field(..., ge=100_000, le=2_000_000_000)
    commission_rate_bps: int = Field(..., ge=100, le=5_000)
    closing_rate_bps: int = Field(..., ge=100, le=10_000)
    consent_accepted: bool

    @model_validator(mode="after")
    def require_consent(self):
        if not self.consent_accepted:
            raise ValueError("Advisor verification consent is required")
        return self


class AdvisorOnboardingInputs(BaseModel):
    annual_income_goal_cents: int
    average_sale_cents: int
    commission_rate_bps: int
    closing_rate_bps: int
    lead_to_appointment_rate_bps: int


class AdvisorOnboardingLicense(BaseModel):
    id: int
    state: str
    license_number: str
    license_type: Optional[str]
    verification_status: Literal["pending", "verified", "rejected"]
    rejection_reason: Optional[str]


class AdvisorOnboardingResponse(BaseModel):
    complete: bool
    completed_at: Optional[datetime]
    consent_accepted: bool
    inputs: AdvisorOnboardingInputs
    average_commission_cents: int
    deals_needed: int
    appointments_needed: int
    leads_needed: int
    license_status: Literal["not_submitted", "pending", "verified", "rejected"]
    licenses: list[AdvisorOnboardingLicense]
