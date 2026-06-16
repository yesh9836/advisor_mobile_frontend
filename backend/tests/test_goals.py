from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.goal import AdvisorGoal
from app.models.lead import LeadDownload, LeadOutcome
from app.schemas.goal import AdvisorGoalUpsertRequest
from app.services.goal_service import GoalService


def _goal_payload(*, target_year: int = 2026, earned_ytd_cents: int = 7_800_000) -> dict[str, int]:
    return {
        "target_year": target_year,
        "annual_income_goal_cents": 25_000_000,
        "average_commission_cents": 350_000,
        "earned_ytd_cents": earned_ytd_cents,
        "appointment_to_deal_rate_bps": 1_200,
        "lead_to_appointment_rate_bps": 2_500,
    }


def test_goal_service_calculates_defaults_and_caps_over_goal(db: Session, user_factory) -> None:
    advisor = user_factory(role="advisor")
    goal = GoalService.get_or_create_goal(db=db, user=advisor, target_year=2026)

    response = GoalService.build_goal_response(db=db, user=advisor, goal=goal)

    assert response["goal"].annual_income_goal_cents == 25_000_000
    assert response["derived"]["deals_needed"] == 72
    assert response["derived"]["appointments_needed"] == 600
    assert response["derived"]["leads_needed"] == 2400
    assert response["derived"]["closed_deals_ytd"] == 0

    goal.earned_ytd_cents = 30_000_000
    derived = GoalService.calculate_derived_values(goal=goal, closed_deals_ytd=0)

    assert derived["income_progress_percent"] == 100
    assert derived["deals_remaining"] == 0
    assert derived["appointments_remaining"] == 0
    assert derived["leads_remaining"] == 0


def test_goal_service_counts_only_explicit_closed_deals_for_advisor_year(
    db: Session,
    user_factory,
    lead_factory,
) -> None:
    advisor = user_factory(role="advisor")
    other_advisor = user_factory(role="advisor")
    closed_lead = lead_factory()
    appointment_lead = lead_factory()
    other_lead = lead_factory()

    db.add_all(
        [
            LeadOutcome(
                user_id=advisor.id,
                lead_id=closed_lead.id,
                status="closed_deal",
                updated_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
            ),
            LeadOutcome(
                user_id=advisor.id,
                lead_id=appointment_lead.id,
                status="appointment_set",
                updated_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
            ),
            LeadOutcome(
                user_id=other_advisor.id,
                lead_id=other_lead.id,
                status="closed_deal",
                updated_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
            ),
        ]
    )
    db.commit()

    assert GoalService.count_closed_deals_ytd(db=db, user=advisor, target_year=2026) == 1


def test_goal_service_package_recommendations_use_live_catalog(
    db: Session,
    user_factory,
    plan_factory,
) -> None:
    advisor = user_factory(role="advisor")
    plan_factory(name="Starter", price_cents=7_500, daily_download_limit=50)
    plan_factory(name="Scale", price_cents=20_000, daily_download_limit=200)
    plan_factory(name="Bulk", price_cents=45_000, daily_download_limit=600)

    request_payload = _goal_payload(target_year=2026)
    goal = GoalService.update_goal(
        db=db,
        user=advisor,
        payload=AdvisorGoalUpsertRequest(**request_payload),
    )
    assert request_payload["target_year"] == goal.target_year

    response = GoalService.build_goal_response(db=db, user=advisor, goal=goal)
    recommendations = response["packages"]

    assert [item["name"].split("-")[0] for item in recommendations] == ["Starter", "Scale", "Bulk"]
    assert recommendations[0]["credits_per_package"] == 50
    assert any(item["recommended"] for item in recommendations)
    best = next(item for item in recommendations if item["recommended"])
    assert best["name"].startswith("Bulk-")


def test_goals_api_fetches_default_and_updates_saved_goal(
    client: TestClient,
    user_factory,
    auth_headers,
) -> None:
    advisor = user_factory(role="advisor", email="goals-advisor@example.com")
    headers = auth_headers(advisor.email, "StrongPass123!")

    get_response = client.get("/api/v1/goals/me?target_year=2026", headers=headers)

    assert get_response.status_code == 200, get_response.text
    default_payload = get_response.json()
    assert default_payload["goal"]["target_year"] == 2026
    assert default_payload["goal"]["annual_income_goal_cents"] == 25_000_000

    put_response = client.put(
        "/api/v1/goals/me",
        headers=headers,
        json=_goal_payload(target_year=2026),
    )

    assert put_response.status_code == 200, put_response.text
    data = put_response.json()
    assert data["goal"]["earned_ytd_cents"] == 7_800_000
    assert data["derived"]["estimated_deals_from_earned_ytd"] == 22
    assert data["derived"]["income_progress_percent"] == 31
    assert data["derived"]["deals_remaining"] == 50
    assert data["derived"]["appointments_remaining"] == 417
    assert data["derived"]["leads_remaining"] == 1667


def test_goals_api_enforces_advisor_auth_and_user_isolation(
    client: TestClient,
    db: Session,
    user_factory,
    auth_headers,
) -> None:
    advisor = user_factory(role="advisor", email="isolated-advisor@example.com")
    other_advisor = user_factory(role="advisor", email="other-advisor@example.com")
    admin = user_factory(role="admin", email="goals-admin@example.com")
    db.add(
        AdvisorGoal(
            user_id=other_advisor.id,
            target_year=2026,
            annual_income_goal_cents=999_000_000,
            average_commission_cents=1_000_000,
            earned_ytd_cents=111_000,
            appointment_to_deal_rate_bps=2_000,
            lead_to_appointment_rate_bps=3_000,
        )
    )
    db.commit()

    advisor_response = client.get(
        "/api/v1/goals/me?target_year=2026",
        headers=auth_headers(advisor.email, "StrongPass123!"),
    )
    admin_response = client.get(
        "/api/v1/goals/me?target_year=2026",
        headers=auth_headers(admin.email, "StrongPass123!"),
    )

    assert advisor_response.status_code == 200
    assert advisor_response.json()["goal"]["annual_income_goal_cents"] == 25_000_000
    assert admin_response.status_code == 403


def test_goals_api_rejects_invalid_inputs(
    client: TestClient,
    user_factory,
    auth_headers,
) -> None:
    advisor = user_factory(role="advisor", email="invalid-goals@example.com")
    headers = auth_headers(advisor.email, "StrongPass123!")

    zero_commission = _goal_payload()
    zero_commission["average_commission_cents"] = 0
    bad_rate = _goal_payload()
    bad_rate["appointment_to_deal_rate_bps"] = 10_001
    negative_earned = _goal_payload()
    negative_earned["earned_ytd_cents"] = -1

    assert client.put("/api/v1/goals/me", headers=headers, json=zero_commission).status_code == 422
    assert client.put("/api/v1/goals/me", headers=headers, json=bad_rate).status_code == 422
    assert client.put("/api/v1/goals/me", headers=headers, json=negative_earned).status_code == 422


def test_delivered_lead_can_be_marked_closed_deal(
    client: TestClient,
    db: Session,
    user_factory,
    lead_factory,
    auth_headers,
) -> None:
    advisor = user_factory(role="advisor", email="closed-deal@example.com")
    lead = lead_factory()
    db.add(LeadDownload(user_id=advisor.id, lead_id=lead.id))
    db.commit()

    response = client.put(
        f"/api/v1/leads/{lead.id}/outcome",
        headers=auth_headers(advisor.email, "StrongPass123!"),
        json={"status": "closed_deal", "notes": "Policy placed"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "closed_deal"
