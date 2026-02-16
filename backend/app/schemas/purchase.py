from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


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


class PurchaseOrderItem(BaseModel):
    id: int
    order_reference: str
    package_name: Optional[str] = None
    amount_cents: int
    currency: str
    credits_total: int
    credits_remaining: int
    status: str
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
