import pytest
from fastapi import HTTPException

from app.models.delivery_settings import AdvisorDeliverySettings
from app.services.audit_service import AuditService
from app.services.delivery_settings_service import DeliverySettingsService


@pytest.mark.unit
def test_get_or_create_for_user_creates_single_default_row(db, user_factory):
    advisor = user_factory(
        role="advisor",
        password="DeliveryUnit123!",
        email="delivery.unit.defaults@example.com",
    )

    first = DeliverySettingsService.get_or_create_for_user(db=db, user_id=advisor.id)
    second = DeliverySettingsService.get_or_create_for_user(db=db, user_id=advisor.id)

    assert first.user_id == advisor.id
    assert first.email_alerts_enabled is False
    assert first.sms_alerts_enabled is False
    assert int(first.version) == 1
    assert second.user_id == advisor.id

    total_rows = (
        db.query(AdvisorDeliverySettings)
        .filter(AdvisorDeliverySettings.user_id == advisor.id)
        .count()
    )
    assert total_rows == 1


@pytest.mark.unit
def test_update_for_user_updates_selected_fields_and_increments_version(
    db,
    user_factory,
    monkeypatch: pytest.MonkeyPatch,
):
    advisor = user_factory(
        role="advisor",
        password="DeliveryUnitUpdate123!",
        email="delivery.unit.update@example.com",
    )
    created = DeliverySettingsService.get_or_create_for_user(db=db, user_id=advisor.id)
    captured_audits: list[dict[str, object]] = []
    monkeypatch.setattr(
        AuditService,
        "log_event",
        lambda **kwargs: captured_audits.append(kwargs),
    )

    updated = DeliverySettingsService.update_for_user(
        db=db,
        user_id=advisor.id,
        email_alerts_enabled=True,
        expected_version=int(created.version),
    )

    assert updated.email_alerts_enabled is True
    assert updated.sms_alerts_enabled is False
    assert int(updated.version) == 2
    assert len(captured_audits) == 1
    assert captured_audits[0]["action"] == "delivery_settings_updated"


@pytest.mark.unit
def test_update_for_user_rejects_stale_expected_version(
    db,
    user_factory,
    monkeypatch: pytest.MonkeyPatch,
):
    advisor = user_factory(
        role="advisor",
        password="DeliveryUnitVersion123!",
        email="delivery.unit.version@example.com",
    )
    initial = DeliverySettingsService.get_or_create_for_user(db=db, user_id=advisor.id)
    stale_version = int(initial.version)
    monkeypatch.setattr(AuditService, "log_event", lambda **kwargs: None)

    DeliverySettingsService.update_for_user(
        db=db,
        user_id=advisor.id,
        sms_alerts_enabled=True,
        expected_version=stale_version,
    )

    with pytest.raises(HTTPException) as exc_info:
        DeliverySettingsService.update_for_user(
            db=db,
            user_id=advisor.id,
            email_alerts_enabled=True,
            expected_version=stale_version,
        )
    assert exc_info.value.status_code == 409


@pytest.mark.unit
def test_get_or_create_for_user_requires_advisor_role(db, user_factory):
    admin = user_factory(
        role="admin",
        password="DeliveryUnitAdmin123!",
        email="delivery.unit.admin@example.com",
    )

    with pytest.raises(HTTPException) as exc_info:
        DeliverySettingsService.get_or_create_for_user(db=db, user_id=admin.id)
    assert exc_info.value.status_code == 403


@pytest.mark.unit
def test_get_warnings_for_user_flags_missing_phone_when_sms_enabled(
    db,
    user_factory,
    monkeypatch: pytest.MonkeyPatch,
):
    advisor = user_factory(
        role="advisor",
        password="DeliveryUnitWarn123!",
        email="delivery.unit.warn@example.com",
    )
    advisor.phone = None
    db.add(advisor)
    db.commit()
    monkeypatch.setattr(AuditService, "log_event", lambda **kwargs: None)

    settings = DeliverySettingsService.get_or_create_for_user(db=db, user_id=advisor.id)
    updated = DeliverySettingsService.update_for_user(
        db=db,
        user_id=advisor.id,
        sms_alerts_enabled=True,
        expected_version=int(settings.version),
    )
    warnings = DeliverySettingsService.get_warnings_for_user(advisor, updated)

    assert warnings == ["SMS alerts are enabled, but no phone number is on file."]
