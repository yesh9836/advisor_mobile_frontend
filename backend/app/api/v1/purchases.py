from typing import List, Optional

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db
from app.models.user import User
from app.schemas.purchase import (
    BillingSummaryResponse,
    FirstPurchaseAddonOfferEligibilityResponse,
    PaginatedPurchaseOrders,
    PurchaseBalanceResponse,
    PurchaseCheckoutResponse,
    PurchaseHistoryResponse,
    PurchasePackageResponse,
)
from app.services.first_purchase_offer_service import FirstPurchaseOfferService
from app.services.subscription_service import SubscriptionService

router = APIRouter(prefix="/purchases", tags=["purchases"])


@router.get(
    "/packages",
    response_model=List[PurchasePackageResponse],
    summary="Get available one-time lead packages",
)
def get_packages(db: Session = Depends(get_db)) -> List[PurchasePackageResponse]:
    packages = SubscriptionService.get_available_packages(db=db)
    return [PurchasePackageResponse.model_validate(package) for package in packages]


@router.post(
    "/checkout",
    response_model=PurchaseCheckoutResponse,
    summary="Create Stripe checkout session for one-time package purchase",
)
def create_checkout(
    package_id: int = Body(..., embed=True),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> PurchaseCheckoutResponse:
    session_data = SubscriptionService.create_purchase_checkout_session(
        db=db,
        user=current_user,
        package_id=package_id,
    )
    return PurchaseCheckoutResponse(**session_data)


@router.get(
    "/orders",
    response_model=PaginatedPurchaseOrders,
    summary="Get advisor purchase orders",
)
def get_orders(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> PaginatedPurchaseOrders:
    normalized_status = status.strip() if status else None
    if normalized_status == "":
        normalized_status = None
    data = SubscriptionService.get_purchase_orders(
        db=db,
        user=current_user,
        page=page,
        size=size,
        status_filter=normalized_status,
    )
    return PaginatedPurchaseOrders(**data)


@router.get(
    "/balance",
    response_model=PurchaseBalanceResponse,
    summary="Get advisor credit balance",
)
def get_balance(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> PurchaseBalanceResponse:
    data = SubscriptionService.get_purchase_balance(db=db, user=current_user)
    return PurchaseBalanceResponse(**data)


@router.get(
    "/history",
    response_model=PurchaseHistoryResponse,
    summary="Get advisor purchase history",
)
def get_history(
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> PurchaseHistoryResponse:
    data = SubscriptionService.get_purchase_history(db=db, user=current_user, limit=limit)
    return PurchaseHistoryResponse(**data)


@router.get(
    "/billing/summary",
    response_model=BillingSummaryResponse,
    summary="Get advisor billing history and payment method",
)
def get_billing_summary(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> BillingSummaryResponse:
    data = SubscriptionService.get_billing_summary(db=db, user=current_user)
    return BillingSummaryResponse(**data)


@router.get(
    "/first-purchase-offer",
    response_model=FirstPurchaseAddonOfferEligibilityResponse,
    summary="Check first-purchase add-on offer eligibility for a completed checkout",
)
def get_first_purchase_offer(
    checkout_session_id: str = Query(..., min_length=1),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> FirstPurchaseAddonOfferEligibilityResponse:
    return FirstPurchaseOfferService.get_advisor_offer_eligibility(
        db=db,
        user=current_user,
        checkout_session_id=checkout_session_id.strip(),
    )
