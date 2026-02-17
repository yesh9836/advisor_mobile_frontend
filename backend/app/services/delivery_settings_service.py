import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.delivery_settings import AdvisorDeliverySettings
from app.models.user import User
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


class DeliverySettingsService:
    @staticmethod
    def _get_advisor_user_or_raise(db: Session, user_id: int) -> User:
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        if user.role != "advisor":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Advisor access required")
        return user

    @staticmethod
    def get_warnings_for_user(user: User, settings: AdvisorDeliverySettings) -> List[str]:
        warnings: List[str] = []
        if settings.sms_alerts_enabled and not (user.phone and user.phone.strip()):
            warnings.append("SMS alerts are enabled, but no phone number is on file.")
        return warnings

    @staticmethod
    def get_or_create_for_user(db: Session, user_id: int) -> AdvisorDeliverySettings:
        DeliverySettingsService._get_advisor_user_or_raise(db, user_id)
        settings = (
            db.query(AdvisorDeliverySettings)
            .filter(AdvisorDeliverySettings.user_id == user_id)
            .first()
        )
        if settings is not None:
            return settings

        settings = AdvisorDeliverySettings(
            user_id=user_id,
            email_alerts_enabled=False,
            sms_alerts_enabled=False,
            version=1,
        )
        db.add(settings)
        try:
            db.commit()
        except IntegrityError:
            # Handle concurrent create in a race-safe way.
            db.rollback()
            settings = (
                db.query(AdvisorDeliverySettings)
                .filter(AdvisorDeliverySettings.user_id == user_id)
                .first()
            )
            if settings is None:
                raise
            return settings

        db.refresh(settings)
        return settings

    @staticmethod
    def update_for_user(
        db: Session,
        user_id: int,
        *,
        email_alerts_enabled: Optional[bool] = None,
        sms_alerts_enabled: Optional[bool] = None,
        expected_version: Optional[int] = None,
    ) -> AdvisorDeliverySettings:
        if email_alerts_enabled is None and sms_alerts_enabled is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="At least one setting must be provided",
            )

        DeliverySettingsService._get_advisor_user_or_raise(db, user_id)
        settings = (
            db.query(AdvisorDeliverySettings)
            .filter(AdvisorDeliverySettings.user_id == user_id)
            .with_for_update()
            .first()
        )
        if settings is None:
            settings = DeliverySettingsService.get_or_create_for_user(db=db, user_id=user_id)

        current_version = int(settings.version or 1)
        if expected_version is not None and int(expected_version) != current_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Delivery settings were updated by another request. Please refresh and retry.",
            )

        new_email = (
            settings.email_alerts_enabled
            if email_alerts_enabled is None
            else bool(email_alerts_enabled)
        )
        new_sms = (
            settings.sms_alerts_enabled
            if sms_alerts_enabled is None
            else bool(sms_alerts_enabled)
        )

        changed_fields: dict[str, dict[str, bool]] = {}
        if settings.email_alerts_enabled != new_email:
            changed_fields["email_alerts_enabled"] = {
                "from": bool(settings.email_alerts_enabled),
                "to": bool(new_email),
            }
        if settings.sms_alerts_enabled != new_sms:
            changed_fields["sms_alerts_enabled"] = {
                "from": bool(settings.sms_alerts_enabled),
                "to": bool(new_sms),
            }

        if not changed_fields:
            return settings

        settings.email_alerts_enabled = new_email
        settings.sms_alerts_enabled = new_sms
        settings.version = current_version + 1
        settings.updated_at = datetime.now(timezone.utc)
        db.add(settings)
        db.commit()
        db.refresh(settings)

        AuditService.log_event(
            actor_user_id=user_id,
            action="delivery_settings_updated",
            entity_type="AdvisorDeliverySettings",
            entity_id=user_id,
            meta_data={
                "changed_fields": changed_fields,
                "previous_version": current_version,
                "new_version": int(settings.version),
            },
        )
        logger.info(
            "Updated delivery settings for advisor user_id=%s changed=%s version=%s",
            user_id,
            ",".join(changed_fields.keys()),
            settings.version,
        )

        return settings
