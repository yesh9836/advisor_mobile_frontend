import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Literal, Optional, Tuple
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.lead import Lead, LeadDownload, LeadOutcome, LeadOwnership
from app.models.license import License
from app.models.purchase import LeadCreditLedger, LeadPackage, LeadPurchase
from app.models.user import User
from app.schemas.lead import LeadCreate, LeadOutcomeUpdateRequest
from app.services.audit_service import AuditService
from app.services.metrics_service import MetricsService
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
    def _get_user_purchase_state_limit(db: Session, user_id: int) -> Optional[int]:
        rows = (
            db.query(LeadPackage.state_limit)
            .select_from(LeadPurchase)
            .join(LeadPackage, LeadPackage.id == LeadPurchase.package_id)
            .filter(
                LeadPurchase.user_id == user_id,
                LeadPurchase.status == "completed",
            )
            .all()
        )
        if not rows:
            return None

        state_limits = [row[0] for row in rows]
        if any(limit is None for limit in state_limits):
            return None

        return max(int(limit) for limit in state_limits if limit is not None)

    @staticmethod
    def _get_user_allowed_states_for_new_leads(db: Session, user_id: int) -> List[str]:
        purchase_state_limit = LeadService._get_user_purchase_state_limit(db, user_id)
        return LeadService._get_user_allowed_states(
            db=db,
            user_id=user_id,
            state_limit=purchase_state_limit,
        )

    @staticmethod
    def _get_user_remaining_credits(db: Session, user_id: int) -> int:
        remaining = (
            db.query(func.coalesce(func.sum(LeadPurchase.credits_remaining), 0))
            .filter(
                LeadPurchase.user_id == user_id,
                LeadPurchase.status == "completed",
                LeadPurchase.credits_remaining > 0,
            )
            .scalar()
        )
        return int(remaining or 0)

    @staticmethod
    def _record_credit_denial_metrics(
        *,
        reason: str,
        remaining_credits: int,
    ) -> None:
        MetricsService.increment(
            "lead_download_credit_denied_total",
            tags={"reason": reason},
        )
        MetricsService.histogram(
            "lead_download_credit_denied_remaining_credits",
            float(max(int(remaining_credits), 0)),
            tags={"reason": reason},
        )
    
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
    def _user_has_owned_leads(db: Session, user_id: int) -> bool:
        return (
            db.query(LeadOwnership.id)
            .filter(LeadOwnership.user_id == user_id)
            .first()
            is not None
        )

    @staticmethod
    def _get_owned_leads_for_user(db: Session, user_id: int) -> List[Lead]:
        rows = (
            db.query(LeadOwnership, Lead)
            .join(Lead, Lead.id == LeadOwnership.lead_id)
            .filter(LeadOwnership.user_id == user_id)
            .order_by(LeadOwnership.assigned_at.desc(), LeadOwnership.id.desc())
            .all()
        )
        return [lead for _ownership, lead in rows]

    @staticmethod
    def allocate_unsold_leads_for_purchase(
        db: Session,
        purchase: LeadPurchase,
    ) -> Dict[str, object]:
        requested_count = max(int(purchase.credits_total or 0), 0)
        if purchase.status != "completed" or requested_count <= 0:
            return {
                "requested_count": requested_count,
                "assigned_count": 0,
                "unfulfilled_count": 0,
                "assigned_lead_ids": [],
            }

        existing_assignments = (
            db.query(LeadOwnership)
            .filter(LeadOwnership.purchase_id == purchase.id)
            .order_by(LeadOwnership.id.asc())
            .all()
        )
        assigned_lead_ids = [int(row.lead_id) for row in existing_assignments]
        if len(assigned_lead_ids) >= requested_count:
            return {
                "requested_count": requested_count,
                "assigned_count": len(assigned_lead_ids),
                "unfulfilled_count": 0,
                "assigned_lead_ids": assigned_lead_ids,
            }

        states = LeadService._get_user_allowed_states_for_new_leads(db, purchase.user_id)
        if not states:
            return {
                "requested_count": requested_count,
                "assigned_count": len(assigned_lead_ids),
                "unfulfilled_count": max(requested_count - len(assigned_lead_ids), 0),
                "assigned_lead_ids": assigned_lead_ids,
            }

        needed = requested_count - len(assigned_lead_ids)
        candidate_query = (
            db.query(Lead)
            .filter(Lead.state_code.in_(states))
            .filter(~Lead.id.in_(select(LeadOwnership.lead_id)))
            .order_by(Lead.created_at.desc(), Lead.id.desc())
        )
        bind = db.get_bind()
        dialect_name = bind.dialect.name if bind is not None else ""
        if dialect_name == "mysql":
            candidate_query = candidate_query.with_for_update(skip_locked=True)

        newly_assigned_leads = candidate_query.limit(needed).all()
        for lead in newly_assigned_leads:
            db.add(
                LeadOwnership(
                    user_id=purchase.user_id,
                    lead_id=lead.id,
                    purchase_id=purchase.id,
                )
            )
            assigned_lead_ids.append(int(lead.id))

        if newly_assigned_leads:
            db.flush()

        assigned_count = len(assigned_lead_ids)
        return {
            "requested_count": requested_count,
            "assigned_count": assigned_count,
            "unfulfilled_count": max(requested_count - assigned_count, 0),
            "assigned_lead_ids": assigned_lead_ids,
        }

    @staticmethod
    def _get_exportable_leads_for_user(
        db: Session,
        user: User,
        size: int = DEFAULT_DOWNLOAD_SIZE,
    ) -> List[Lead]:
        states = LeadService._get_user_allowed_states_for_new_leads(db, user.id)
        if not states:
            return []

        return LeadService._get_exportable_leads_for_states(
            db=db,
            user_id=user.id,
            states=states,
            size=size,
            lock_rows=False,
        )

    @staticmethod
    def _get_exportable_leads_for_states(
        db: Session,
        user_id: int,
        states: List[str],
        size: int,
        lock_rows: bool = False,
    ) -> List[Lead]:
        user_downloaded_subquery = select(LeadDownload.lead_id).where(LeadDownload.user_id == user_id)

        query = (
            db.query(Lead)
            .filter(Lead.state_code.in_(states))
            .filter(~Lead.id.in_(user_downloaded_subquery))
            .filter(~Lead.id.in_(select(LeadDownload.lead_id)))
            .filter(~Lead.id.in_(select(LeadOwnership.lead_id)))
            .order_by(Lead.created_at.desc())
        )

        if lock_rows:
            bind = db.get_bind()
            dialect_name = bind.dialect.name if bind is not None else ""
            if dialect_name == "mysql":
                query = query.with_for_update(skip_locked=True)

        return query.limit(size).all()

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
        purchase_ids_by_lead_id: Optional[Dict[int, int]] = None,
    ) -> None:
        if not leads:
            return

        batch_id = uuid4().hex
        for lead in leads:
            purchase_id = None
            if purchase_ids_by_lead_id:
                purchase_id = purchase_ids_by_lead_id.get(lead.id)
            db.add(
                LeadDownload(
                    user_id=user_id,
                    lead_id=lead.id,
                    purchase_id=purchase_id,
                    csv_batch_id=batch_id,
                )
            )
        # Flush inside the transaction so uniqueness errors are handled
        # before commit and can trigger a safe retry path.
        db.flush()

    @staticmethod
    def _consume_credits_for_leads(
        db: Session,
        user_id: int,
        leads: List[Lead],
    ) -> Tuple[Dict[int, int], List[Dict[str, int]]]:
        if not leads:
            return {}, []

        bind = db.get_bind()
        dialect_name = bind.dialect.name if bind is not None else ""

        purchases_query = (
            db.query(LeadPurchase)
            .filter(
                LeadPurchase.user_id == user_id,
                LeadPurchase.status == "completed",
                LeadPurchase.credits_remaining > 0,
            )
            .order_by(LeadPurchase.purchased_at.asc(), LeadPurchase.id.asc())
        )
        if dialect_name == "mysql":
            purchases_query = purchases_query.with_for_update()

        purchases = purchases_query.all()
        if not purchases:
            LeadService._record_credit_denial_metrics(
                reason="no_remaining_credits",
                remaining_credits=0,
            )
            raise HTTPException(status_code=403, detail="No remaining lead credits")

        purchase_ids_by_lead_id: Dict[int, int] = {}
        consumed_events: List[Dict[str, int]] = []
        lead_index = 0
        for purchase in purchases:
            while purchase.credits_remaining > 0 and lead_index < len(leads):
                lead = leads[lead_index]
                purchase.credits_remaining -= 1
                purchase_ids_by_lead_id[lead.id] = purchase.id
                consumed_events.append(
                    {
                        "purchase_id": int(purchase.id),
                        "lead_id": int(lead.id),
                        "credits_delta": -1,
                    }
                )
                db.add(
                    LeadCreditLedger(
                        user_id=user_id,
                        purchase_id=purchase.id,
                        movement_type="lead_consumed",
                        credits_delta=-1,
                        note=f"Lead {lead.id} delivered",
                    )
                )
                lead_index += 1

            db.add(purchase)
            if lead_index >= len(leads):
                break

        if lead_index < len(leads):
            LeadService._record_credit_denial_metrics(
                reason="insufficient_credits",
                remaining_credits=0,
            )
            raise HTTPException(status_code=403, detail="No remaining lead credits")

        return purchase_ids_by_lead_id, consumed_events

    @staticmethod
    def _allocate_download_batch_atomically(db: Session, user: User) -> Tuple[List[Lead], List[Dict[str, int]]]:
        LeadService._lock_user_download_row(db, user.id)
        remaining_credits = LeadService._get_user_remaining_credits(db, user.id)
        if remaining_credits <= 0:
            LeadService._record_credit_denial_metrics(
                reason="no_remaining_credits",
                remaining_credits=remaining_credits,
            )
            raise HTTPException(status_code=403, detail="No remaining lead credits")
        export_size = min(DEFAULT_DOWNLOAD_SIZE, remaining_credits)

        states = LeadService._get_user_allowed_states_for_new_leads(db, user.id)
        if not states:
            return [], []

        leads = LeadService._get_exportable_leads_for_states(
            db=db,
            user_id=user.id,
            states=states,
            size=export_size,
            lock_rows=True,
        )
        if not leads:
            return [], []

        purchase_ids_by_lead_id, consumed_events = LeadService._consume_credits_for_leads(
            db=db,
            user_id=user.id,
            leads=leads,
        )

        LeadService._record_download_batch(
            db=db,
            user_id=user.id,
            leads=leads,
            purchase_ids_by_lead_id=purchase_ids_by_lead_id,
        )
        return leads, consumed_events

    @staticmethod
    def _is_duplicate_download_integrity_error(exc: IntegrityError) -> bool:
        error_text = str(getattr(exc, "orig", exc)).lower()
        if (
            "lead_downloads" not in error_text
            and "uq_lead_downloads_user_lead" not in error_text
            and "uq_lead_downloads_global_lead" not in error_text
        ):
            return False
        duplicate_markers = (
            "uq_lead_downloads_user_lead",
            "uq_lead_downloads_global_lead",
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
        search: Optional[str] = None,
    ) -> Dict[str, object]:
        downloaded_subquery = select(LeadDownload.lead_id).where(LeadDownload.user_id == user.id)
        query = db.query(Lead)
        has_owned_leads = LeadService._user_has_owned_leads(db, user.id)
        if has_owned_leads:
            owned_subquery = select(LeadOwnership.lead_id).where(LeadOwnership.user_id == user.id)
            query = query.filter(Lead.id.in_(owned_subquery))
            available_condition = ~Lead.id.in_(downloaded_subquery)
            delivered_condition = Lead.id.in_(downloaded_subquery)
        else:
            states = LeadService._get_user_allowed_states_for_new_leads(db, user.id)
            available_condition = and_(
                Lead.state_code.in_(states),
                ~Lead.id.in_(downloaded_subquery),
                ~Lead.id.in_(select(LeadDownload.lead_id)),
                ~Lead.id.in_(select(LeadOwnership.lead_id)),
            )
            delivered_condition = Lead.id.in_(downloaded_subquery)

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

        normalized_search = (search or "").strip()
        if normalized_search:
            search_pattern = f"%{normalized_search}%"
            query = query.filter(
                or_(
                    Lead.first_name.ilike(search_pattern),
                    Lead.last_name.ilike(search_pattern),
                    Lead.mobile_phone.ilike(search_pattern),
                    Lead.state_code.ilike(search_pattern),
                    Lead.source.ilike(search_pattern),
                )
            )

        if delivery_status == "available":
            query = query.filter(available_condition)
        elif delivery_status == "delivered":
            query = query.filter(delivered_condition)
        else:
            if not has_owned_leads:
                query = query.filter(
                    or_(
                        delivered_condition,
                        available_condition,
                    )
                )

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
        if LeadService._user_has_owned_leads(db, user.id):
            owned_count = (
                db.query(func.count(LeadOwnership.id))
                .filter(LeadOwnership.user_id == user.id)
                .scalar()
            ) or 0
            if owned_count <= 0:
                return {"can_download": False, "reason": "No leads available", "remaining": 0}
            return {"can_download": True, "remaining": int(owned_count)}

        remaining_credits = LeadService._get_user_remaining_credits(db, user.id)
        if remaining_credits <= 0:
            LeadService._record_credit_denial_metrics(
                reason="no_remaining_credits",
                remaining_credits=0,
            )
            return {"can_download": False, "reason": "No remaining lead credits", "remaining": 0}

        states = LeadService._get_user_allowed_states_for_new_leads(db, user.id)
        if not states:
            return {"can_download": False, "reason": "No verified license states", "remaining": remaining_credits}

        available_count = (
            db.query(func.count(Lead.id))
            .filter(Lead.state_code.in_(states))
            .filter(~Lead.id.in_(select(LeadDownload.lead_id)))
            .filter(~Lead.id.in_(select(LeadOwnership.lead_id)))
            .scalar()
        ) or 0
        if available_count <= 0:
            return {"can_download": False, "reason": "No leads available", "remaining": remaining_credits}

        return {"can_download": True, "remaining": remaining_credits}

    @staticmethod
    def download_leads_csv(db: Session, user: User) -> str:
        owned_leads = LeadService._get_owned_leads_for_user(db=db, user_id=user.id)
        if owned_leads:
            lead_ids = [lead.id for lead in owned_leads]
            existing_download_ids = {
                row[0]
                for row in (
                    db.query(LeadDownload.lead_id)
                    .filter(
                        LeadDownload.user_id == user.id,
                        LeadDownload.lead_id.in_(lead_ids),
                    )
                    .all()
                )
            }
            ownership_rows = (
                db.query(LeadOwnership)
                .filter(
                    LeadOwnership.user_id == user.id,
                    LeadOwnership.lead_id.in_(lead_ids),
                )
                .all()
            )
            purchase_ids_by_lead_id = {
                int(ownership.lead_id): int(ownership.purchase_id)
                for ownership in ownership_rows
                if ownership.purchase_id is not None
            }
            leads_to_mark_delivered = [
                lead for lead in owned_leads if lead.id not in existing_download_ids
            ]
            if leads_to_mark_delivered:
                try:
                    LeadService._record_download_batch(
                        db=db,
                        user_id=user.id,
                        leads=leads_to_mark_delivered,
                        purchase_ids_by_lead_id=purchase_ids_by_lead_id,
                    )
                    db.commit()
                except Exception as exc:
                    db.rollback()
                    logger.error("Failed to record owned lead download batch for user_id=%s: %s", user.id, exc)
                    raise HTTPException(status_code=500, detail="Failed to record lead downloads")
            return generate_leads_csv_stream(owned_leads)

        prepend_msg = ""
        max_attempts = 2

        for attempt in range(1, max_attempts + 1):
            try:
                leads, consumed_events = LeadService._allocate_download_batch_atomically(db=db, user=user)
                db.commit()
                for consumed in consumed_events:
                    purchase_id = consumed["purchase_id"]
                    lead_id = consumed["lead_id"]
                    credits_delta = consumed["credits_delta"]
                    AuditService.log_purchase_event(
                        actor_user_id=user.id,
                        action="purchase_credit_consumed",
                        purchase_id=purchase_id,
                        credits_delta=credits_delta,
                        correlation_ids={
                            "purchase_id": purchase_id,
                        },
                        meta_data={
                            "lead_id": lead_id,
                            "movement_type": "lead_consumed",
                        },
                    )
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
    def download_delivered_leads_csv(db: Session, user: User) -> str:
        delivered_leads = (
            db.query(Lead)
            .join(LeadDownload, LeadDownload.lead_id == Lead.id)
            .filter(LeadDownload.user_id == user.id)
            .order_by(LeadDownload.downloaded_at.desc(), LeadDownload.id.desc())
            .all()
        )
        if not delivered_leads:
            raise HTTPException(status_code=404, detail="No delivered leads found")
        return generate_leads_csv_stream(
            delivered_leads,
            prepend_message="Previously delivered leads export.",
        )

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
        states = LeadService._get_user_allowed_states_for_new_leads(db, user.id)
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")

        has_download_access = (
            db.query(LeadDownload.id)
            .filter(LeadDownload.user_id == user.id, LeadDownload.lead_id == lead_id)
            .first()
            is not None
        )
        has_ownership_access = (
            db.query(LeadOwnership.id)
            .filter(LeadOwnership.user_id == user.id, LeadOwnership.lead_id == lead_id)
            .first()
            is not None
        )
        has_state_access = lead.state_code in states
        if not has_download_access and not has_ownership_access and not has_state_access:
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
    def _calculate_cost_per_appointment(total_spend_cents: int, appointments_set: int) -> float:
        if appointments_set <= 0:
            return 0.0
        return round((total_spend_cents / 100.0) / appointments_set, 2)

    @staticmethod
    def get_dashboard_summary(db: Session, user: User) -> Dict[str, object]:
        now = datetime.now(timezone.utc)
        seven_days_ago = now - timedelta(days=7)
        states = LeadService._get_user_allowed_states_for_new_leads(db, user.id)

        leads_delivered_7_days = 0
        appointments_set_7_days = 0
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

        spend_cents_7_days = (
            db.query(func.coalesce(func.sum(LeadPurchase.amount_cents), 0))
            .filter(
                LeadPurchase.user_id == user.id,
                LeadPurchase.status == "completed",
                LeadPurchase.purchased_at >= seven_days_ago,
            )
            .scalar()
        ) or 0

        latest_completed_purchase = (
            db.query(LeadPurchase)
            .filter(
                LeadPurchase.user_id == user.id,
                LeadPurchase.status == "completed",
            )
            .order_by(LeadPurchase.purchased_at.desc(), LeadPurchase.id.desc())
            .first()
        )

        cost_per_appointment = LeadService._calculate_cost_per_appointment(
            total_spend_cents=int(spend_cents_7_days),
            appointments_set=appointments_set_7_days,
        )

        currency = (latest_completed_purchase.currency or "USD").upper() if latest_completed_purchase else "USD"

        return {
            "leads_delivered_7_days": int(leads_delivered_7_days),
            "appointments_set_7_days": int(appointments_set_7_days),
            "cost_per_appointment": cost_per_appointment,
            "currency": currency,
            "settings": {
                "email_alerts_enabled": True,
                "sms_alerts_enabled": False,
                "target_states": states,
                "min_assets": None,
                "daily_download_limit": None,
            },
        }
