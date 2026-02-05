from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class SubscriptionPlanResponse(BaseModel):
    """Schema for subscription plan response (all plan fields)."""
    id: int
    name: str
    price_cents: int
    currency: str
    state_limit: Optional[int]
    daily_download_limit: int
    features: Optional[List[str] | Dict[str, Any]]
    stripe_price_id: str
    created_at: datetime

    model_config = {
        "from_attributes": True,
    }


class SubscriptionResponse(BaseModel):
    """Schema for subscription response (all subscription fields + plan details)."""
    id: int
    user_id: int
    plan_id: int
    stripe_subscription_id: str
    status: str
    current_period_start: Optional[datetime]
    current_period_end: Optional[datetime]
    created_at: datetime
    plan: SubscriptionPlanResponse

    model_config = {
        "from_attributes": True,
    }


class CheckoutSessionResponse(BaseModel):
    """Schema for Stripe checkout session response."""
    session_id: str
    url: str
