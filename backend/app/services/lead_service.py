import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Generator
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models.lead import Lead, LeadDownload
from app.models.license import License
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.lead import LeadCreate
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
    def get_available_leads_for_user(
        db: Session,
        user: User,
        page: int = 1,
        size: int = 20
    ) -> Dict[str, object]:
        subscription = LeadService._require_active_subscription(db, user)
        plan = subscription.plan

        verified_states = (
            db.query(License.state)
            .filter(
                and_(
                    License.user_id == user.id,
                    License.verification_status == "verified",
                )
            )
            .order_by(License.state.asc())
            .all()
        )
        states = [row[0].upper() for row in verified_states]

        if not states:
            return {"items": [], "total": 0, "page": page, "size": size}

        if plan.state_limit is not None:
            states = states[: plan.state_limit]

        if not states:
            return {"items": [], "total": 0, "page": page, "size": size}

        downloaded_subquery = (
            select(LeadDownload.lead_id)
            .where(LeadDownload.user_id == user.id)
        )

        query = (
            db.query(Lead)
            .filter(Lead.state_code.in_(states))
            .filter(~Lead.id.in_(downloaded_subquery))
        )

        total = query.count()
        offset = max(0, (page - 1) * size)

        items = (
            query.order_by(Lead.created_at.desc())
            .offset(offset)
            .limit(size)
            .all()
        )

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
            .filter(func.date(LeadDownload.downloaded_at) >= today_start)
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
        available = LeadService.get_available_leads_for_user(
            db=db,
            user=user,
            page=1,
            size=DEFAULT_DOWNLOAD_SIZE,
        )
        leads: List[Lead] = available["items"]

        requested_count = len(leads)
        prepend_msg = ""

        if remaining >= 0 and requested_count > remaining:
            leads = leads[:remaining]
            prepend_msg = f"# Daily limit reached. Returned {len(leads)} of {requested_count} leads."

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
