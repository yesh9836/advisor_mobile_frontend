import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models.lead import Lead, LeadDownload, LeadOutcome
from app.models.license import License
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.lead import LeadCreate, LeadOutcomeUpdateRequest
from app.services.audit_service import AuditService
from app.utils.csv_generator import generate_leads_csv_stream

logger = logging.getLogger(__name__)

US_STATE_CODES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC",
}

DEFAULT_DOWNLOAD_SIZE = 50


class LeadService:
    """Service for lead distribution and downloads."""

    @staticmethod
    def _get_latest_subscription(db: Session, user_id: int) -> Optional[Subscription]:
        return (
            db.query(Subscription)
            .filter(Subscription.user_id == user_id)
            .order_by(Subscription.created_at.desc())
            .first()
        )

    @staticmethod
    def _require_active_subscription(db: Session, user: User) -> Subscription:
        subscription = LeadService._get_latest_subscription(db, user.id)
        now = datetime.now(timezone.utc)

        if not subscription or subscription.status != "active":
            raise HTTPException(status_code=403, detail="Active subscription required")
        
        if subscription.current_period_end and subscription.current_period_end.tzinfo is None:
            subscription.current_period_end = subscription.current_period_end.replace(tzinfo=timezone.utc)

        if not subscription.current_period_end or subscription.current_period_end <= now:
            raise HTTPException(status_code=403, detail="Subscription expired")

        return subscription
    
    @staticmethod
    def _get_user_allowed_states(db: Session, user_id: int, state_limit: Optional[int]) -> List[str]:
        verified_states = (
            db.query(License.state)
            .filter(
                and_(
                    License.user_id == user_id,
                    License.verification_status == "verified",
                )
            )
            .order_by(License.state.asc())
            .all()
        )
        states = [row[0].upper() for row in verified_states]
        if state_limit is not None:
            states = states[:state_limit]
        return states

    @staticmethod
    def _attach_outcomes_to_leads(db: Session, user_id: int, leads: List[Lead]) -> None:
        if not leads:
            return

        lead_ids = [lead.id for lead in leads]
        outcomes = (
            db.query(LeadOutcome)
            .filter(LeadOutcome.user_id == user_id, LeadOutcome.lead_id.in_(lead_ids))
            .all()
        )
        outcomes_by_lead_id = {item.lead_id: item for item in outcomes}

        for lead in leads:
            outcome = outcomes_by_lead_id.get(lead.id)
            setattr(lead, "outcome_status", outcome.status if outcome else None)
            setattr(lead, "outcome_notes", outcome.notes if outcome else None)
            setattr(lead, "outcome_updated_at", outcome.updated_at if outcome else None)

    @staticmethod
    def _attach_downloads_to_leads(db: Session, user_id: int, leads: List[Lead]) -> None:
        if not leads:
            return

        lead_ids = [lead.id for lead in leads]
        downloads = (
            db.query(LeadDownload)
            .filter(LeadDownload.user_id == user_id, LeadDownload.lead_id.in_(lead_ids))
            .order_by(LeadDownload.downloaded_at.desc())
            .all()
        )

        latest_by_lead_id: Dict[int, LeadDownload] = {}
        for download in downloads:
            if download.lead_id not in latest_by_lead_id:
                latest_by_lead_id[download.lead_id] = download

        for lead in leads:
            download = latest_by_lead_id.get(lead.id)
            setattr(lead, "is_downloaded", download is not None)
            setattr(lead, "downloaded_at", download.downloaded_at if download else None)
    

    @staticmethod
    def _get_exportable_leads_for_user(
        db: Session,
        user: User,
        size: int = DEFAULT_DOWNLOAD_SIZE,
    ) -> List[Lead]:
        subscription = LeadService._require_active_subscription(db, user)
        plan = subscription.plan

        states = LeadService._get_user_allowed_states(db, user.id, plan.state_limit)
        if not states:
            return []

        downloaded_subquery = (
            select(LeadDownload.lead_id)
            .where(LeadDownload.user_id == user.id)
        )

        return (
            db.query(Lead)
            .filter(Lead.state_code.in_(states))
            .filter(~Lead.id.in_(downloaded_subquery))
            .order_by(Lead.created_at.desc())
            .limit(size)
            .all()
        )


    @staticmethod
    def get_available_leads_for_user(
        db: Session,
        user: User,
        page: int = 1,
        size: int = 20,
        delivery_status: str = "all",
    ) -> Dict[str, object]:
        subscription = LeadService._require_active_subscription(db, user)
        plan = subscription.plan

        states = LeadService._get_user_allowed_states(db, user.id, plan.state_limit)
        if not states:
            return {"items": [], "total": 0, "page": page, "size": size}

        downloaded_subquery = (
            select(LeadDownload.lead_id)
            .where(LeadDownload.user_id == user.id)
        )

        query = db.query(Lead).filter(Lead.state_code.in_(states))

        if delivery_status == "available":
            query = query.filter(~Lead.id.in_(downloaded_subquery))
        elif delivery_status == "delivered":
            query = query.filter(Lead.id.in_(downloaded_subquery))

        total = query.count()
        offset = max(0, (page - 1) * size)

        items = (
            query.order_by(Lead.created_at.desc())
            .offset(offset)
            .limit(size)
            .all()
        )

        LeadService._attach_outcomes_to_leads(db, user.id, items)
        LeadService._attach_downloads_to_leads(db, user.id, items)

        return {"items": items, "total": total, "page": page, "size": size}

    @staticmethod
    def can_user_download_leads(db: Session, user: User) -> Dict[str, object]:
        subscription = LeadService._get_latest_subscription(db, user.id)
        now = datetime.now(timezone.utc)

        if not subscription or subscription.status != "active":
            return {"can_download": False, "reason": "No active subscription", "remaining": 0}
        
        if subscription.current_period_end and subscription.current_period_end.tzinfo is None:
            subscription.current_period_end = subscription.current_period_end.replace(tzinfo=timezone.utc)

        if not subscription.current_period_end or subscription.current_period_end <= now:
            return {"can_download": False, "reason": "Subscription expired", "remaining": 0}

        plan = subscription.plan
        daily_limit = plan.daily_download_limit

        if daily_limit is None or daily_limit >= 999999:
            return {"can_download": True, "remaining": -1}

        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        today_count = (
            db.query(func.count(LeadDownload.id))
            .filter(LeadDownload.user_id == user.id)
            .filter(LeadDownload.downloaded_at >= today_start)
            .scalar()
        ) or 0

        if today_count >= daily_limit:
            return {"can_download": False, "reason": "Daily limit reached", "remaining": 0}

        return {"can_download": True, "remaining": daily_limit - today_count}

    @staticmethod
    def download_leads_csv(db: Session, user: User) -> str:
        check = LeadService.can_user_download_leads(db, user)
        if not check["can_download"]:
            raise HTTPException(status_code=403, detail=check["reason"])

        remaining = int(check["remaining"])
        prepend_msg = ""

        export_size = DEFAULT_DOWNLOAD_SIZE if remaining < 0 else min(DEFAULT_DOWNLOAD_SIZE, remaining)
        leads = LeadService._get_exportable_leads_for_user(
            db=db,
            user=user,
            size=export_size,
        )

        if not leads:
            # Return empty CSV with headers
            return generate_leads_csv_stream([], prepend_message=prepend_msg)

        # Record downloads in DB (Atomic Batch)
        batch_id = uuid4().hex
        try:
            for lead in leads:
                db.add(
                    LeadDownload(
                        user_id=user.id,
                        lead_id=lead.id,
                        csv_batch_id=batch_id,
                    )
                )
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to record lead downloads: {e}")
            raise HTTPException(status_code=500, detail="Failed to record lead downloads")

        return generate_leads_csv_stream(leads, prepend_message=prepend_msg)

    @staticmethod
    def create_lead(db: Session, data: LeadCreate) -> Lead:
        lead_data = data.model_dump(exclude_unset=True)

        source = lead_data.pop("source", None) or "manual_entry"
        lead_data["source"] = source

        if "state_code" in lead_data and lead_data["state_code"]:
            lead_data["state_code"] = lead_data["state_code"].strip().upper()

        lead = Lead(**lead_data)

        try:
            db.add(lead)
            db.commit()
            db.refresh(lead)
            return lead
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create lead: {e}")
            raise HTTPException(status_code=500, detail="Failed to create lead")

    @staticmethod
    def bulk_import_leads(db: Session, csv_data: List[dict]) -> Dict[str, object]:
        errors: List[Dict[str, object]] = []

        if not csv_data:
            return {"success": 0, "failed": 0, "errors": []}

        phones = {row.get("mobile_phone") for row in csv_data if row.get("mobile_phone")}
        existing_phones = set()
        if phones:
            existing_rows = (
                db.query(Lead.mobile_phone)
                .filter(Lead.mobile_phone.in_(phones))
                .all()
            )
            existing_phones = {row[0] for row in existing_rows if row[0]}

        seen_phones = set()
        valid_rows: List[dict] = []

        for idx, row in enumerate(csv_data):
            row_num = idx + 2
            row_errors: List[str] = []

            state_code = (row.get("state_code") or "").strip().upper()
            mobile_phone = (row.get("mobile_phone") or "").strip()

            if not state_code:
                row_errors.append("Missing state_code")
            if not mobile_phone:
                row_errors.append("Missing mobile_phone")

            if state_code and (len(state_code) != 2 or state_code not in US_STATE_CODES):
                row_errors.append("Invalid state_code")

            if mobile_phone and mobile_phone in existing_phones:
                row_errors.append("Duplicate mobile_phone")

            if mobile_phone and mobile_phone in seen_phones:
                row_errors.append("Duplicate mobile_phone in file")

            if row_errors:
                for err in row_errors:
                    errors.append({"row": row_num, "error": err})
                continue

            seen_phones.add(mobile_phone)

            clean_row = dict(row)
            clean_row["state_code"] = state_code
            clean_row["mobile_phone"] = mobile_phone
            clean_row["source"] = "csv_import"

            valid_rows.append(clean_row)

        if errors:
            return {"success": 0, "failed": len(errors), "errors": errors}

        try:
            leads = [Lead(**row) for row in valid_rows]
            db.add_all(leads)
            db.commit()
            return {"success": len(leads), "failed": 0, "errors": []}
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to import leads: {e}")
            raise HTTPException(status_code=500, detail="Failed to import leads")

    @staticmethod
    def upsert_lead_outcome(
        db: Session,
        user: User,
        lead_id: int,
        payload: LeadOutcomeUpdateRequest,
    ) -> LeadOutcome:
        subscription = LeadService._require_active_subscription(db, user)
        states = LeadService._get_user_allowed_states(db, user.id, subscription.plan.state_limit)

        if not states:
            raise HTTPException(status_code=404, detail="Lead not found")

        lead = (
            db.query(Lead)
            .filter(Lead.id == lead_id, Lead.state_code.in_(states))
            .first()
        )
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")

        outcome = (
            db.query(LeadOutcome)
            .filter(LeadOutcome.user_id == user.id, LeadOutcome.lead_id == lead_id)
            .first()
        )

        previous_status = outcome.status if outcome else None
        previous_notes = outcome.notes if outcome else None

        if outcome is None:
            outcome = LeadOutcome(
                user_id=user.id,
                lead_id=lead_id,
                status=payload.status,
                notes=payload.notes,
            )
            db.add(outcome)
        else:
            outcome.status = payload.status
            outcome.notes = payload.notes

        try:
            db.commit()
            db.refresh(outcome)
        except Exception as exc:
            db.rollback()
            logger.error("Failed to save lead outcome: %s", exc)
            raise HTTPException(status_code=500, detail="Failed to save lead outcome")

        AuditService.log_event(
            actor_user_id=user.id,
            action="lead_outcome_updated",
            entity_type="LeadOutcome",
            entity_id=outcome.id,
            meta_data={
                "lead_id": lead_id,
                "previous_status": previous_status,
                "new_status": outcome.status,
                "notes_changed": previous_notes != outcome.notes,
                "notes_length": len(outcome.notes or ""),
            },
        )

        return outcome

    @staticmethod
    def _calculate_cost_per_appointment(plan_price_cents: int, appointments_set: int) -> float:
        if appointments_set <= 0:
            return 0.0
        return round((plan_price_cents / 100.0) / appointments_set, 2)

    @staticmethod
    def get_dashboard_summary(db: Session, user: User) -> Dict[str, object]:
        subscription = LeadService._require_active_subscription(db, user)
        plan = subscription.plan

        now = datetime.now(timezone.utc)
        seven_days_ago = now - timedelta(days=7)

        states = LeadService._get_user_allowed_states(db, user.id, plan.state_limit)

        leads_delivered_7_days = 0
        if states:
            leads_delivered_7_days = (
                db.query(func.count(func.distinct(LeadDownload.lead_id)))
                .filter(LeadDownload.user_id == user.id)
                .filter(LeadDownload.downloaded_at >= seven_days_ago)
                .scalar()
            ) or 0

        appointments_set_7_days = (
            db.query(func.count(LeadOutcome.id))
            .filter(
                LeadOutcome.user_id == user.id,
                LeadOutcome.status == "appointment_set",
                LeadOutcome.updated_at >= seven_days_ago,
            )
            .scalar()
        ) or 0

        cost_per_appointment = LeadService._calculate_cost_per_appointment(
            plan_price_cents=plan.price_cents,
            appointments_set=appointments_set_7_days,
        )

        return {
            "leads_delivered_7_days": int(leads_delivered_7_days),
            "appointments_set_7_days": int(appointments_set_7_days),
            "cost_per_appointment": cost_per_appointment,
            "currency": (plan.currency or "USD").upper(),
            "settings": {
                "email_alerts_enabled": True,
                "sms_alerts_enabled": False,
                "target_states": states,
                "min_assets": None,
                "daily_download_limit": plan.daily_download_limit,
            },
        }
