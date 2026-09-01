from datetime import datetime, timedelta, timezone

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


def test_goal_service_calculates_defaults_and_completes_when_income_goal_met(
    db: Session,
    user_factory,
) -> None:
    advisor = user_factory(role="advisor")
    goal = GoalService.get_or_create_goal(db=db, user=advisor, target_year=2026)

    response = GoalService.build_goal_response(db=db, user=advisor, goal=goal)

    assert response["goal"].annual_income_goal_cents == 1_000_000
    assert response["derived"]["deals_needed"] == 3
    assert response["derived"]["appointments_needed"] == 25
    assert response["derived"]["leads_needed"] == 100
    assert response["derived"]["closed_deals_ytd"] == 0

    goal.annual_income_goal_cents = 25_000_000
    goal.earned_ytd_cents = 7_800_000
    earned_ytd_derived = GoalService.calculate_derived_values(goal=goal, closed_deals_ytd=0)

    assert earned_ytd_derived["income_progress_percent"] == 31
    assert earned_ytd_derived["deals_remaining"] == 50
    assert earned_ytd_derived["appointments_remaining"] == 410
    assert earned_ytd_derived["leads_remaining"] == 1639

    goal.earned_ytd_cents = 30_000_000
    derived = GoalService.calculate_derived_values(goal=goal, closed_deals_ytd=0)

    assert derived["income_progress_percent"] == 100
    assert derived["deals_remaining"] == 0
    assert derived["appointments_remaining"] == 0
    assert derived["leads_remaining"] == 0
    assert derived["pacing"]["status"] == "goal_met"
    assert derived["pacing"]["message"] == "Annual income goal met."

    closed_deal_derived = GoalService.calculate_derived_values(goal=goal, closed_deals_ytd=3)

    assert closed_deal_derived["income_progress_percent"] == 100
    assert closed_deal_derived["deals_remaining"] == 0
    assert closed_deal_derived["appointments_remaining"] == 0
    assert closed_deal_derived["leads_remaining"] == 0


def test_goal_service_returns_no_packages_when_income_goal_met(
    db: Session,
    user_factory,
    plan_factory,
) -> None:
    advisor = user_factory(role="advisor")
    plan_factory(name="Starter", price_cents=100, daily_download_limit=10)
    goal = GoalService.update_goal(
        db=db,
        user=advisor,
        payload=AdvisorGoalUpsertRequest(
            **_goal_payload(target_year=2026, earned_ytd_cents=25_000_000)
        ),
    )

    response = GoalService.build_goal_response(db=db, user=advisor, goal=goal)

    assert response["derived"]["leads_remaining"] == 0
    assert response["derived"]["pacing"]["status"] == "goal_met"
    assert response["packages"] == []


def test_goal_service_manual_earned_ytd_drives_remaining_volume_even_with_closed_deals(
    db: Session,
    user_factory,
) -> None:
    advisor = user_factory(role="advisor")
    goal = GoalService.get_or_create_goal(db=db, user=advisor, target_year=2026)
    goal.annual_income_goal_cents = 1_000_000
    goal.average_commission_cents = 50_000
    goal.earned_ytd_cents = 40_000
    goal.appointment_to_deal_rate_bps = 300
    goal.lead_to_appointment_rate_bps = 500

    earned_400 = GoalService.calculate_derived_values(goal=goal, closed_deals_ytd=2)
    goal.earned_ytd_cents = 100_000
    earned_1000 = GoalService.calculate_derived_values(goal=goal, closed_deals_ytd=2)

    assert earned_400["deals_remaining"] == 20
    assert earned_400["appointments_remaining"] == 640
    assert earned_400["leads_remaining"] == 12800
    assert earned_1000["deals_remaining"] == 18
    assert earned_1000["appointments_remaining"] == 600
    assert earned_1000["leads_remaining"] == 12000


def test_goal_service_changes_volume_within_average_commission_band(
    db: Session,
    user_factory,
) -> None:
    advisor = user_factory(role="advisor")
    goal = GoalService.get_or_create_goal(db=db, user=advisor, target_year=2026)
    goal.annual_income_goal_cents = 1_000_000
    goal.average_commission_cents = 350_000
    goal.earned_ytd_cents = 300_000
    goal.appointment_to_deal_rate_bps = 500
    goal.lead_to_appointment_rate_bps = 500

    earned_3000 = GoalService.calculate_derived_values(goal=goal, closed_deals_ytd=0)
    goal.earned_ytd_cents = 900_000
    earned_9000 = GoalService.calculate_derived_values(goal=goal, closed_deals_ytd=0)

    assert earned_3000["deals_remaining"] == 2
    assert earned_3000["appointments_remaining"] == 40
    assert earned_3000["leads_remaining"] == 800
    assert earned_9000["deals_remaining"] == 1
    assert earned_9000["appointments_remaining"] == 6
    assert earned_9000["leads_remaining"] == 115


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
    outcome_counts = GoalService.count_outcomes_ytd(
        db=db,
        user=advisor,
        target_year=2026,
    )
    assert outcome_counts == {"appointment_set": 1, "closed_deal": 1}

    goal = GoalService.get_or_create_goal(db=db, user=advisor, target_year=2026)
    derived = GoalService.calculate_derived_values(
        goal=goal,
        closed_deals_ytd=outcome_counts["closed_deal"],
        appointments_set_ytd=outcome_counts["appointment_set"],
        reached_leads_ytd=sum(outcome_counts.values()),
    )
    assert derived["contacted_leads_ytd"] == 0
    assert derived["appointments_set_ytd"] == 1
    assert derived["reached_leads_ytd"] == 2
    assert derived["current_success_rate_bps"] == 5000


def test_goal_service_package_recommendations_use_live_catalog(
    db: Session,
    user_factory,
    plan_factory,
) -> None:
    now = datetime.now(timezone.utc)
    advisor = user_factory(role="advisor")
    plan_factory(name="Starter", price_cents=100, daily_download_limit=10)
    plan_factory(name="Scale", price_cents=200, daily_download_limit=10)
    plan_factory(name="GoodFit", price_cents=350, daily_download_limit=100)
    hidden = plan_factory(name="HiddenGoalPackage", price_cents=1, daily_download_limit=1000)
    future = plan_factory(name="FutureGoalPackage", price_cents=1, daily_download_limit=1000)
    expired = plan_factory(name="ExpiredGoalPackage", price_cents=1, daily_download_limit=1000)

    hidden.features = {"credits_total": 1000, "catalog_visible": False}
    future.features = {"credits_total": 1000, "catalog_visible": True}
    future.effective_from = now + timedelta(days=1)
    expired.features = {"credits_total": 1000, "catalog_visible": True}
    expired.effective_to = now - timedelta(days=1)
    db.commit()

    request_payload = _goal_payload(target_year=2026)
    goal = GoalService.update_goal(
        db=db,
        user=advisor,
        payload=AdvisorGoalUpsertRequest(**request_payload),
    )
    assert request_payload["target_year"] == goal.target_year

    response = GoalService.build_goal_response(db=db, user=advisor, goal=goal)
    recommendations = response["packages"]

    assert [item["name"].split("-")[0] for item in recommendations] == ["GoodFit", "Starter", "Scale"]
    assert any(item["recommended"] for item in recommendations)
    best = next(item for item in recommendations if item["recommended"])
    assert best["name"].startswith("GoodFit-")
    assert not any(item["name"].startswith("HiddenGoalPackage-") for item in recommendations)
    assert not any(item["name"].startswith("FutureGoalPackage-") for item in recommendations)
    assert not any(item["name"].startswith("ExpiredGoalPackage-") for item in recommendations)


def test_goal_service_package_recommendations_tie_break_by_overage_and_id(
    db: Session,
    plan_factory,
) -> None:
    larger_overage = plan_factory(name="LargerOverage", price_cents=100, daily_download_limit=100)
    exact_fit = plan_factory(name="ExactFit", price_cents=100, daily_download_limit=95)
    same_score_later_id = plan_factory(name="ExactFitLater", price_cents=100, daily_download_limit=95)

    recommendations = GoalService.build_package_recommendations(db=db, leads_remaining=95)

    assert [item["package_id"] for item in recommendations] == [
        exact_fit.id,
        same_score_later_id.id,
        larger_overage.id,
    ]
    assert recommendations[0]["recommended"] is True
    assert recommendations[0]["overage_leads"] == 0


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
    assert default_payload["goal"]["annual_income_goal_cents"] == 1_000_000
    assert default_payload["derived"]["deals_needed"] == 3
    assert default_payload["derived"]["appointments_needed"] == 25
    assert default_payload["derived"]["leads_needed"] == 100

    put_response = client.put(
        "/api/v1/goals/me",
        headers=headers,
        json=_goal_payload(target_year=2026),
    )

    assert put_response.status_code == 200, put_response.text
    data = put_response.json()
    assert data["goal"]["earned_ytd_cents"] == 7_800_000
    assert data["derived"]["income_progress_percent"] == 31
    assert data["derived"]["deals_remaining"] == 50
    assert data["derived"]["appointments_remaining"] == 410
    assert data["derived"]["leads_remaining"] == 1639


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
    assert advisor_response.json()["goal"]["annual_income_goal_cents"] == 1_000_000
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
