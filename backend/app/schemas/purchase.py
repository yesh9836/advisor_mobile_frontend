from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from app.core.currency import require_usd_currency


class PurchasePackageResponse(BaseModel):
    id: int
    name: str
    price_cents: int
    currency: str
    state_limit: Optional[int]
    daily_download_limit: int
    features: Optional[List[str] | Dict[str, Any]]
    stripe_price_id: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PurchaseCheckoutResponse(BaseModel):
    session_id: str
    url: str


class PurchaseCheckoutRequest(BaseModel):
    package_id: int = Field(..., ge=1)
    retry_token: Optional[str] = Field(default=None, min_length=8, max_length=128)

    @field_validator("retry_token")
    @classmethod
    def normalize_retry_token(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        return cleaned


class PurchaseOrderItem(BaseModel):
    id: int
    order_reference: str
    package_name: Optional[str] = None
    amount_cents: int
    currency: str
    credits_total: int
    entitled_credits_total: int
    credits_remaining: int
    status: str
    assigned_count: int
    unfulfilled_count: int
    fulfillment_status: str
    purchased_at: datetime
    stripe_checkout_session_id: str
    stripe_payment_intent_id: Optional[str] = None


class PaginatedPurchaseOrders(BaseModel):
    items: List[PurchaseOrderItem]
    total: int
    page: int
    size: int


class PurchaseBalanceResponse(BaseModel):
    total_credits: int
    remaining_credits: int
    completed_purchases: int


class PurchaseHistoryResponse(BaseModel):
    items: List[PurchaseOrderItem]


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
    package_name: Optional[str] = None
    hosted_invoice_url: Optional[str] = None
    invoice_pdf: Optional[str] = None
    description: Optional[str] = None


class BillingSummaryResponse(BaseModel):
    payment_method: Optional[BillingPaymentMethodResponse] = None
    invoices: List[BillingInvoiceResponse]


class FirstPurchaseAddonOfferUpdateRequest(BaseModel):
    is_enabled: bool
    trigger_package_id: Optional[int] = Field(default=None, ge=1)
    offer_credits_total: Optional[int] = Field(default=None, ge=1, le=1000000)
    offer_price_cents: Optional[int] = Field(default=None, ge=1)
    offer_currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    headline: Optional[str] = Field(default=None, max_length=120)
    message: Optional[str] = Field(default=None, max_length=400)
    cta_label: Optional[str] = Field(default=None, max_length=80)
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None

    @field_validator("headline", "message", "cta_label")
    @classmethod
    def normalize_text_fields(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        clean = value.strip()
        if not clean:
            return None
        return clean

    @field_validator("offer_currency")
    @classmethod
    def normalize_offer_currency(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        clean = value.strip()
        if not clean:
            return None
        return require_usd_currency(clean, field_name="offer_currency")


class FirstPurchaseAddonOfferConfigResponse(BaseModel):
    id: Optional[int] = None
    is_enabled: bool
    trigger_package_id: Optional[int] = None
    trigger_package_name: Optional[str] = None
    offer_package_id: Optional[int] = None
    offer_package_name: Optional[str] = None
    offer_price_cents: Optional[int] = None
    offer_currency: Optional[str] = None
    offer_credits_total: Optional[int] = None
    headline: Optional[str] = None
    message: Optional[str] = None
    cta_label: Optional[str] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    updated_by: Optional[int] = None
    inventory_ready: Optional[bool] = None
    inventory_available_count: Optional[int] = None
    inventory_required_count: Optional[int] = None
    inventory_gate_code: Optional[str] = None
    inventory_gate_message: Optional[str] = None


class FirstPurchaseAddonOfferAdvisorResponse(BaseModel):
    trigger_package_id: int
    offer_package_id: int
    offer_package_name: str
    offer_price_cents: int
    offer_currency: str
    offer_credits_total: int
    headline: str
    message: str
    cta_label: str


class FirstPurchaseAddonOfferEligibilityResponse(BaseModel):
    eligible: bool
    offer: Optional[FirstPurchaseAddonOfferAdvisorResponse] = None
    rejection_code: Optional[str] = None
    rejection_message: Optional[str] = None
    inventory_available_count: Optional[int] = None
    inventory_required_count: Optional[int] = None
