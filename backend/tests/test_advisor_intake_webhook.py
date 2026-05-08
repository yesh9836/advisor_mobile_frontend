import hashlib
import hmac
import json
from datetime import datetime, timezone
from urllib.parse import urlencode

import pytest

from app.core.config import settings
from app.models.advisor_intake import AdvisorIntakeWebhookEvent
from app.models.notification import NotificationOutbox
from app.models.user import User


def _build_payload(entry_id: str = "advisor-entry-1001") -> dict:
    return {
        "entry_id": entry_id,
        "form_id": "advisor-intake",
        "fields": [
            {"name": "Advisor Name", "value": "Riley Harper"},
            {"name": "Advisor Email", "value": "RILEY.HARPER@example.com"},
            {"name": "Advisor Phone", "value": "3054959490"},
            {"name": "Company Name", "value": "Harper Wealth"},
            {"name": "Licensed State", "value": "FL"},
        ],
    }


def _signed_headers(
    raw_body: bytes,
    *,
    content_type: str = "application/json",
    timestamp: int | None = None,
) -> dict[str, str]:
    ts = int(timestamp or datetime.now(tz=timezone.utc).timestamp())
    signature = hmac.new(
        settings.ADVISOR_INTAKE_WEBHOOK_HMAC_SECRET.encode("utf-8"),
        f"{ts}.".encode("utf-8") + raw_body,
        hashlib.sha256,
    ).hexdigest()
    return {
        "Content-Type": content_type,
        settings.ADVISOR_INTAKE_WEBHOOK_TIMESTAMP_HEADER: str(ts),
        settings.ADVISOR_INTAKE_WEBHOOK_SIGNATURE_HEADER: signature,
    }


@pytest.mark.integration
def test_advisor_intake_webhook_accepts_signed_request_and_creates_advisor(client, db):
    raw_body = json.dumps(_build_payload()).encode("utf-8")
    headers = _signed_headers(raw_body)

    response = client.post("/api/v1/webhooks/advisor-intake", data=raw_body, headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ok"
    assert body["idempotent_replay"] is False
    assert body["account_created"] is True
    assert body["existing_user"] is False
    assert body["setup_email_queued"] is False

    user = db.query(User).filter(User.id == body["user_id"]).first()
    assert user is not None
    assert user.role == "advisor"
    assert user.email == "riley.harper@example.com"
    assert user.name == "Riley Harper"
    assert user.phone == "+13054959490"
    assert db.query(NotificationOutbox).count() == 0

    event = db.query(AdvisorIntakeWebhookEvent).first()
    assert event is not None
    assert event.provider == "elementor"
    assert event.external_entry_id == "advisor-entry-1001"
    assert event.user_id == user.id
    assert event.status == "account_created"


@pytest.mark.integration
def test_advisor_intake_webhook_accepts_flat_form_payload(client, db):
    payload = {
        "entry_id": "advisor-form-1001",
        "name": "Jordan Lee",
        "email": "jordan.lee@example.com",
        "phone": "305-555-1212",
    }
    raw_body = urlencode(payload).encode("utf-8")
    headers = _signed_headers(
        raw_body,
        content_type="application/x-www-form-urlencoded",
    )

    response = client.post("/api/v1/webhooks/advisor-intake", data=raw_body, headers=headers)

    assert response.status_code == 200, response.text
    user = db.query(User).filter(User.email == "jordan.lee@example.com").first()
    assert user is not None
    assert user.role == "advisor"
    assert user.phone == "+13055551212"


@pytest.mark.integration
def test_advisor_intake_webhook_replay_is_idempotent_by_entry_id(client, db):
    payload = _build_payload(entry_id="advisor-entry-2001")
    raw_body = json.dumps(payload).encode("utf-8")
    headers = _signed_headers(raw_body)

    first = client.post("/api/v1/webhooks/advisor-intake", data=raw_body, headers=headers)
    assert first.status_code == 200, first.text

    second = client.post("/api/v1/webhooks/advisor-intake", data=raw_body, headers=headers)
    assert second.status_code == 200, second.text
    assert second.json()["idempotent_replay"] is True
    assert second.json()["user_id"] == first.json()["user_id"]
    assert second.json()["account_created"] is False
    assert second.json()["existing_user"] is True

    assert db.query(User).filter(User.role == "advisor").count() == 1
    assert db.query(AdvisorIntakeWebhookEvent).count() == 1


@pytest.mark.integration
def test_advisor_intake_webhook_existing_advisor_email_returns_success(client, db, user_factory):
    existing = user_factory(
        role="advisor",
        email="existing.advisor@example.com",
        name="Existing Advisor",
    )
    payload = _build_payload(entry_id="advisor-entry-existing")
    payload["fields"][1]["value"] = "existing.advisor@example.com"
    raw_body = json.dumps(payload).encode("utf-8")
    headers = _signed_headers(raw_body)

    response = client.post("/api/v1/webhooks/advisor-intake", data=raw_body, headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["user_id"] == existing.id
    assert body["account_created"] is False
    assert body["existing_user"] is True
    assert db.query(User).filter(User.email == "existing.advisor@example.com").count() == 1
    event = db.query(AdvisorIntakeWebhookEvent).first()
    assert event is not None
    assert event.status == "existing_advisor"


@pytest.mark.integration
def test_advisor_intake_webhook_rejects_non_advisor_duplicate_email(client, db, user_factory):
    user_factory(
        role="admin",
        email="admin.owner@example.com",
        name="Admin Owner",
    )
    payload = _build_payload(entry_id="advisor-entry-admin-email")
    payload["fields"][1]["value"] = "admin.owner@example.com"
    raw_body = json.dumps(payload).encode("utf-8")
    headers = _signed_headers(raw_body)

    response = client.post("/api/v1/webhooks/advisor-intake", data=raw_body, headers=headers)

    assert response.status_code == 409
    assert response.json()["detail"] == "Advisor intake email already belongs to a non-advisor account"
    assert db.query(AdvisorIntakeWebhookEvent).count() == 0


@pytest.mark.integration
def test_advisor_intake_webhook_rejects_invalid_signature(client, db):
    raw_body = json.dumps(_build_payload()).encode("utf-8")
    headers = _signed_headers(raw_body)
    headers[settings.ADVISOR_INTAKE_WEBHOOK_SIGNATURE_HEADER] = "bad-signature"

    response = client.post("/api/v1/webhooks/advisor-intake", data=raw_body, headers=headers)

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid advisor intake webhook signature"
    assert db.query(User).count() == 0
    assert db.query(AdvisorIntakeWebhookEvent).count() == 0


@pytest.mark.integration
def test_advisor_intake_webhook_rejects_missing_phone(client, db):
    payload = _build_payload(entry_id="advisor-entry-missing-phone")
    payload["fields"] = [field for field in payload["fields"] if field["name"] != "Advisor Phone"]
    raw_body = json.dumps(payload).encode("utf-8")
    headers = _signed_headers(raw_body)

    response = client.post("/api/v1/webhooks/advisor-intake", data=raw_body, headers=headers)

    assert response.status_code == 400
    assert response.json()["detail"] == "Missing advisor phone"
    assert db.query(User).count() == 0
    assert db.query(AdvisorIntakeWebhookEvent).count() == 0


@pytest.mark.integration
def test_advisor_intake_webhook_rejects_invalid_phone(client, db):
    payload = _build_payload(entry_id="advisor-entry-invalid-phone")
    payload["fields"][2]["value"] = "not-a-phone"
    raw_body = json.dumps(payload).encode("utf-8")
    headers = _signed_headers(raw_body)

    response = client.post("/api/v1/webhooks/advisor-intake", data=raw_body, headers=headers)

    assert response.status_code == 400
    assert response.json()["detail"] == "Advisor phone must be a valid US number"
    assert db.query(User).count() == 0
    assert db.query(AdvisorIntakeWebhookEvent).count() == 0


@pytest.mark.integration
def test_advisor_intake_webhook_rejects_stale_timestamp(client, db):
    raw_body = json.dumps(_build_payload()).encode("utf-8")
    old_timestamp = int(datetime.now(tz=timezone.utc).timestamp()) - int(
        settings.ADVISOR_INTAKE_WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS
    ) - 5
    headers = _signed_headers(raw_body, timestamp=old_timestamp)

    response = client.post("/api/v1/webhooks/advisor-intake", data=raw_body, headers=headers)

    assert response.status_code == 400
    assert response.json()["detail"] == "Advisor intake webhook timestamp is outside tolerance window"
    assert db.query(User).count() == 0
