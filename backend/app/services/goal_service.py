import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.goal import AdvisorGoal
from app.models.lead import LeadOutcome
from app.models.purchase import LeadPackage
from app.models.user import User
from app.schemas.goal import AdvisorGoalUpsertRequest
from app.services.subscription_service import SubscriptionService


DEFAULT_ANNUAL_INCOME_GOAL_CENTS = 10_000_00
DEFAULT_AVERAGE_COMMISSION_CENTS = 3_500_00
DEFAULT_APPOINTMENT_TO_DEAL_RATE_BPS = 1_200
DEFAULT_LEAD_TO_APPOINTMENT_RATE_BPS = 2_500


class GoalService:
    """Saved advisor goal persistence and deterministic goal calculations."""

    @staticmethod
    def current_goal_year() -> int:
        return datetime.now(timezone.utc).year

    @staticmethod
    def get_or_create_goal(
        *,
        db: Session,
        user: User,
        target_year: Optional[int] = None,
    ) -> AdvisorGoal:
        year = int(target_year or GoalService.current_goal_year())
        GoalService._validate_target_year(year)

        existing = (
            db.query(AdvisorGoal)
            .filter(AdvisorGoal.user_id == user.id, AdvisorGoal.target_year == year)
            .first()
        )
        if existing is not None:
            return existing

        goal = AdvisorGoal(
            user_id=user.id,
            target_year=year,
            annual_income_goal_cents=DEFAULT_ANNUAL_INCOME_GOAL_CENTS,
            average_commission_cents=DEFAULT_AVERAGE_COMMISSION_CENTS,
            earned_ytd_cents=0,
            appointment_to_deal_rate_bps=DEFAULT_APPOINTMENT_TO_DEAL_RATE_BPS,
            lead_to_appointment_rate_bps=DEFAULT_LEAD_TO_APPOINTMENT_RATE_BPS,
        )
        db.add(goal)
        try:
            db.commit()
            db.refresh(goal)
        except IntegrityError:
            db.rollback()
            existing_after_race = (
                db.query(AdvisorGoal)
                .filter(AdvisorGoal.user_id == user.id, AdvisorGoal.target_year == year)
                .first()
            )
            if existing_after_race is not None:
                return existing_after_race
            raise
        return goal

    @staticmethod
    def update_goal(
        *,
        db: Session,
        user: User,
        payload: AdvisorGoalUpsertRequest,
    ) -> AdvisorGoal:
        GoalService._validate_payload(payload)

        goal = (
            db.query(AdvisorGoal)
            .filter(AdvisorGoal.user_id == user.id, AdvisorGoal.target_year == payload.target_year)
            .first()
        )
        if goal is None:
            goal = AdvisorGoal(user_id=user.id, target_year=payload.target_year)
            db.add(goal)

        goal.annual_income_goal_cents = payload.annual_income_goal_cents
        goal.average_commission_cents = payload.average_commission_cents
        goal.earned_ytd_cents = payload.earned_ytd_cents
        goal.appointment_to_deal_rate_bps = payload.appointment_to_deal_rate_bps
        goal.lead_to_appointment_rate_bps = payload.lead_to_appointment_rate_bps

        try:
            db.commit()
            db.refresh(goal)
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Goal already exists for this advisor and year",
            ) from exc

        return goal

    @staticmethod
    def build_goal_response(*, db: Session, user: User, goal: AdvisorGoal) -> Dict[str, Any]:
        outcome_counts = GoalService.count_outcomes_ytd(
            db=db,
            user=user,
            target_year=int(goal.target_year),
        )
        reached_leads = sum(
            outcome_counts.get(outcome, 0)
            for outcome in ("contacted", "appointment_set", "closed_deal")
        )
        derived = GoalService.calculate_derived_values(
            goal=goal,
            closed_deals_ytd=outcome_counts.get("closed_deal", 0),
            contacted_leads_ytd=outcome_counts.get("contacted", 0),
            appointments_set_ytd=outcome_counts.get("appointment_set", 0),
            reached_leads_ytd=reached_leads,
        )
        return {
            "goal": goal,
            "derived": derived,
            "packages": GoalService.build_package_recommendations(
                db=db,
                leads_remaining=int(derived["leads_remaining"]),
            ),
        }

    @staticmethod
    def calculate_derived_values(
        *,
        goal: AdvisorGoal,
        closed_deals_ytd: int,
        contacted_leads_ytd: int = 0,
        appointments_set_ytd: int = 0,
        reached_leads_ytd: int = 0,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        annual_goal = max(int(goal.annual_income_goal_cents), 1)
        average_commission = max(int(goal.average_commission_cents), 1)
        earned_ytd = max(int(goal.earned_ytd_cents), 0)
        close_rate = GoalService._basis_points_to_ratio(goal.appointment_to_deal_rate_bps)
        appointment_rate = GoalService._basis_points_to_ratio(goal.lead_to_appointment_rate_bps)

        deals_needed = math.ceil(annual_goal / average_commission)
        appointments_needed = math.ceil(deals_needed / close_rate)
        leads_needed = math.ceil(appointments_needed / appointment_rate)
        closed_deals = max(int(closed_deals_ytd), 0)
        contacted_leads = max(int(contacted_leads_ytd), 0)
        appointments_set = max(int(appointments_set_ytd), 0)
        reached_leads = max(int(reached_leads_ytd), 0)
        current_success_rate_bps = (
            min(10_000, round((closed_deals / reached_leads) * 10_000))
            if reached_leads
            else 0
        )
        progress_percent = min(100, round((earned_ytd / annual_goal) * 100))

        remaining_income = max(annual_goal - earned_ytd, 0)
        income_goal_met = remaining_income == 0
        remaining_deal_equivalent = remaining_income / average_commission
        deals_remaining = (
            0
            if income_goal_met
            else math.ceil(remaining_deal_equivalent)
        )
        appointments_remaining = (
            math.ceil(remaining_deal_equivalent / close_rate)
            if remaining_deal_equivalent
            else 0
        )
        leads_remaining = (
            math.ceil(remaining_deal_equivalent / (close_rate * appointment_rate))
            if remaining_deal_equivalent
            else 0
        )
        pacing = GoalService._build_pacing(
            leads_remaining=leads_remaining,
            income_goal_met=income_goal_met,
            target_year=int(goal.target_year),
            now=now,
        )

        return {
            "deals_needed": int(deals_needed),
            "appointments_needed": int(appointments_needed),
            "leads_needed": int(leads_needed),
            "closed_deals_ytd": int(closed_deals),
            "contacted_leads_ytd": int(contacted_leads),
            "appointments_set_ytd": int(appointments_set),
            "reached_leads_ytd": int(reached_leads),
            "current_success_rate_bps": int(current_success_rate_bps),
            "income_progress_percent": int(progress_percent),
            "deals_remaining": int(deals_remaining),
            "appointments_remaining": int(appointments_remaining),
            "leads_remaining": int(leads_remaining),
            "recommended_monthly_leads": int(pacing["recommended_monthly_leads"]),
            "pacing": pacing,
        }

    @staticmethod
    def count_closed_deals_ytd(*, db: Session, user: User, target_year: int) -> int:
        return GoalService.count_outcomes_ytd(
            db=db,
            user=user,
            target_year=target_year,
        ).get("closed_deal", 0)

    @staticmethod
    def count_outcomes_ytd(
        *,
        db: Session,
        user: User,
        target_year: int,
    ) -> Dict[str, int]:
        year_start = datetime(target_year, 1, 1, tzinfo=timezone.utc)
        next_year_start = datetime(target_year + 1, 1, 1, tzinfo=timezone.utc)
        rows = (
            db.query(LeadOutcome.status, func.count(LeadOutcome.id))
            .filter(
                LeadOutcome.user_id == user.id,
                LeadOutcome.updated_at >= year_start,
                LeadOutcome.updated_at < next_year_start,
            )
            .group_by(LeadOutcome.status)
            .all()
        )
        return {str(outcome): int(count or 0) for outcome, count in rows}

    @staticmethod
    def build_package_recommendations(
        *,
        db: Session,
        leads_remaining: int,
    ) -> List[Dict[str, Any]]:
        available_packages = SubscriptionService.get_available_packages(db=db)
        visible_packages = [
            package
            for package in available_packages
            if GoalService._is_goal_recommendation_package(package)
        ]
        if not visible_packages or leads_remaining <= 0:
            return []

        target_leads = max(int(leads_remaining), 1)
        recommendations: List[Dict[str, Any]] = []
        for package in visible_packages:
            credits = GoalService._resolve_package_credits(package)
            packages_needed = math.ceil(target_leads / credits)
            covered_leads = packages_needed * credits
            package_price_cents = max(int(package.price_cents or 0), 0)
            total_cost_cents = packages_needed * package_price_cents
            recommendations.append(
                {
                    "package_id": int(package.id),
                    "name": package.name,
                    "price_cents": int(package.price_cents or 0),
                    "currency": package.currency,
                    "credits_per_package": credits,
                    "packages_needed": int(packages_needed),
                    "total_cost_cents": int(total_cost_cents),
                    "overage_leads": int(max(covered_leads - target_leads, 0)),
                    "estimated_cost_per_lead_cents": math.ceil(package_price_cents / credits),
                    "state_limit": package.state_limit,
                    "features": package.features,
                    "recommended": False,
                }
            )

        best = min(
            recommendations,
            key=lambda item: (
                int(item["total_cost_cents"]),
                int(item["overage_leads"]),
                int(item["packages_needed"]),
                int(item["package_id"]),
            ),
        )
        best["recommended"] = True
        return sorted(
            recommendations,
            key=lambda item: (
                not bool(item["recommended"]),
                int(item["total_cost_cents"]),
                int(item["overage_leads"]),
                int(item["packages_needed"]),
                int(item["package_id"]),
            ),
        )[:3]

    @staticmethod
    def _resolve_package_credits(package: LeadPackage) -> int:
        return SubscriptionService._resolve_package_credits(package)

    @staticmethod
    def _is_goal_recommendation_package(package: LeadPackage) -> bool:
        if GoalService._resolve_package_credits(package) <= 0:
            return False
        if SubscriptionService._is_first_purchase_offer_managed_package(package):
            return False
        if not str(package.stripe_price_id or "").strip():
            return False
        return SubscriptionService._is_package_catalog_available(package)

    @staticmethod
    def _basis_points_to_ratio(value: int) -> float:
        bps = int(value)
        if bps < 1 or bps > 10000:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Rates must be between 1 and 10000 basis points",
            )
        return bps / 10000

    @staticmethod
    def _build_pacing(
        *,
        leads_remaining: int,
        income_goal_met: bool = False,
        target_year: int,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        current = now or datetime.now(timezone.utc)
        if target_year < current.year:
            remaining_months = 1
            status_label = "year_ended"
        elif target_year > current.year:
            remaining_months = 12
            status_label = "future_year"
        else:
            remaining_months = max(1, 12 - current.month + 1)
            status_label = "on_track" if leads_remaining == 0 else "active"

        recommended_monthly_leads = (
            math.ceil(max(int(leads_remaining), 0) / remaining_months)
            if leads_remaining > 0
            else 0
        )
        if income_goal_met:
            message = "Annual income goal met."
            status_label = "goal_met"
        elif leads_remaining <= 0:
            message = "Lead volume goal met based on actual closed deals year-to-date."
        elif target_year < current.year:
            message = (
                f"Goal year ended with {leads_remaining:,} estimated leads still remaining."
            )
        else:
            message = (
                f"Buy about {recommended_monthly_leads:,} leads/month for the rest of the year."
            )

        return {
            "remaining_months": int(remaining_months),
            "recommended_monthly_leads": int(recommended_monthly_leads),
            "status": status_label,
            "message": message,
        }

    @staticmethod
    def _validate_payload(payload: AdvisorGoalUpsertRequest) -> None:
        GoalService._validate_target_year(payload.target_year)
        GoalService._basis_points_to_ratio(payload.appointment_to_deal_rate_bps)
        GoalService._basis_points_to_ratio(payload.lead_to_appointment_rate_bps)

    @staticmethod
    def _validate_target_year(target_year: int) -> None:
        if target_year < 2000 or target_year > 2100:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Target year must be between 2000 and 2100",
            )
