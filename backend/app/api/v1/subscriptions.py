import logging
from typing import List

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.subscription import (
    CheckoutSessionResponse,
    SubscriptionPlanResponse,
    SubscriptionResponse,
    BillingSummaryResponse
)
from app.services.subscription_service import SubscriptionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.get(
    "/plans",
    response_model=List[SubscriptionPlanResponse],
    summary="Get available subscription plans",
)
def get_plans(db: Session = Depends(get_db)) -> List[SubscriptionPlanResponse]:
    plans = SubscriptionService.get_available_plans(db=db)
    return [SubscriptionPlanResponse.model_validate(plan) for plan in plans]


@router.post(
    "/checkout",
    response_model=CheckoutSessionResponse,
    summary="Create Stripe checkout session",
)
def create_checkout_session(
    plan_id: int = Body(..., embed=True),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> CheckoutSessionResponse:
    session_data = SubscriptionService.create_checkout_session(
        db=db,
        user=current_user,
        plan_id=plan_id,
    )
    return CheckoutSessionResponse(**session_data)


@router.get(
    "/current",
    response_model=SubscriptionResponse,
    summary="Get current user's subscription",
)
def get_current_subscription(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> SubscriptionResponse:
    subscription = (
        db.query(Subscription)
        .filter(Subscription.user_id == current_user.id)
        .order_by(Subscription.created_at.desc())
        .first()
    )

    if not subscription:
        raise HTTPException(status_code=404, detail="No subscription found")

    return SubscriptionResponse.model_validate(subscription)


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


@router.post(
    "/cancel",
    response_model=SubscriptionResponse,
    summary="Cancel current user's subscription",
)
def cancel_subscription(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> SubscriptionResponse:
    subscription = SubscriptionService.cancel_subscription(db=db, user=current_user)
    return SubscriptionResponse.model_validate(subscription)
