from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class DeliverySettingsUpdateRequest(BaseModel):
    email_alerts_enabled: Optional[bool] = None
    sms_alerts_enabled: Optional[bool] = None
    expected_version: Optional[int] = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_has_at_least_one_field(self) -> "DeliverySettingsUpdateRequest":
        if self.email_alerts_enabled is None and self.sms_alerts_enabled is None:
            raise ValueError("At least one setting must be provided")
        return self


class DeliverySettingsResponse(BaseModel):
    email_alerts_enabled: bool
    sms_alerts_enabled: bool
    version: int
    updated_at: datetime
    warnings: List[str] = Field(default_factory=list)
