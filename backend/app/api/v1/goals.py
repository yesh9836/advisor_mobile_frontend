from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_advisor
from app.models.user import User
from app.schemas.goal import AdvisorGoalResponse, AdvisorGoalUpsertRequest
from app.services.goal_service import GoalService

router = APIRouter(prefix="/goals", tags=["goals"])


@router.get(
    "/me",
    response_model=AdvisorGoalResponse,
    summary="Get current advisor goal",
)
def get_my_goal(
    target_year: Optional[int] = Query(default=None, ge=2000, le=2100),
    current_user: User = Depends(require_advisor),
    db: Session = Depends(get_db),
) -> AdvisorGoalResponse:
    goal = GoalService.get_or_create_goal(
        db=db,
        user=current_user,
        target_year=target_year,
    )
    return AdvisorGoalResponse.model_validate(
        GoalService.build_goal_response(db=db, user=current_user, goal=goal),
    )


@router.put(
    "/me",
    response_model=AdvisorGoalResponse,
    summary="Save current advisor goal",
)
def save_my_goal(
    payload: AdvisorGoalUpsertRequest,
    current_user: User = Depends(require_advisor),
    db: Session = Depends(get_db),
) -> AdvisorGoalResponse:
    goal = GoalService.update_goal(db=db, user=current_user, payload=payload)
    return AdvisorGoalResponse.model_validate(
        GoalService.build_goal_response(db=db, user=current_user, goal=goal),
    )
