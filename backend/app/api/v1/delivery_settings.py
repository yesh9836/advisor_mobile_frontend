from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db
from app.models.user import User
from app.schemas.delivery_settings import DeliverySettingsResponse, DeliverySettingsUpdateRequest
from app.services.delivery_settings_service import DeliverySettingsService

router = APIRouter(prefix="/delivery-settings", tags=["delivery-settings"])


def _require_advisor(current_user: User) -> None:
    if current_user.role != "advisor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Advisor access required",
        )


@router.get(
    "/me",
    response_model=DeliverySettingsResponse,
    summary="Get delivery settings for current advisor",
)
def get_my_delivery_settings(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> DeliverySettingsResponse:
    _require_advisor(current_user)
    settings = DeliverySettingsService.get_or_create_for_user(db=db, user_id=current_user.id)
    warnings = DeliverySettingsService.get_warnings_for_user(current_user, settings)
    return DeliverySettingsResponse(
        email_alerts_enabled=settings.email_alerts_enabled,
        sms_alerts_enabled=settings.sms_alerts_enabled,
        version=int(settings.version),
        updated_at=settings.updated_at,
        warnings=warnings,
    )


@router.patch(
    "/me",
    response_model=DeliverySettingsResponse,
    summary="Update delivery settings for current advisor",
)
def update_my_delivery_settings(
    payload: DeliverySettingsUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> DeliverySettingsResponse:
    _require_advisor(current_user)
    settings = DeliverySettingsService.update_for_user(
        db=db,
        user_id=current_user.id,
        email_alerts_enabled=payload.email_alerts_enabled,
        sms_alerts_enabled=payload.sms_alerts_enabled,
        expected_version=payload.expected_version,
    )
    warnings = DeliverySettingsService.get_warnings_for_user(current_user, settings)
    return DeliverySettingsResponse(
        email_alerts_enabled=settings.email_alerts_enabled,
        sms_alerts_enabled=settings.sms_alerts_enabled,
        version=int(settings.version),
        updated_at=settings.updated_at,
        warnings=warnings,
    )
