import hashlib
import hmac
import json
from datetime import datetime, timezone

import pytest

from app.core.config import settings
from app.models.lead import Lead, LeadIntakeWebhookEvent


def _build_payload(entry_id: str = "entry-1001") -> dict:
    return {
        "entry_id": entry_id,
        "form_id": "42",
        "fields": [
            {"name": "What is your First & Last Name?:", "value": "Bernard\nFrazier"},
            {"name": "When would you like to retire?:", "value": "5-9 Years"},
            {
                "name": "What investment strategies are you currently using? (Check all that apply):",
                "value": "Active Trading, Real Estate",
            },
            {"name": "What state are you located in?:", "value": "Florida"},
            {"name": "Please Enter Your Zip Code:", "value": "33415"},
            {"name": "Please provide your Mobile Phone Number::", "value": "3054959490"},
            {"name": "What is the best time of day to reach you?:", "value": "AM\non"},
        ],
    }


def _signed_headers(raw_body: bytes, timestamp: int | None = None) -> dict[str, str]:
    ts = int(timestamp or datetime.now(tz=timezone.utc).timestamp())
    signature = hmac.new(
        settings.WPFORMS_WEBHOOK_HMAC_SECRET.encode("utf-8"),
        f"{ts}.".encode("utf-8") + raw_body,
        hashlib.sha256,
    ).hexdigest()
    return {
        "Content-Type": "application/json",
        settings.WPFORMS_WEBHOOK_TIMESTAMP_HEADER: str(ts),
        settings.WPFORMS_WEBHOOK_SIGNATURE_HEADER: signature,
    }


@pytest.mark.integration
def test_wpforms_webhook_accepts_signed_request_and_creates_lead(client, db):
    payload = _build_payload()
    raw_body = json.dumps(payload).encode("utf-8")
    headers = _signed_headers(raw_body)

    response = client.post("/api/v1/webhooks/wpforms/survey", data=raw_body, headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ok"
    assert body["idempotent_replay"] is False
    assert body["lead_id"] is not None

    lead = db.query(Lead).filter(Lead.id == body["lead_id"]).first()
    assert lead is not None
    assert lead.source == "api_submission"
    assert lead.first_name == "Bernard"
    assert lead.last_name == "Frazier"
    assert lead.state_code == "FL"
    assert lead.zip_code == "33415"
    assert lead.mobile_phone == "+13054959490"
    assert lead.current_investment_strategies == ["Active Trading", "Real Estate"]
    assert lead.best_time_to_reach == "AM"


@pytest.mark.integration
def test_wpforms_webhook_replay_is_idempotent_by_entry_id(client, db):
    payload = _build_payload(entry_id="entry-2001")
    raw_body = json.dumps(payload).encode("utf-8")
    headers = _signed_headers(raw_body)

    first = client.post("/api/v1/webhooks/wpforms/survey", data=raw_body, headers=headers)
    assert first.status_code == 200, first.text

    second = client.post("/api/v1/webhooks/wpforms/survey", data=raw_body, headers=headers)
    assert second.status_code == 200, second.text
    assert second.json()["idempotent_replay"] is True

    lead_rows = db.query(Lead).all()
    intake_rows = db.query(LeadIntakeWebhookEvent).all()
    assert len(lead_rows) == 1
    assert len(intake_rows) == 1


@pytest.mark.integration
def test_wpforms_webhook_rejects_invalid_signature(client, db):
    payload = _build_payload(entry_id="entry-3001")
    raw_body = json.dumps(payload).encode("utf-8")
    headers = _signed_headers(raw_body)
    headers[settings.WPFORMS_WEBHOOK_SIGNATURE_HEADER] = "bad-signature"

    response = client.post("/api/v1/webhooks/wpforms/survey", data=raw_body, headers=headers)
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid webhook signature"
    assert db.query(Lead).count() == 0
    assert db.query(LeadIntakeWebhookEvent).count() == 0


@pytest.mark.integration
def test_wpforms_webhook_rejects_stale_timestamp(client, db):
    payload = _build_payload(entry_id="entry-4001")
    raw_body = json.dumps(payload).encode("utf-8")
    old_timestamp = int(datetime.now(tz=timezone.utc).timestamp()) - int(
        settings.WPFORMS_WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS
    ) - 5
    headers = _signed_headers(raw_body, timestamp=old_timestamp)

    response = client.post("/api/v1/webhooks/wpforms/survey", data=raw_body, headers=headers)
    assert response.status_code == 400
    assert response.json()["detail"] == "Webhook timestamp is outside tolerance window"
    assert db.query(Lead).count() == 0
