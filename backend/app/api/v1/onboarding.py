import math

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_advisor
from app.db.timezone import utcnow
from app.models.license import License
from app.models.user import User
from app.schemas.onboarding import (
    AdvisorOnboardingInputs,
    AdvisorOnboardingLicense,
    AdvisorOnboardingResponse,
    AdvisorOnboardingSaveRequest,
)
from app.services.goal_service import GoalService


router = APIRouter(prefix="/onboarding", tags=["onboarding"])

DEFAULT_ANNUAL_INCOME_CENTS = 25_000_000
DEFAULT_AVERAGE_SALE_CENTS = 2_500_000
DEFAULT_COMMISSION_RATE_BPS = 2_000
DEFAULT_CLOSING_RATE_BPS = 3_300
LEAD_TO_APPOINTMENT_RATE_BPS = 3_333


@router.get("/me", response_model=AdvisorOnboardingResponse)
def get_my_onboarding(
    current_user: User = Depends(require_advisor),
    db: Session = Depends(get_db),
) -> AdvisorOnboardingResponse:
    goal = GoalService.get_or_create_goal(db=db, user=current_user)
    return _build_response(db=db, user=current_user, goal=goal)


@router.put("/me", response_model=AdvisorOnboardingResponse)
def save_my_onboarding(
    payload: AdvisorOnboardingSaveRequest,
    current_user: User = Depends(require_advisor),
    db: Session = Depends(get_db),
) -> AdvisorOnboardingResponse:
    licenses = _licenses_for(db=db, user=current_user)
    if not any(
        item.verification_status in {"pending", "verified"}
        for item in licenses
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Submit or resubmit a license before completing onboarding."
            ),
        )

    goal = GoalService.get_or_create_goal(db=db, user=current_user)
    goal.annual_income_goal_cents = payload.annual_income_goal_cents
    goal.average_sale_cents = payload.average_sale_cents
    goal.commission_rate_bps = payload.commission_rate_bps
    goal.average_commission_cents = max(
        1,
        round(
            payload.average_sale_cents
            * payload.commission_rate_bps
            / 10_000
        ),
    )
    goal.appointment_to_deal_rate_bps = payload.closing_rate_bps
    goal.lead_to_appointment_rate_bps = LEAD_TO_APPOINTMENT_RATE_BPS
    goal.onboarding_completed_at = goal.onboarding_completed_at or utcnow()
    goal.onboarding_consent_at = goal.onboarding_consent_at or utcnow()
    db.commit()
    db.refresh(goal)
    return _build_response(db=db, user=current_user, goal=goal)


def _licenses_for(*, db: Session, user: User) -> list[License]:
    return (
        db.query(License)
        .filter(License.user_id == user.id)
        .order_by(License.created_at.desc(), License.id.desc())
        .all()
    )


def _build_response(
    *, db: Session, user: User, goal
) -> AdvisorOnboardingResponse:
    licenses = _licenses_for(db=db, user=user)
    # A rejected state always needs attention, even when another state is
    # already verified. Pending review is the next most actionable status.
    status_order = {"rejected": 3, "pending": 2, "verified": 1}
    license_status = (
        max(
            (item.verification_status for item in licenses),
            key=lambda value: status_order.get(value, 0),
        )
        if licenses
        else "not_submitted"
    )
    has_inputs = (
        goal.average_sale_cents is not None
        and goal.commission_rate_bps is not None
    )
    annual_income = int(
        goal.annual_income_goal_cents
        if has_inputs
        else DEFAULT_ANNUAL_INCOME_CENTS
    )
    average_sale = int(goal.average_sale_cents or DEFAULT_AVERAGE_SALE_CENTS)
    commission_rate = int(
        goal.commission_rate_bps or DEFAULT_COMMISSION_RATE_BPS
    )
    closing_rate = int(
        goal.appointment_to_deal_rate_bps
        if has_inputs
        else DEFAULT_CLOSING_RATE_BPS
    )
    average_commission = max(1, round(average_sale * commission_rate / 10_000))
    deals = math.ceil(annual_income / average_commission)
    appointments = math.ceil(deals / (closing_rate / 10_000))
    leads = math.ceil(appointments / (LEAD_TO_APPOINTMENT_RATE_BPS / 10_000))
    return AdvisorOnboardingResponse(
        complete=goal.onboarding_completed_at is not None,
        completed_at=goal.onboarding_completed_at,
        consent_accepted=goal.onboarding_consent_at is not None,
        inputs=AdvisorOnboardingInputs(
            annual_income_goal_cents=annual_income,
            average_sale_cents=average_sale,
            commission_rate_bps=commission_rate,
            closing_rate_bps=closing_rate,
            lead_to_appointment_rate_bps=LEAD_TO_APPOINTMENT_RATE_BPS,
        ),
        average_commission_cents=average_commission,
        deals_needed=deals,
        appointments_needed=appointments,
        leads_needed=leads,
        license_status=license_status,
        licenses=[
            AdvisorOnboardingLicense.model_validate(
                item,
                from_attributes=True,
            )
            for item in licenses
        ],
    )
