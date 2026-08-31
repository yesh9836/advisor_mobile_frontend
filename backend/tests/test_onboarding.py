from fastapi.testclient import TestClient


def _payload(**overrides) -> dict:
    payload = {
        "annual_income_goal_cents": 25_000_000,
        "average_sale_cents": 2_500_000,
        "commission_rate_bps": 2_000,
        "closing_rate_bps": 3_300,
        "consent_accepted": True,
    }
    payload.update(overrides)
    return payload


def test_new_advisor_gets_reference_defaults_and_mandatory_status(
    client: TestClient,
    user_factory,
    auth_headers,
) -> None:
    advisor = user_factory(role="advisor")
    headers = auth_headers(advisor.email, "StrongPass123!")

    response = client.get("/api/v1/onboarding/me", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["complete"] is False
    assert body["license_status"] == "not_submitted"
    assert body["inputs"] == {
        "annual_income_goal_cents": 25_000_000,
        "average_sale_cents": 2_500_000,
        "commission_rate_bps": 2_000,
        "closing_rate_bps": 3_300,
        "lead_to_appointment_rate_bps": 3_333,
    }


def test_onboarding_requires_license_and_consent(
    client: TestClient,
    user_factory,
    auth_headers,
) -> None:
    advisor = user_factory(role="advisor")
    headers = auth_headers(advisor.email, "StrongPass123!")

    no_license = client.put(
        "/api/v1/onboarding/me",
        headers=headers,
        json=_payload(),
    )
    no_consent = client.put(
        "/api/v1/onboarding/me",
        headers=headers,
        json=_payload(consent_accepted=False),
    )

    assert no_license.status_code == 409
    assert no_consent.status_code == 422


def test_pending_license_completes_plan_and_preserves_editable_inputs(
    client: TestClient,
    user_factory,
    auth_headers,
    license_factory,
) -> None:
    advisor = user_factory(role="advisor")
    license_factory(user_id=advisor.id, state="TX", status="pending")
    headers = auth_headers(advisor.email, "StrongPass123!")

    response = client.put(
        "/api/v1/onboarding/me",
        headers=headers,
        json=_payload(),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["complete"] is True
    assert body["consent_accepted"] is True
    assert body["license_status"] == "pending"
    assert body["average_commission_cents"] == 500_000
    assert body["deals_needed"] == 50
    assert body["appointments_needed"] == 152
    assert body["leads_needed"] == 457

    edited = client.put(
        "/api/v1/onboarding/me",
        headers=headers,
        json=_payload(closing_rate_bps=5_000),
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["inputs"]["closing_rate_bps"] == 5_000
    assert edited.json()["appointments_needed"] == 100


def test_rejected_license_is_returned_with_reason(
    client: TestClient,
    db,
    user_factory,
    auth_headers,
    license_factory,
) -> None:
    advisor = user_factory(role="advisor")
    license_row = license_factory(
        user_id=advisor.id,
        state="CA",
        status="rejected",
    )
    license_row.rejection_reason = "Document is unreadable"
    db.commit()
    headers = auth_headers(advisor.email, "StrongPass123!")

    response = client.get("/api/v1/onboarding/me", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["license_status"] == "rejected"
    assert body["licenses"][0]["rejection_reason"] == "Document is unreadable"
