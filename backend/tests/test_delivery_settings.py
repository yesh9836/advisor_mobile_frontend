import pytest

from app.models.audit_log import AuditLog


@pytest.mark.integration
def test_advisor_can_read_and_update_own_delivery_settings_and_summary_reflects_changes(
    client,
    db,
    user_factory,
    auth_headers,
):
    advisor = user_factory(
        role="advisor",
        password="DeliveryInt123!",
        email="delivery.int.advisor@example.com",
    )
    headers = auth_headers(advisor.email, "DeliveryInt123!")

    get_response = client.get("/api/v1/delivery-settings/me", headers=headers)
    assert get_response.status_code == 200, get_response.text
    body = get_response.json()
    assert body["email_alerts_enabled"] is False
    assert body["sms_alerts_enabled"] is False
    assert body["warnings"] == []
    initial_version = int(body["version"])

    patch_response = client.patch(
        "/api/v1/delivery-settings/me",
        headers=headers,
        json={"email_alerts_enabled": True, "expected_version": initial_version},
    )
    assert patch_response.status_code == 200, patch_response.text
    patched = patch_response.json()
    assert patched["email_alerts_enabled"] is True
    assert patched["sms_alerts_enabled"] is False
    assert int(patched["version"]) == initial_version + 1

    summary_response = client.get("/api/v1/leads/dashboard/summary", headers=headers)
    assert summary_response.status_code == 200, summary_response.text
    summary = summary_response.json()
    assert summary["settings"]["email_alerts_enabled"] is True
    assert summary["settings"]["sms_alerts_enabled"] is False

    audit_row = (
        db.query(AuditLog)
        .filter(
            AuditLog.actor_user_id == advisor.id,
            AuditLog.action == "delivery_settings_updated",
            AuditLog.entity_type == "AdvisorDeliverySettings",
            AuditLog.entity_id == advisor.id,
        )
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert audit_row is not None
    assert audit_row.meta_data["changed_fields"]["email_alerts_enabled"] == {
        "from": False,
        "to": True,
    }


@pytest.mark.integration
def test_delivery_settings_endpoint_is_advisor_only(client, user_factory, auth_headers):
    admin = user_factory(
        role="admin",
        password="DeliveryIntAdmin123!",
        email="delivery.int.admin@example.com",
    )
    headers = auth_headers(admin.email, "DeliveryIntAdmin123!")

    read_response = client.get("/api/v1/delivery-settings/me", headers=headers)
    assert read_response.status_code == 403
    assert read_response.json()["detail"] == "Advisor access required"

    patch_response = client.patch(
        "/api/v1/delivery-settings/me",
        headers=headers,
        json={"email_alerts_enabled": True, "expected_version": 1},
    )
    assert patch_response.status_code == 403
    assert patch_response.json()["detail"] == "Advisor access required"


@pytest.mark.integration
def test_advisor_updates_are_scoped_to_current_user(client, user_factory, auth_headers):
    first_advisor = user_factory(
        role="advisor",
        password="DeliveryIntFirst123!",
        email="delivery.int.first@example.com",
    )
    second_advisor = user_factory(
        role="advisor",
        password="DeliveryIntSecond123!",
        email="delivery.int.second@example.com",
    )
    first_headers = auth_headers(first_advisor.email, "DeliveryIntFirst123!")
    second_headers = auth_headers(second_advisor.email, "DeliveryIntSecond123!")

    first_read = client.get("/api/v1/delivery-settings/me", headers=first_headers)
    assert first_read.status_code == 200, first_read.text
    first_version = int(first_read.json()["version"])

    first_patch = client.patch(
        "/api/v1/delivery-settings/me",
        headers=first_headers,
        json={"sms_alerts_enabled": True, "expected_version": first_version},
    )
    assert first_patch.status_code == 200, first_patch.text
    assert first_patch.json()["sms_alerts_enabled"] is True

    second_read = client.get("/api/v1/delivery-settings/me", headers=second_headers)
    assert second_read.status_code == 200, second_read.text
    assert second_read.json()["email_alerts_enabled"] is False
    assert second_read.json()["sms_alerts_enabled"] is False


@pytest.mark.integration
def test_delivery_settings_patch_rejects_stale_expected_version(client, user_factory, auth_headers):
    advisor = user_factory(
        role="advisor",
        password="DeliveryIntVersion123!",
        email="delivery.int.version@example.com",
    )
    headers = auth_headers(advisor.email, "DeliveryIntVersion123!")

    first_read = client.get("/api/v1/delivery-settings/me", headers=headers)
    assert first_read.status_code == 200, first_read.text
    stale_version = int(first_read.json()["version"])

    first_patch = client.patch(
        "/api/v1/delivery-settings/me",
        headers=headers,
        json={"email_alerts_enabled": True, "expected_version": stale_version},
    )
    assert first_patch.status_code == 200, first_patch.text

    second_patch = client.patch(
        "/api/v1/delivery-settings/me",
        headers=headers,
        json={"sms_alerts_enabled": True, "expected_version": stale_version},
    )
    assert second_patch.status_code == 409


@pytest.mark.integration
def test_delivery_settings_patch_requires_at_least_one_toggle(client, user_factory, auth_headers):
    advisor = user_factory(
        role="advisor",
        password="DeliveryIntPayload123!",
        email="delivery.int.payload@example.com",
    )
    headers = auth_headers(advisor.email, "DeliveryIntPayload123!")

    response = client.patch(
        "/api/v1/delivery-settings/me",
        headers=headers,
        json={"expected_version": 1},
    )
    assert response.status_code == 422
