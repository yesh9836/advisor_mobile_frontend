import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Literal, Optional
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
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

        return LeadService._get_exportable_leads_for_states(
            db=db,
            user_id=user.id,
            states=states,
            size=size,
        )

    @staticmethod
    def _get_exportable_leads_for_states(
        db: Session,
        user_id: int,
        states: List[str],
        size: int,
    ) -> List[Lead]:
        downloaded_subquery = (
            select(LeadDownload.lead_id)
            .where(LeadDownload.user_id == user_id)
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
    def _is_unlimited_daily_limit(daily_limit: Optional[int]) -> bool:
        return daily_limit is None or daily_limit >= 999999

    @staticmethod
    def _get_today_download_count(db: Session, user_id: int, today_start: datetime) -> int:
        return (
            db.query(func.count(LeadDownload.id))
            .filter(LeadDownload.user_id == user_id)
            .filter(LeadDownload.downloaded_at >= today_start)
            .scalar()
        ) or 0

    @staticmethod
    def _lock_user_download_row(db: Session, user_id: int) -> None:
        lock_query = select(User.id).where(User.id == user_id)
        bind = db.get_bind()
        dialect_name = bind.dialect.name if bind is not None else ""

        if dialect_name == "mysql":
            lock_query = lock_query.with_for_update()

        locked_user_id = db.execute(lock_query).scalar_one_or_none()
        if locked_user_id is None:
            raise HTTPException(status_code=404, detail="User not found")

    @staticmethod
    def _record_download_batch(
        db: Session,
        user_id: int,
        leads: List[Lead],
    ) -> None:
        if not leads:
            return

        batch_id = uuid4().hex
        for lead in leads:
            db.add(
                LeadDownload(
                    user_id=user_id,
                    lead_id=lead.id,
                    csv_batch_id=batch_id,
                )
            )
        # Flush inside the transaction so uniqueness errors are handled
        # before commit and can trigger a safe retry path.
        db.flush()

    @staticmethod
    def _allocate_download_batch_atomically(db: Session, user: User) -> List[Lead]:
        LeadService._lock_user_download_row(db, user.id)

        subscription = LeadService._require_active_subscription(db, user)
        plan = subscription.plan

        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        today_count = LeadService._get_today_download_count(db, user.id, today_start)

        daily_limit = plan.daily_download_limit
        if LeadService._is_unlimited_daily_limit(daily_limit):
            export_size = DEFAULT_DOWNLOAD_SIZE
        else:
            if daily_limit is None:
                raise HTTPException(status_code=500, detail="Invalid plan daily limit")
            remaining = daily_limit - today_count
            if remaining <= 0:
                raise HTTPException(status_code=403, detail="Daily limit reached")
            export_size = min(DEFAULT_DOWNLOAD_SIZE, remaining)

        states = LeadService._get_user_allowed_states(db, user.id, plan.state_limit)
        if not states:
            return []

        leads = LeadService._get_exportable_leads_for_states(
            db=db,
            user_id=user.id,
            states=states,
            size=export_size,
        )
        LeadService._record_download_batch(db=db, user_id=user.id, leads=leads)
        return leads

    @staticmethod
    def _is_duplicate_download_integrity_error(exc: IntegrityError) -> bool:
        error_text = str(getattr(exc, "orig", exc)).lower()
        if "lead_downloads" not in error_text and "uq_lead_downloads_user_lead" not in error_text:
            return False
        duplicate_markers = (
            "uq_lead_downloads_user_lead",
            "duplicate entry",
            "unique constraint",
        )
        return any(marker in error_text for marker in duplicate_markers)


    @staticmethod
    def get_available_leads_for_user(
        db: Session,
        user: User,
        page: int = 1,
        size: int = 20,
        delivery_status: Literal["all", "available", "delivered"] = "all",
        outcome_status: Literal["all", "new", "contacted", "appointment_set"] = "all",
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

        if outcome_status != "all":
            query = query.outerjoin(
                LeadOutcome,
                and_(
                    LeadOutcome.lead_id == Lead.id,
                    LeadOutcome.user_id == user.id,
                ),
            )
            if outcome_status == "new":
                query = query.filter(
                    or_(
                        LeadOutcome.id.is_(None),
                        LeadOutcome.status == "new",
                    )
                )
            else:
                query = query.filter(LeadOutcome.status == outcome_status)

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
        
        if not subscription.current_period_end or subscription.current_period_end <= now:
            return {"can_download": False, "reason": "Subscription expired", "remaining": 0}

        plan = subscription.plan
        daily_limit = plan.daily_download_limit

        if LeadService._is_unlimited_daily_limit(daily_limit):
            return {"can_download": True, "remaining": -1}

        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        today_count = LeadService._get_today_download_count(db, user.id, today_start)

        if today_count >= daily_limit:
            return {"can_download": False, "reason": "Daily limit reached", "remaining": 0}

        return {"can_download": True, "remaining": daily_limit - today_count}

    @staticmethod
    def download_leads_csv(db: Session, user: User) -> str:
        prepend_msg = ""
        max_attempts = 2

        for attempt in range(1, max_attempts + 1):
            try:
                leads = LeadService._allocate_download_batch_atomically(db=db, user=user)
                db.commit()
                return generate_leads_csv_stream(leads, prepend_message=prepend_msg)
            except HTTPException:
                db.rollback()
                raise
            except IntegrityError as exc:
                db.rollback()
                if LeadService._is_duplicate_download_integrity_error(exc) and attempt < max_attempts:
                    logger.warning(
                        "Retrying lead download allocation after unique conflict for user_id=%s (attempt %s/%s)",
                        user.id,
                        attempt,
                        max_attempts,
                    )
                    continue
                logger.error("Failed to record lead downloads due integrity error for user_id=%s: %s", user.id, exc)
                raise HTTPException(status_code=500, detail="Failed to record lead downloads")
            except Exception as exc:
                db.rollback()
                logger.error("Failed to record lead downloads for user_id=%s: %s", user.id, exc)
                raise HTTPException(status_code=500, detail="Failed to record lead downloads")

        raise HTTPException(status_code=500, detail="Failed to record lead downloads")

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
        appointments_set_7_days = 0
        if states:
            leads_delivered_7_days = (
                db.query(func.count(func.distinct(LeadDownload.lead_id)))
                .join(Lead, Lead.id == LeadDownload.lead_id)
                .filter(LeadDownload.user_id == user.id)
                .filter(Lead.state_code.in_(states))
                .filter(LeadDownload.downloaded_at >= seven_days_ago)
                .scalar()
            ) or 0

            appointments_set_7_days = (
                db.query(func.count(LeadOutcome.id))
                .join(Lead, Lead.id == LeadOutcome.lead_id)
                .filter(
                    LeadOutcome.user_id == user.id,
                    Lead.state_code.in_(states),
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
