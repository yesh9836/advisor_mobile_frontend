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

class BillingPaymentMethodResponse(BaseModel):
    brand: str
    last4: str
    exp_month: int
    exp_year: int
    funding: Optional[str] = None
    country: Optional[str] = None
    is_placeholder: bool = False


class BillingInvoiceResponse(BaseModel):
    stripe_invoice_id: str
    amount_paid_cents: int
    currency: str
    status: str
    created_at: datetime
    hosted_invoice_url: Optional[str] = None
    invoice_pdf: Optional[str] = None
    description: Optional[str] = None


class BillingSummaryResponse(BaseModel):
    payment_method: Optional[BillingPaymentMethodResponse] = None
    invoices: List[BillingInvoiceResponse]


class CreditSummaryResponse(BaseModel):
    total_credits: int
    remaining_credits: int
    completed_purchases: int
