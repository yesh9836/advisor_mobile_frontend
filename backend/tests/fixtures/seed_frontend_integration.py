"""Create the database state required by the frontend integration smoke test."""

import logging
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.append(os.getcwd())

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.goal import AdvisorGoal
from app.models.lead import Lead, LeadOutcome, LeadOwnership
from app.models.license import License
from app.models.purchase import LeadPackage, LeadPurchase
from app.models.user import User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEMO_ADMIN_EMAIL = "admin.demo@example.com"
DEMO_ADVISOR_EMAIL = "advisor.demo@example.com"
DEMO_PASSWORD = "Password123!"

TARGET_STATES = ["FL", "GA", "TX", "AL", "CA"]

def _resolve_seed_stripe_price_id(plan_key: str, fallback: str) -> str:
    """Allow seed price IDs to be configured from env for real Stripe test accounts."""
    for env_key in (f"SEED_STRIPE_PRICE_ID_{plan_key}", f"STRIPE_PRICE_ID_{plan_key}"):
        value = os.getenv(env_key, "").strip()
        if value:
            return value
    return fallback


def _warn_if_placeholder_price_id(plan_name: str, plan_key: str, price_id: str) -> None:
    if price_id.startswith("price_fake_"):
        logger.warning(
            "Plan %s is using placeholder stripe_price_id=%s. Set %s (or STRIPE_PRICE_ID_%s) before running this script for Stripe checkout tests.",
            plan_name,
            price_id,
            f"SEED_STRIPE_PRICE_ID_{plan_key}",
            plan_key,
        )


def _build_plan_data() -> list[dict[str, object]]:
    basic_price_id = _resolve_seed_stripe_price_id("BASIC", "price_fake_basic_123")
    pro_price_id = _resolve_seed_stripe_price_id("PRO", "price_fake_pro_456")
    unlimited_price_id = _resolve_seed_stripe_price_id("UNLIMITED", "price_fake_unlim_789")
    _warn_if_placeholder_price_id("Basic", "BASIC", basic_price_id)
    _warn_if_placeholder_price_id("Pro", "PRO", pro_price_id)
    _warn_if_placeholder_price_id("Unlimited", "UNLIMITED", unlimited_price_id)

    return [
        {
            "name": "Basic",
            "price_cents": 9900,
            "currency": "USD",
            "stripe_price_id": basic_price_id,
            "state_limit": 1,
            "daily_download_limit": 10,
            "features": {"support": "email"},
        },
        {
            "name": "Pro",
            "price_cents": 19900,
            "currency": "USD",
            "stripe_price_id": pro_price_id,
            "state_limit": 3,
            "daily_download_limit": 50,
            "features": {"support": "priority"},
        },
        {
            "name": "Unlimited",
            "price_cents": 29900,
            "currency": "USD",
            "stripe_price_id": unlimited_price_id,
            "state_limit": None,
            "daily_download_limit": 100,
            "features": {"support": "24/7"},
        },
    ]


PLAN_DATA = _build_plan_data()


def ensure_user(
    db: Session,
    *,
    email: str,
    name: str,
    role: str,
    phone: str | None,
    password: str,
    stripe_customer_id: str | None = None,
) -> User:
    user = db.query(User).filter(User.email == email).first()
    if user:
        user.name = name
        user.role = role
        user.phone = phone
        if stripe_customer_id and not user.stripe_customer_id:
            user.stripe_customer_id = stripe_customer_id
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    user = User(
        email=email,
        name=name,
        role=role,
        phone=phone,
        password_hash=get_password_hash(password),
        stripe_customer_id=stripe_customer_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def ensure_plans(db: Session) -> dict[str, LeadPackage]:
    plans: dict[str, LeadPackage] = {}

    for plan_data in PLAN_DATA:
        existing = db.query(LeadPackage).filter(LeadPackage.name == plan_data["name"]).first()
        if existing:
            existing.price_cents = plan_data["price_cents"]
            existing.currency = plan_data["currency"]
            existing.stripe_price_id = plan_data["stripe_price_id"]
            existing.state_limit = plan_data["state_limit"]
            existing.daily_download_limit = plan_data["daily_download_limit"]
            existing.features = plan_data["features"]
            db.add(existing)
            plans[existing.name] = existing
            continue

        plan = LeadPackage(**plan_data)
        db.add(plan)
        db.flush()
        plans[plan.name] = plan

    db.commit()
    for name in list(plans.keys()):
        db.refresh(plans[name])

    return plans


def ensure_verified_licenses(db: Session, advisor: User, admin: User) -> None:
    now = datetime.now(timezone.utc)

    for state in TARGET_STATES:
        license_number = f"DEMO-{advisor.id}-{state}-001"
        lic = (
            db.query(License)
            .filter(
                and_(
                    License.user_id == advisor.id,
                    License.state == state,
                )
            )
            .first()
        )

        if not lic:
            lic = License(
                user_id=advisor.id,
                state=state,
                license_number=license_number,
                license_type="RIA",
                document_path=f"uploads/licenses/{advisor.id}/{state.lower()}_demo.pdf",
                verification_status="verified",
                verified_at=now,
                verified_by=admin.id,
            )
        else:
            lic.license_number = license_number
            lic.license_type = "RIA"
            lic.document_path = f"uploads/licenses/{advisor.id}/{state.lower()}_demo.pdf"
            lic.verification_status = "verified"
            lic.verified_at = now
            lic.verified_by = admin.id

        db.add(lic)

    db.commit()


def ensure_completed_purchase(db: Session, advisor: User, package: LeadPackage) -> LeadPurchase:
    now = datetime.now(timezone.utc)
    checkout_session_id = f"cs_seed_demo_{advisor.id}_{package.id}"
    payment_intent_id = f"pi_seed_demo_{advisor.id}_{package.id}"

    credits_total = max(int(package.daily_download_limit or 0), 0)
    if isinstance(package.features, dict):
        raw_credits = package.features.get("credits_total", package.features.get("credits"))
        if isinstance(raw_credits, (int, float)):
            credits_total = max(int(raw_credits), 0)
        elif isinstance(raw_credits, str) and raw_credits.isdigit():
            credits_total = int(raw_credits)

    purchase = (
        db.query(LeadPurchase)
        .filter(LeadPurchase.stripe_checkout_session_id == checkout_session_id)
        .first()
    )
    if not purchase:
        purchase = LeadPurchase(
            user_id=advisor.id,
            package_id=package.id,
            stripe_checkout_session_id=checkout_session_id,
            stripe_payment_intent_id=payment_intent_id,
            amount_cents=package.price_cents,
            currency=(package.currency or "USD").upper(),
            credits_total=credits_total,
            credits_remaining=credits_total,
            status="completed",
            purchased_at=now,
        )
        db.add(purchase)
    else:
        purchase.user_id = advisor.id
        purchase.package_id = package.id
        purchase.stripe_payment_intent_id = payment_intent_id
        purchase.amount_cents = package.price_cents
        purchase.currency = (package.currency or "USD").upper()
        purchase.credits_total = credits_total
        purchase.credits_remaining = credits_total
        purchase.status = "completed"
        purchase.purchased_at = now
        db.add(purchase)

    db.commit()
    db.refresh(purchase)
    return purchase


def ensure_leads(db: Session, states: list[str], count_per_state: int = 12) -> list[Lead]:
    now = datetime.now(timezone.utc)
    created = 0

    for state_idx, state in enumerate(states, start=1):
        for i in range(1, count_per_state + 1):
            mobile_phone = f"+1555{state_idx:02d}{i:04d}"
            existing = db.query(Lead).filter(Lead.mobile_phone == mobile_phone).first()
            if existing:
                continue

            days_ago = (i - 1) % 10
            created_at = now - timedelta(days=days_ago, hours=i % 6)

            lead = Lead(
                source="manual_entry",
                state_code=state,
                zip_code=f"33{state_idx}{i:02d}",
                first_name=f"Test{state}{i}",
                last_name="Lead",
                mobile_phone=mobile_phone,
                preferred_follow_up_method="Phone",
                best_time_to_reach="Morning",
                retirement_timeline="Within 5 years",
                confidence_in_long_term_plan="Somewhat confident",
                most_important_retirement_activity="Travel",
                expected_retirement_income_source="401k",
                total_investable_assets_range="$100k-$250k",
                has_financial_advisor="No",
                additional_notes=f"Seed lead for {state}",
                created_at=created_at,
                updated_at=created_at,
            )
            db.add(lead)
            created += 1

    db.commit()
    logger.info("Leads created: %s", created)

    return (
        db.query(Lead)
        .filter(Lead.state_code.in_(states))
        .order_by(Lead.created_at.desc())
        .all()
    )


def ensure_outcomes(db: Session, advisor: User, leads: list[Lead], max_rows: int = 9) -> None:
    statuses = [
        "new",
        "contacted",
        "appointment_set",
        "closed_deal",
        "contacted",
        "appointment_set",
        "closed_deal",
        "new",
        "appointment_set",
    ]
    now = datetime.now(timezone.utc)
    updated = 0

    for idx, lead in enumerate(leads[:max_rows]):
        status = statuses[idx % len(statuses)]
        notes = f"Seed outcome for lead {lead.id} ({status})"

        outcome = (
            db.query(LeadOutcome)
            .filter(
                LeadOutcome.user_id == advisor.id,
                LeadOutcome.lead_id == lead.id,
            )
            .first()
        )

        if not outcome:
            outcome = LeadOutcome(
                user_id=advisor.id,
                lead_id=lead.id,
                status=status,
                notes=notes,
            )
        else:
            outcome.status = status
            outcome.notes = notes

        outcome.updated_at = now - timedelta(days=(idx % 6))
        db.add(outcome)
        updated += 1

    db.commit()
    logger.info("Outcomes upserted: %s", updated)


def ensure_current_goal(db: Session, advisor: User) -> AdvisorGoal:
    target_year = datetime.now(timezone.utc).year
    goal = (
        db.query(AdvisorGoal)
        .filter(
            AdvisorGoal.user_id == advisor.id,
            AdvisorGoal.target_year == target_year,
        )
        .first()
    )
    if goal is None:
        goal = AdvisorGoal(user_id=advisor.id, target_year=target_year)

    # Keep this profile aligned with the populated Demo Advisor experience
    # used by the emulator: $180k target, $36k earned, and a $6k average
    # commission. The derived remaining metrics are 24 deals, 96
    # appointments, and 960 leads.
    goal.annual_income_goal_cents = 18_000_000
    goal.average_sale_cents = 3_000_000
    goal.commission_rate_bps = 2_000
    goal.average_commission_cents = 600_000
    goal.earned_ytd_cents = 3_600_000
    goal.appointment_to_deal_rate_bps = 2_500
    goal.lead_to_appointment_rate_bps = 1_000
    goal.onboarding_completed_at = (
        goal.onboarding_completed_at or datetime.now(timezone.utc)
    )
    goal.onboarding_consent_at = (
        goal.onboarding_consent_at or datetime.now(timezone.utc)
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    logger.info(
        "Current goal and onboarding upserted: annual=$%s earned=$%s",
        goal.annual_income_goal_cents // 100,
        goal.earned_ytd_cents // 100,
    )
    return goal


def ensure_recent_dashboard_deliveries(
    db: Session,
    advisor: User,
    purchase: LeadPurchase,
    leads: list[Lead],
    max_rows: int = 9,
) -> list[Lead]:
    """Keep repeatable demo deliveries inside the dashboard's seven-day window."""
    now = datetime.now(timezone.utc)
    assigned_leads: list[Lead] = []

    for lead in leads:
        ownership = (
            db.query(LeadOwnership)
            .filter(LeadOwnership.lead_id == lead.id)
            .first()
        )
        if ownership is not None and ownership.user_id != advisor.id:
            continue

        assigned_at = now - timedelta(days=len(assigned_leads) % 6)
        if ownership is None:
            ownership = LeadOwnership(
                user_id=advisor.id,
                lead_id=lead.id,
                purchase_id=purchase.id,
                assigned_at=assigned_at,
            )
        else:
            ownership.purchase_id = purchase.id
            ownership.assigned_at = assigned_at

        db.add(ownership)
        assigned_leads.append(lead)
        if len(assigned_leads) >= max_rows:
            break

    db.commit()
    logger.info("Recent dashboard deliveries upserted: %s", len(assigned_leads))
    return assigned_leads


def main() -> None:
    db = SessionLocal()
    try:
        plans = ensure_plans(db)

        admin = ensure_user(
            db,
            email=DEMO_ADMIN_EMAIL,
            name="Demo Admin",
            role="admin",
            phone="555-0100",
            password=DEMO_PASSWORD,
        )

        advisor = ensure_user(
            db,
            email=DEMO_ADVISOR_EMAIL,
            name="Demo Advisor",
            role="advisor",
            phone="555-0101",
            password=DEMO_PASSWORD,
            stripe_customer_id="cus_demo_advisor_001",
        )

        ensure_verified_licenses(db, advisor, admin)
        purchase = ensure_completed_purchase(db, advisor, plans["Pro"])
        leads = ensure_leads(db, TARGET_STATES, count_per_state=12)
        dashboard_leads = ensure_recent_dashboard_deliveries(
            db,
            advisor,
            purchase,
            leads,
            max_rows=9,
        )
        ensure_outcomes(db, advisor, dashboard_leads, max_rows=9)
        ensure_current_goal(db, advisor)

        logger.info("Seed complete.")
        logger.info("Advisor login: %s / %s", DEMO_ADVISOR_EMAIL, DEMO_PASSWORD)
        logger.info("Admin login: %s / %s", DEMO_ADMIN_EMAIL, DEMO_PASSWORD)

    except Exception as exc:
        db.rollback()
        logger.error("Seeding failed: %s", exc)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
