from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel, Field, field_validator


class LicenseCreate(BaseModel):
    """Schema for creating a new license submission."""
    
    state: str = Field(
        ...,
        min_length=2,
        max_length=2,
        description="Two-letter state code (e.g., CA, NY, TX)",
    )
    license_number: str = Field(
        ...,
        min_length=1,
        max_length=80,
        description="License number from state",
    )
    license_type: Optional[str] = Field(
        None,
        max_length=80,
        description="Type of license (optional)",
    )

    @field_validator("state")
    @classmethod
    def validate_state_uppercase(cls, v: str) -> str:
        """Ensure state code is uppercase."""
        return v.upper()

    @field_validator("license_number")
    @classmethod
    def validate_license_number(cls, v: str) -> str:
        """Trim whitespace from license number."""
        return v.strip()


class LicenseApprove(BaseModel):
    """Schema for approving a license (no body needed)."""
    pass


class LicenseReject(BaseModel):
    """Schema for rejecting a license."""
    
    rejection_reason: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Reason for rejecting the license",
    )


class LicenseResponse(BaseModel):
    """Schema for license response."""
    
    id: int
    user_id: int
    state: str
    license_number: str
    license_type: Optional[str]
    document_path: Optional[str]
    verification_status: Literal["pending", "verified", "rejected"]
    verified_at: Optional[datetime]
    verified_by: Optional[int]
    rejection_reason: Optional[str]
    created_at: datetime

    model_config = {
        "from_attributes": True,
    }


class LicenseWithUser(LicenseResponse):
    """Schema for license with user details (for admin views)."""
    
    user_name: str
    user_email: str

    model_config = {
        "from_attributes": True,
    }