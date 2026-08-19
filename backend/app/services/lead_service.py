import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Literal, Optional, Tuple
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import and_, false, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.lead import Lead, LeadDownload, LeadOutcome, LeadOwnership
from app.models.license import License
from app.models.purchase import LeadCreditLedger, LeadPackage, LeadPurchase
from app.models.user import User
from app.schemas.lead import LeadCreate, LeadOutcomeUpdateRequest, LeadResponse
from app.services.audit_service import AuditService
from app.services.delivery_settings_service import DeliverySettingsService
from app.services.metrics_service import MetricsService
from app.services.notification_service import NotificationService
from app.utils.csv_generator import LEAD_CSV_REQUIRED_VALUE_FIELDS, generate_leads_csv_stream
from app.utils.phone import normalize_phone_number
from app.utils.us_states import US_STATE_CODES

logger = logging.getLogger(__name__)

DEFAULT_DOWNLOAD_SIZE = 50
SEARCH_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+")


class LeadService:
    """Service for lead distribution and downloads."""

    _RECONCILIATION_MAX_ASSIGNMENTS_PER_ADVISOR_ROUND = 25
    _PRE_DELIVERY_REDACTED_FIELDS: Tuple[str, ...] = (
        "zip_code",
        "first_name",
        "last_name",
        "mobile_phone",
        "preferred_follow_up_method",
        "best_time_to_reach",
        "retirement_timeline",
        "confidence_in_long_term_plan",
        "most_important_retirement_activity",
        "planning_to_relocate_retirement",
        "expected_retirement_income_source",
        "overall_health",
        "money_management_style",
        "investor_profile_statement",
        "investment_comfort_level",
        "main_purpose_for_investing",
        "retirement_savings_range",
        "annual_household_income_range",
        "total_investable_assets_range",
        "monthly_savings_range",
        "wants_to_improve_strategy_timing",
        "current_investment_strategies",
        "has_financial_advisor",
        "advisor_local_preference",
        "owns_annuity",
        "additional_notes",
    )

    @staticmethod
    def _build_bulk_import_audit_metadata(
        *,
        scanned_count: int,
        success_count: int,
        failed_count: int,
        errors: Optional[List[Dict[str, object]]] = None,
    ) -> Dict[str, int]:
        error_items = errors if isinstance(errors, list) else []
        skipped_duplicates = sum(
            1
            for error in error_items
            if isinstance(error, dict)
            and "duplicate" in str(error.get("error", "")).lower()
        )
        return {
            "scanned": int(scanned_count),
            "inserted": int(success_count),
            "failed": int(failed_count),
            "skipped_duplicates": int(skipped_duplicates),
        }

    @staticmethod
    def _lead_not_downloaded_by_anyone_condition():
        return ~select(LeadDownload.id).where(LeadDownload.lead_id == Lead.id).exists()

    @staticmethod
    def _lead_not_owned_condition():
        return ~select(LeadOwnership.id).where(LeadOwnership.lead_id == Lead.id).exists()

    @staticmethod
    def _lead_not_delivered_condition():
        return and_(
            LeadService._lead_not_downloaded_by_anyone_condition(),
            LeadService._lead_not_owned_condition(),
        )

    @staticmethod
    def _lead_not_downloaded_by_user_condition(user_id: int):
        return ~select(LeadDownload.id).where(
            LeadDownload.user_id == user_id,
            LeadDownload.lead_id == Lead.id,
        ).exists()

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
    def get_unsold_inventory_snapshot_for_user(db: Session, user: User) -> Dict[str, object]:
        """
        Return advisor-scoped unsold inventory snapshot.

        This excludes already delivered/downloaded leads and ownership-assigned leads.
        """
        states = LeadService._get_user_allowed_states_for_new_leads(db, int(user.id))
        if not states:
            return {
                "state_codes": [],
                "available_count": 0,
            }

        available_count = (
            db.query(func.count(Lead.id))
            .filter(Lead.state_code.in_(states))
            .filter(LeadService._lead_not_delivered_condition())
            .scalar()
        ) or 0
        return {
            "state_codes": states,
            "available_count": int(available_count),
        }

    @staticmethod
    def get_global_unsold_inventory_count(db: Session) -> int:
        count = (
            db.query(func.count(Lead.id))
            .filter(LeadService._lead_not_delivered_condition())
            .scalar()
        ) or 0
        return int(count)

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
    def _can_user_view_unsold_inventory(
        db: Session,
        user_id: int,
        states: Optional[List[str]] = None,
    ) -> bool:
        if LeadService._get_user_remaining_credits(db, user_id) <= 0:
            return False
        scoped_states = states if states is not None else LeadService._get_user_allowed_states_for_new_leads(db, user_id)
        return bool(scoped_states)

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
    def _attach_received_timestamps_to_leads(db: Session, user_id: int, leads: List[Lead]) -> None:
        if not leads:
            return

        lead_ids = [lead.id for lead in leads]
        ownerships = (
            db.query(LeadOwnership)
            .filter(LeadOwnership.user_id == user_id, LeadOwnership.lead_id.in_(lead_ids))
            .all()
        )
        assigned_at_by_lead_id = {
            int(ownership.lead_id): ownership.assigned_at
            for ownership in ownerships
            if ownership.assigned_at is not None
        }

        for lead in leads:
            received_at = assigned_at_by_lead_id.get(int(lead.id))
            if received_at is None:
                received_at = getattr(lead, "downloaded_at", None)
            setattr(lead, "received_at", received_at)

    @staticmethod
    def _latest_downloaded_at_subquery(user_id: int):
        return (
            select(func.max(LeadDownload.downloaded_at))
            .where(
                LeadDownload.user_id == user_id,
                LeadDownload.lead_id == Lead.id,
            )
            .scalar_subquery()
        )

    @staticmethod
    def _ownership_assigned_at_subquery(user_id: int):
        return (
            select(LeadOwnership.assigned_at)
            .where(
                LeadOwnership.user_id == user_id,
                LeadOwnership.lead_id == Lead.id,
            )
            .limit(1)
            .scalar_subquery()
        )

    @staticmethod
    def _user_has_outcome_write_access(db: Session, user_id: int, lead_id: int) -> bool:
        has_download_access = (
            db.query(LeadDownload.id)
            .filter(LeadDownload.user_id == user_id, LeadDownload.lead_id == lead_id)
            .first()
            is not None
        )
        if has_download_access:
            return True

        has_ownership_access = (
            db.query(LeadOwnership.id)
            .filter(LeadOwnership.user_id == user_id, LeadOwnership.lead_id == lead_id)
            .first()
            is not None
        )
        return has_ownership_access

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
            .order_by(LeadOwnership.assigned_at.desc(), Lead.id.desc())
            .all()
        )
        return [lead for _ownership, lead in rows]

    @staticmethod
    def _get_delivered_leads_for_user(db: Session, user_id: int) -> List[Lead]:
        latest_downloads = (
            db.query(
                LeadDownload.lead_id.label("lead_id"),
                LeadDownload.downloaded_at.label("downloaded_at"),
                LeadDownload.id.label("download_id"),
                func.row_number().over(
                    partition_by=LeadDownload.lead_id,
                    order_by=(LeadDownload.downloaded_at.desc(), LeadDownload.id.desc()),
                ).label("row_rank"),
            )
            .filter(LeadDownload.user_id == user_id)
            .subquery()
        )
        ownership_alias = (
            db.query(
                LeadOwnership.lead_id.label("lead_id"),
                LeadOwnership.assigned_at.label("assigned_at"),
                LeadOwnership.id.label("ownership_id"),
            )
            .filter(LeadOwnership.user_id == user_id)
            .subquery()
        )
        return (
            db.query(Lead)
            .join(latest_downloads, latest_downloads.c.lead_id == Lead.id)
            .outerjoin(ownership_alias, ownership_alias.c.lead_id == Lead.id)
            .filter(latest_downloads.c.row_rank == 1)
            .order_by(
                func.coalesce(
                    ownership_alias.c.assigned_at,
                    latest_downloads.c.downloaded_at,
                    Lead.created_at,
                ).desc(),
                latest_downloads.c.download_id.desc(),
                Lead.id.desc(),
            )
            .all()
        )

    def _normalize_state_codes(state_codes: Optional[List[str]]) -> List[str]:
        if not state_codes:
            return []
        normalized = {
            str(state_code).strip().upper()
            for state_code in state_codes
            if str(state_code).strip()
        }
        return sorted(code for code in normalized if len(code) == 2)

    @staticmethod
    def _tokenize_search_query(search: str) -> List[str]:
        tokens = [token.strip() for token in SEARCH_TOKEN_PATTERN.findall(search or "")]
        return [token for token in tokens if token]

    @staticmethod
    def _build_non_pii_search_token_filter(token: str):
        prefix_pattern = f"{token}%"
        token_filters = [
            Lead.source.ilike(prefix_pattern),
        ]

        if len(token) == 2 and token.isalpha():
            token_filters.append(Lead.state_code == token.upper())
        else:
            token_filters.append(Lead.state_code.ilike(prefix_pattern))

        return or_(*token_filters)

    @staticmethod
    def _build_pii_search_token_filter(token: str):
        prefix_pattern = f"{token}%"
        token_filters = [
            Lead.first_name.ilike(prefix_pattern),
            Lead.last_name.ilike(prefix_pattern),
        ]
        if any(character.isdigit() for character in token):
            token_filters.append(Lead.mobile_phone.ilike(f"%{token}%"))

        return or_(*token_filters)

    @staticmethod
    def _attach_pii_unlock_flags(db: Session, user_id: int, leads: List[Lead]) -> None:
        if not leads:
            return

        lead_ids = [lead.id for lead in leads]
        owned_rows = (
            db.query(LeadOwnership.lead_id)
            .filter(LeadOwnership.user_id == user_id, LeadOwnership.lead_id.in_(lead_ids))
            .all()
        )
        owned_lead_ids = {int(row[0]) for row in owned_rows}

        for lead in leads:
            is_downloaded = bool(getattr(lead, "is_downloaded", False))
            setattr(lead, "pii_unlocked", is_downloaded or lead.id in owned_lead_ids)

    @staticmethod
    def to_advisor_lead_list_item_payload(lead: Lead) -> Dict[str, object]:
        payload = LeadResponse.model_validate(lead).model_dump(mode="python")
        payload["received_at"] = getattr(lead, "received_at", None)
        pii_unlocked = bool(getattr(lead, "pii_unlocked", False))
        payload["pii_unlocked"] = pii_unlocked
        if pii_unlocked:
            return payload

        for field_name in LeadService._PRE_DELIVERY_REDACTED_FIELDS:
            payload[field_name] = None
        return payload

    @staticmethod
    def _compute_purchase_assignment_target(
        *,
        purchase: LeadPurchase,
    ) -> int:
        return max(int(purchase.credits_total or 0), 0)

    @staticmethod
    def _get_purchase_assignment_target(
        db: Session,
        purchase: LeadPurchase,
    ) -> int:
        _ = db
        return LeadService._compute_purchase_assignment_target(purchase=purchase)

    @staticmethod
    def allocate_unsold_leads_for_purchase(
        db: Session,
        purchase: LeadPurchase,
        *,
        max_assignments: Optional[int] = None,
        assignment_target: Optional[int] = None,
    ) -> Dict[str, object]:
        bind = db.get_bind()
        dialect_name = bind.dialect.name if bind is not None else ""
        if purchase.id is not None and dialect_name == "mysql":
            locked_purchase = (
                db.query(LeadPurchase)
                .filter(LeadPurchase.id == purchase.id)
                .with_for_update()
                .first()
            )
            if locked_purchase is not None:
                purchase = locked_purchase

        if assignment_target is None:
            requested_count = LeadService._get_purchase_assignment_target(db=db, purchase=purchase)
        else:
            requested_count = max(int(assignment_target), 0)
        if purchase.status != "completed" or requested_count <= 0:
            return {
                "requested_count": requested_count,
                "assigned_count": 0,
                "unfulfilled_count": 0,
                "newly_assigned_count": 0,
                "newly_assigned_lead_ids": [],
                "assigned_lead_ids": [],
            }

        existing_assignments = (
            db.query(LeadOwnership)
            .filter(LeadOwnership.purchase_id == purchase.id)
            .order_by(LeadOwnership.id.asc())
            .all()
        )
        assigned_lead_ids = [int(row.lead_id) for row in existing_assignments]
        existing_assigned_count = len(assigned_lead_ids)
        if len(assigned_lead_ids) >= requested_count:
            return {
                "requested_count": requested_count,
                "assigned_count": len(assigned_lead_ids),
                "unfulfilled_count": 0,
                "newly_assigned_count": 0,
                "newly_assigned_lead_ids": [],
                "assigned_lead_ids": assigned_lead_ids,
            }

        if purchase.target_states:
            verified_states = set(
                LeadService._get_user_allowed_states(
                    db=db,
                    user_id=purchase.user_id,
                    state_limit=None,
                )
            )
            states = [
                str(state).upper()
                for state in purchase.target_states
                if str(state).upper() in verified_states
            ]
        else:
            states = LeadService._get_user_allowed_states_for_new_leads(
                db,
                purchase.user_id,
            )
        if not states:
            return {
                "requested_count": requested_count,
                "assigned_count": len(assigned_lead_ids),
                "unfulfilled_count": max(requested_count - len(assigned_lead_ids), 0),
                "newly_assigned_count": 0,
                "newly_assigned_lead_ids": [],
                "assigned_lead_ids": assigned_lead_ids,
            }

        needed = requested_count - len(assigned_lead_ids)
        needed = min(needed, max(int(purchase.credits_remaining or 0), 0))
        if max_assignments is not None:
            needed = min(needed, max(int(max_assignments), 0))
        if needed <= 0:
            assigned_count = len(assigned_lead_ids)
            return {
                "requested_count": requested_count,
                "assigned_count": assigned_count,
                "unfulfilled_count": max(requested_count - assigned_count, 0),
                "newly_assigned_count": 0,
                "newly_assigned_lead_ids": [],
                "assigned_lead_ids": assigned_lead_ids,
            }

        candidate_query = (
            db.query(Lead)
            .filter(Lead.state_code.in_(states))
            .filter(LeadService._lead_not_delivered_condition())
            .order_by(Lead.created_at.desc(), Lead.id.desc())
        )
        if dialect_name == "mysql":
            candidate_query = candidate_query.with_for_update(skip_locked=True)

        newly_assigned_leads = candidate_query.limit(needed).all()
        newly_assigned_lead_ids: List[int] = []
        for lead in newly_assigned_leads:
            db.add(
                LeadOwnership(
                    user_id=purchase.user_id,
                    lead_id=lead.id,
                    purchase_id=purchase.id,
                )
            )
            assigned_lead_ids.append(int(lead.id))
            newly_assigned_lead_ids.append(int(lead.id))

        consumed_credits = min(
            len(newly_assigned_lead_ids),
            max(int(purchase.credits_remaining or 0), 0),
        )
        if consumed_credits > 0:
            for lead_id in newly_assigned_lead_ids[:consumed_credits]:
                db.add(
                    LeadCreditLedger(
                        user_id=purchase.user_id,
                        purchase_id=purchase.id,
                        movement_type="lead_consumed",
                        credits_delta=-1,
                        note=f"Lead {lead_id} assigned",
                    )
                )
            purchase.credits_remaining = max(int(purchase.credits_remaining or 0) - consumed_credits, 0)
            db.add(purchase)

        if newly_assigned_leads:
            db.flush()

        assigned_count = len(assigned_lead_ids)
        return {
            "requested_count": requested_count,
            "assigned_count": assigned_count,
            "unfulfilled_count": max(requested_count - assigned_count, 0),
            "newly_assigned_count": max(assigned_count - existing_assigned_count, 0),
            "newly_assigned_lead_ids": newly_assigned_lead_ids,
            "assigned_lead_ids": assigned_lead_ids,
        }

    @staticmethod
    def _query_unfulfilled_completed_purchases(
        db: Session,
        *,
        state_codes: Optional[List[str]] = None,
        max_purchases: int = 500,
    ) -> List[LeadPurchase]:
        ownership_counts = (
            db.query(
                LeadOwnership.purchase_id.label("purchase_id"),
                func.count(LeadOwnership.id).label("assigned_count"),
            )
            .filter(LeadOwnership.purchase_id.isnot(None))
            .group_by(LeadOwnership.purchase_id)
            .subquery()
        )
        query = (
            db.query(LeadPurchase)
            .join(User, User.id == LeadPurchase.user_id)
            .outerjoin(ownership_counts, ownership_counts.c.purchase_id == LeadPurchase.id)
            .filter(LeadPurchase.status == "completed")
            .filter(LeadPurchase.credits_remaining > 0)
            .filter(LeadPurchase.credits_total > 0)
            .filter(func.coalesce(ownership_counts.c.assigned_count, 0) < LeadPurchase.credits_total)
            .order_by(
                User.created_at.asc(),
                User.id.asc(),
                LeadPurchase.purchased_at.asc(),
                LeadPurchase.id.asc(),
            )
        )

        normalized_states = LeadService._normalize_state_codes(state_codes)
        if normalized_states:
            query = query.filter(
                db.query(License.id)
                .filter(
                    License.user_id == LeadPurchase.user_id,
                    License.verification_status == "verified",
                    func.upper(License.state).in_(normalized_states),
                )
                .exists()
            )

        sanitized_limit = max(1, int(max_purchases))
        return query.limit(sanitized_limit).all()

    @staticmethod
    def _advance_purchase_queue_index(
        purchase_queue: List[int],
        queue_index: int,
        purchase_unfulfilled: Dict[int, int],
    ) -> int:
        cursor = max(int(queue_index), 0)
        while (
            cursor < len(purchase_queue)
            and max(int(purchase_unfulfilled.get(purchase_queue[cursor], 0) or 0), 0) <= 0
        ):
            cursor += 1
        return cursor

    @staticmethod
    def _allocate_unsold_leads_for_advisor_round(
        db: Session,
        *,
        advisor_id: int,
        advisor_states: List[str],
        purchase_queue: List[int],
        queue_index: int,
        purchase_by_id: Dict[int, LeadPurchase],
        purchase_unfulfilled: Dict[int, int],
        max_assignments: int,
        dialect_name: str,
    ) -> Dict[str, object]:
        next_queue_index = LeadService._advance_purchase_queue_index(
            purchase_queue,
            queue_index,
            purchase_unfulfilled,
        )
        if next_queue_index >= len(purchase_queue) or max(int(max_assignments), 0) <= 0:
            return {
                "next_queue_index": next_queue_index,
                "assigned_count": 0,
                "per_purchase_assigned_ids": {},
            }

        normalized_states = [state for state in advisor_states if state]
        if not normalized_states:
            return {
                "next_queue_index": next_queue_index,
                "assigned_count": 0,
                "per_purchase_assigned_ids": {},
            }

        purchase_batch_plan: List[Tuple[int, int]] = []
        remaining_capacity = max(int(max_assignments), 0)
        purchase_cursor = next_queue_index
        while purchase_cursor < len(purchase_queue) and remaining_capacity > 0:
            purchase_id = purchase_queue[purchase_cursor]
            unfulfilled_count = max(int(purchase_unfulfilled.get(purchase_id, 0) or 0), 0)
            if unfulfilled_count <= 0:
                purchase_cursor += 1
                continue
            purchase = purchase_by_id[purchase_id]
            available_credit_capacity = max(int(purchase.credits_remaining or 0), 0)
            assignable_for_purchase = min(unfulfilled_count, available_credit_capacity)
            if assignable_for_purchase <= 0:
                purchase_cursor += 1
                continue
            assigned_for_purchase = min(assignable_for_purchase, remaining_capacity)
            purchase_batch_plan.append((purchase_id, assigned_for_purchase))
            remaining_capacity -= assigned_for_purchase
            purchase_cursor += 1

        total_requested = sum(assigned_count for _purchase_id, assigned_count in purchase_batch_plan)
        if total_requested <= 0:
            return {
                "next_queue_index": next_queue_index,
                "assigned_count": 0,
                "per_purchase_assigned_ids": {},
            }

        candidate_query = (
            db.query(Lead)
            .filter(Lead.state_code.in_(normalized_states))
            .filter(LeadService._lead_not_delivered_condition())
            .order_by(Lead.created_at.desc(), Lead.id.desc())
        )
        if dialect_name == "mysql":
            candidate_query = candidate_query.with_for_update(skip_locked=True)

        candidate_rows = candidate_query.limit(total_requested).all()
        if not candidate_rows:
            return {
                "next_queue_index": next_queue_index,
                "assigned_count": 0,
                "per_purchase_assigned_ids": {},
            }

        per_purchase_assigned_ids: Dict[int, List[int]] = {}
        planned_purchase_index = 0
        planned_remaining = purchase_batch_plan[planned_purchase_index][1]
        for lead in candidate_rows:
            while planned_purchase_index < len(purchase_batch_plan) and planned_remaining <= 0:
                planned_purchase_index += 1
                if planned_purchase_index < len(purchase_batch_plan):
                    planned_remaining = purchase_batch_plan[planned_purchase_index][1]
            if planned_purchase_index >= len(purchase_batch_plan):
                break

            purchase_id = purchase_batch_plan[planned_purchase_index][0]
            db.add(
                LeadOwnership(
                    user_id=advisor_id,
                    lead_id=lead.id,
                    purchase_id=purchase_id,
                )
            )
            per_purchase_assigned_ids.setdefault(purchase_id, []).append(int(lead.id))
            planned_remaining -= 1

        assigned_count = sum(len(lead_ids) for lead_ids in per_purchase_assigned_ids.values())
        if assigned_count <= 0:
            return {
                "next_queue_index": next_queue_index,
                "assigned_count": 0,
                "per_purchase_assigned_ids": {},
            }

        for purchase_id, lead_ids in per_purchase_assigned_ids.items():
            assigned_for_purchase = len(lead_ids)
            purchase_unfulfilled[purchase_id] = max(
                int(purchase_unfulfilled.get(purchase_id, 0) or 0) - assigned_for_purchase,
                0,
            )

            purchase = purchase_by_id[purchase_id]
            consumed_credits = min(
                assigned_for_purchase,
                max(int(purchase.credits_remaining or 0), 0),
            )
            if consumed_credits > 0:
                for lead_id in lead_ids[:consumed_credits]:
                    db.add(
                        LeadCreditLedger(
                            user_id=purchase.user_id,
                            purchase_id=purchase.id,
                            movement_type="lead_consumed",
                            credits_delta=-1,
                            note=f"Lead {lead_id} assigned",
                        )
                    )
                purchase.credits_remaining = max(
                    int(purchase.credits_remaining or 0) - consumed_credits,
                    0,
                )
                db.add(purchase)

        # Flush per advisor to make new ownership rows visible to subsequent candidate scans.
        db.flush()

        next_queue_index = LeadService._advance_purchase_queue_index(
            purchase_queue,
            next_queue_index,
            purchase_unfulfilled,
        )
        return {
            "next_queue_index": next_queue_index,
            "assigned_count": assigned_count,
            "per_purchase_assigned_ids": per_purchase_assigned_ids,
        }

    @staticmethod
    def reconcile_pending_purchase_assignments(
        db: Session,
        *,
        state_codes: Optional[List[str]] = None,
        source_event: str = "inventory_ingest",
        max_purchases: int = 500,
    ) -> Dict[str, int]:
        purchases = LeadService._query_unfulfilled_completed_purchases(
            db=db,
            state_codes=state_codes,
            max_purchases=max_purchases,
        )
        if not purchases:
            return {
                "scanned_purchases": 0,
                "updated_purchases": 0,
                "newly_assigned_count": 0,
                "remaining_unfulfilled_count": 0,
            }

        purchase_ids = [int(purchase.id) for purchase in purchases if purchase.id is not None]
        purchase_by_id: Dict[int, LeadPurchase] = {
            int(purchase.id): purchase
            for purchase in purchases
            if purchase.id is not None
        }
        assigned_counts_by_purchase: Dict[int, int] = {}
        assignment_targets_by_purchase: Dict[int, int] = {}
        if purchase_ids:
            assigned_rows = (
                db.query(
                    LeadOwnership.purchase_id,
                    func.count(LeadOwnership.id),
                )
                .filter(LeadOwnership.purchase_id.in_(purchase_ids))
                .group_by(LeadOwnership.purchase_id)
                .all()
            )
            assigned_counts_by_purchase = {
                int(purchase_id): int(assigned_count)
                for purchase_id, assigned_count in assigned_rows
                if purchase_id is not None
            }
            assignment_targets_by_purchase = {
                purchase_id: LeadService._compute_purchase_assignment_target(
                    purchase=purchase_by_id[purchase_id],
                )
                for purchase_id in purchase_ids
            }

        purchase_unfulfilled: Dict[int, int] = {}
        advisor_order: List[int] = []
        advisor_purchase_queues: Dict[int, List[int]] = {}
        advisor_queue_index: Dict[int, int] = {}

        for purchase in purchases:
            if purchase.id is None:
                continue
            purchase_id = int(purchase.id)
            requested_count = assignment_targets_by_purchase.get(
                purchase_id,
                LeadService._compute_purchase_assignment_target(purchase=purchase),
            )
            assigned_count = assigned_counts_by_purchase.get(purchase_id, 0)
            unfulfilled_count = max(requested_count - assigned_count, 0)

            purchase_unfulfilled[purchase_id] = unfulfilled_count

            if unfulfilled_count <= 0:
                continue

            advisor_id = int(purchase.user_id)
            if advisor_id not in advisor_purchase_queues:
                advisor_purchase_queues[advisor_id] = []
                advisor_queue_index[advisor_id] = 0
                advisor_order.append(advisor_id)
            advisor_purchase_queues[advisor_id].append(purchase_id)

        bind = db.get_bind()
        dialect_name = bind.dialect.name if bind is not None else ""
        if purchase_ids and dialect_name == "mysql":
            # Keep purchase credit mutations serialized across concurrent reconciliation workers.
            db.query(LeadPurchase.id).filter(LeadPurchase.id.in_(purchase_ids)).with_for_update().all()

        advisor_states_by_id: Dict[int, List[str]] = {
            advisor_id: LeadService._get_user_allowed_states_for_new_leads(db, advisor_id)
            for advisor_id in advisor_order
        }

        total_newly_assigned = 0
        per_purchase_newly_assigned: Dict[int, int] = {}
        per_purchase_newly_assigned_ids: Dict[int, List[int]] = {}

        while True:
            round_active_advisors: List[int] = []
            for advisor_id in advisor_order:
                purchase_queue = advisor_purchase_queues.get(advisor_id, [])
                queue_index = LeadService._advance_purchase_queue_index(
                    purchase_queue,
                    advisor_queue_index.get(advisor_id, 0),
                    purchase_unfulfilled,
                )
                advisor_queue_index[advisor_id] = queue_index
                if queue_index >= len(purchase_queue):
                    continue
                if not advisor_states_by_id.get(advisor_id):
                    continue
                round_active_advisors.append(advisor_id)

            if not round_active_advisors:
                break

            assignments_per_advisor = 1
            if len(round_active_advisors) == 1:
                assignments_per_advisor = LeadService._RECONCILIATION_MAX_ASSIGNMENTS_PER_ADVISOR_ROUND

            assigned_in_round = 0
            for advisor_id in round_active_advisors:
                allocation_summary = LeadService._allocate_unsold_leads_for_advisor_round(
                    db=db,
                    advisor_id=advisor_id,
                    advisor_states=advisor_states_by_id.get(advisor_id, []),
                    purchase_queue=advisor_purchase_queues.get(advisor_id, []),
                    queue_index=advisor_queue_index.get(advisor_id, 0),
                    purchase_by_id=purchase_by_id,
                    purchase_unfulfilled=purchase_unfulfilled,
                    max_assignments=assignments_per_advisor,
                    dialect_name=dialect_name,
                )
                advisor_queue_index[advisor_id] = int(
                    allocation_summary.get("next_queue_index", advisor_queue_index.get(advisor_id, 0))
                )
                newly_assigned_count = int(allocation_summary.get("assigned_count", 0) or 0)

                if newly_assigned_count <= 0:
                    continue

                assigned_in_round += newly_assigned_count
                per_purchase_assigned_ids = allocation_summary.get("per_purchase_assigned_ids", {})
                if not isinstance(per_purchase_assigned_ids, dict):
                    continue
                for purchase_id, lead_ids in per_purchase_assigned_ids.items():
                    normalized_purchase_id = int(purchase_id)
                    normalized_lead_ids = [int(lead_id) for lead_id in lead_ids]
                    if not normalized_lead_ids:
                        continue
                    per_purchase_newly_assigned[normalized_purchase_id] = (
                        per_purchase_newly_assigned.get(normalized_purchase_id, 0)
                        + len(normalized_lead_ids)
                    )
                    per_purchase_newly_assigned_ids.setdefault(
                        normalized_purchase_id,
                        [],
                    ).extend(normalized_lead_ids)

            total_newly_assigned += assigned_in_round
            if assigned_in_round <= 0:
                break

        updated_purchases = len(per_purchase_newly_assigned)
        total_remaining_unfulfilled = sum(
            max(int(unfulfilled_count), 0) for unfulfilled_count in purchase_unfulfilled.values()
        )

        for purchase_id, newly_assigned_count in per_purchase_newly_assigned.items():
            purchase = purchase_by_id[purchase_id]
            requested_count = assignment_targets_by_purchase.get(
                purchase_id,
                LeadService._compute_purchase_assignment_target(purchase=purchase),
            )
            assigned_count = max(requested_count - purchase_unfulfilled[purchase_id], 0)
            newly_assigned_ids = sorted(set(per_purchase_newly_assigned_ids.get(purchase_id, [])))
            notification_summary = {"enqueued_total": 0, "enqueued_email": 0, "enqueued_sms": 0}
            if newly_assigned_ids:
                notification_summary = NotificationService.enqueue_lead_delivery_notifications(
                    db=db,
                    user_id=int(purchase.user_id),
                    lead_ids=newly_assigned_ids,
                    purchase_id=int(purchase_id),
                    source_event=source_event,
                    purchase_total_leads=requested_count,
                    delivered_leads_count=assigned_count,
                )
            AuditService.log_purchase_event(
                db=db,
                actor_user_id=purchase.user_id,
                action="purchase_leads_backfilled",
                purchase_id=purchase_id,
                correlation_ids={"purchase_id": purchase_id},
                meta_data={
                    "source_event": source_event,
                    "requested_count": requested_count,
                    "assigned_count": assigned_count,
                    "newly_assigned_count": newly_assigned_count,
                    "newly_assigned_lead_ids": newly_assigned_ids,
                    "unfulfilled_count": int(purchase_unfulfilled[purchase_id]),
                    "notification_enqueued_total": int(notification_summary["enqueued_total"]),
                    "notification_enqueued_email": int(notification_summary["enqueued_email"]),
                    "notification_enqueued_sms": int(notification_summary["enqueued_sms"]),
                },
            )

        if total_newly_assigned > 0:
            db.commit()
            MetricsService.increment(
                "purchase_pending_reconciliation_assigned_total",
                value=total_newly_assigned,
                tags={"source_event": source_event},
            )
        else:
            # Releases row locks acquired during reconciliation scans on MySQL.
            db.rollback()

        return {
            "scanned_purchases": len(purchases),
            "updated_purchases": updated_purchases,
            "newly_assigned_count": total_newly_assigned,
            "remaining_unfulfilled_count": total_remaining_unfulfilled,
        }

    @staticmethod
    def _reconcile_pending_purchases_best_effort(
        db: Session,
        *,
        state_codes: Optional[List[str]],
        source_event: str,
    ) -> None:
        try:
            summary = LeadService.reconcile_pending_purchase_assignments(
                db=db,
                state_codes=state_codes,
                source_event=source_event,
            )
            if summary["newly_assigned_count"] > 0:
                logger.info(
                    (
                        "Purchase reconciliation assigned leads: source=%s "
                        "scanned=%s updated=%s assigned=%s remaining_unfulfilled=%s"
                    ),
                    source_event,
                    summary["scanned_purchases"],
                    summary["updated_purchases"],
                    summary["newly_assigned_count"],
                    summary["remaining_unfulfilled_count"],
                )
        except Exception as exc:
            db.rollback()
            logger.error(
                "Purchase reconciliation failed after inventory ingest: source=%s error=%s",
                source_event,
                exc,
            )

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
        query = (
            db.query(Lead)
            .filter(Lead.state_code.in_(states))
            .filter(LeadService._lead_not_downloaded_by_user_condition(user_id))
            .filter(LeadService._lead_not_delivered_condition())
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
    ) -> Optional[str]:
        if not leads:
            return None

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
        return batch_id

    @staticmethod
    def _record_ownership_batch(
        db: Session,
        user_id: int,
        leads: List[Lead],
        purchase_ids_by_lead_id: Optional[Dict[int, int]] = None,
    ) -> None:
        if not leads:
            return

        for lead in leads:
            purchase_id = None
            if purchase_ids_by_lead_id:
                purchase_id = purchase_ids_by_lead_id.get(lead.id)
            db.add(
                LeadOwnership(
                    user_id=user_id,
                    lead_id=lead.id,
                    purchase_id=purchase_id,
                )
            )
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

        LeadService._record_ownership_batch(
            db=db,
            user_id=user.id,
            leads=leads,
            purchase_ids_by_lead_id=purchase_ids_by_lead_id,
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
    def _is_duplicate_ownership_integrity_error(exc: IntegrityError) -> bool:
        error_text = str(getattr(exc, "orig", exc)).lower()
        if (
            "lead_ownerships" not in error_text
            and "uq_lead_ownerships_user_lead" not in error_text
            and "uq_lead_ownerships_global_lead" not in error_text
        ):
            return False
        duplicate_markers = (
            "uq_lead_ownerships_user_lead",
            "uq_lead_ownerships_global_lead",
            "duplicate entry",
            "unique constraint",
        )
        return any(marker in error_text for marker in duplicate_markers)

    @staticmethod
    def _is_retryable_delivery_integrity_error(exc: IntegrityError) -> bool:
        return (
            LeadService._is_duplicate_download_integrity_error(exc)
            or LeadService._is_duplicate_ownership_integrity_error(exc)
        )

    @staticmethod
    def get_available_leads_for_user(
        db: Session,
        user: User,
        page: int = 1,
        size: int = 20,
        delivery_status: Literal["all", "available", "delivered"] = "all",
        outcome_status: Literal["all", "new", "contacted", "appointment_set", "closed_deal"] = "all",
        search: Optional[str] = None,
    ) -> Dict[str, object]:
        downloaded_subquery = select(LeadDownload.lead_id).where(LeadDownload.user_id == user.id)
        latest_downloaded_at = LeadService._latest_downloaded_at_subquery(user.id)
        ownership_assigned_at = LeadService._ownership_assigned_at_subquery(user.id)
        query = db.query(Lead)
        has_owned_leads = LeadService._user_has_owned_leads(db, user.id)
        if has_owned_leads:
            owned_subquery = select(LeadOwnership.lead_id).where(LeadOwnership.user_id == user.id)
            query = query.filter(Lead.id.in_(owned_subquery))
            available_condition = LeadService._lead_not_downloaded_by_user_condition(user.id)
            delivered_condition = Lead.id.in_(downloaded_subquery)
        else:
            states = LeadService._get_user_allowed_states_for_new_leads(db, user.id)
            if LeadService._can_user_view_unsold_inventory(db=db, user_id=user.id, states=states):
                available_condition = and_(
                    Lead.state_code.in_(states),
                    LeadService._lead_not_downloaded_by_user_condition(user.id),
                    LeadService._lead_not_delivered_condition(),
                )
            else:
                available_condition = false()
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
        for token in LeadService._tokenize_search_query(normalized_search):
            non_pii_token_filter = LeadService._build_non_pii_search_token_filter(token)
            pii_token_filter = LeadService._build_pii_search_token_filter(token)
            if has_owned_leads:
                query = query.filter(or_(non_pii_token_filter, pii_token_filter))
            else:
                query = query.filter(
                    or_(
                        non_pii_token_filter,
                        and_(delivered_condition, pii_token_filter),
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
            query.order_by(
                func.coalesce(
                    ownership_assigned_at if has_owned_leads else latest_downloaded_at,
                    Lead.created_at,
                ).desc(),
                Lead.id.desc(),
            )
            .offset(offset)
            .limit(size)
            .all()
        )

        LeadService._attach_outcomes_to_leads(db, user.id, items)
        LeadService._attach_downloads_to_leads(db, user.id, items)
        LeadService._attach_received_timestamps_to_leads(db, user.id, items)
        LeadService._attach_pii_unlock_flags(db, user.id, items)

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

        inventory_snapshot = LeadService.get_unsold_inventory_snapshot_for_user(db=db, user=user)
        states = inventory_snapshot.get("state_codes") or []
        if not states:
            return {"can_download": False, "reason": "No verified license states", "remaining": remaining_credits}

        available_count = int(inventory_snapshot.get("available_count") or 0)
        if available_count <= 0:
            return {"can_download": False, "reason": "No leads available", "remaining": remaining_credits}

        return {"can_download": True, "remaining": remaining_credits}

    @staticmethod
    def download_leads_csv(db: Session, user: User) -> str:
        owned_leads = LeadService._get_owned_leads_for_user(db=db, user_id=user.id)
        if owned_leads:
            lead_ids = [lead.id for lead in owned_leads]
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
            try:
                LeadService._record_download_batch(
                    db=db,
                    user_id=user.id,
                    leads=owned_leads,
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
                for consumed in consumed_events:
                    purchase_id = consumed["purchase_id"]
                    lead_id = consumed["lead_id"]
                    credits_delta = consumed["credits_delta"]
                    AuditService.log_purchase_event(
                        db=db,
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
                db.commit()
                return generate_leads_csv_stream(leads, prepend_message=prepend_msg)
            except HTTPException:
                db.rollback()
                raise
            except IntegrityError as exc:
                db.rollback()
                if LeadService._is_retryable_delivery_integrity_error(exc) and attempt < max_attempts:
                    logger.warning(
                        (
                            "Retrying lead download allocation after delivery unique conflict "
                            "for user_id=%s (attempt %s/%s)"
                        ),
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
        delivered_leads = LeadService._get_delivered_leads_for_user(db=db, user_id=user.id)
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
        if "mobile_phone" in lead_data:
            lead_data["mobile_phone"] = normalize_phone_number(lead_data.get("mobile_phone"))

        lead = Lead(**lead_data)

        try:
            db.add(lead)
            db.commit()
            db.refresh(lead)
            LeadService._reconcile_pending_purchases_best_effort(
                db=db,
                state_codes=[lead.state_code] if lead.state_code else None,
                source_event="lead_create",
            )
            return lead
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create lead: {e}")
            raise HTTPException(status_code=500, detail="Failed to create lead")

    @staticmethod
    def bulk_import_leads(
        db: Session,
        csv_data: List[dict],
        *,
        actor_user_id: Optional[int] = None,
    ) -> Dict[str, object]:
        errors: List[Dict[str, object]] = []
        failed_rows = 0

        if not csv_data:
            result = {"success": 0, "failed": 0, "errors": []}
            if actor_user_id is not None:
                try:
                    AuditService.log_event(
                        db=db,
                        actor_user_id=actor_user_id,
                        action="lead_bulk_import",
                        entity_type="LeadImport",
                        meta_data=LeadService._build_bulk_import_audit_metadata(
                            scanned_count=0,
                            success_count=0,
                            failed_count=0,
                            errors=[],
                        ),
                    )
                    db.commit()
                except Exception as exc:
                    db.rollback()
                    logger.error("Failed to audit empty lead import: %s", exc)
                    raise HTTPException(status_code=500, detail="Failed to import leads")
            return result

        normalized_rows: List[dict] = []
        for row in csv_data:
            clean_row = dict(row)
            clean_row["mobile_phone"] = normalize_phone_number(clean_row.get("mobile_phone"))
            normalized_rows.append(clean_row)

        phones = {
            row.get("mobile_phone")
            for row in normalized_rows
            if row.get("mobile_phone")
        }
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

        for idx, row in enumerate(normalized_rows):
            row_num = idx + 2
            row_errors: List[str] = []

            state_code = (row.get("state_code") or "").strip().upper()
            mobile_phone = (row.get("mobile_phone") or "").strip()

            if not state_code and "state_code" in LEAD_CSV_REQUIRED_VALUE_FIELDS:
                row_errors.append("Missing state_code")
            if not mobile_phone and "mobile_phone" in LEAD_CSV_REQUIRED_VALUE_FIELDS:
                row_errors.append("Missing mobile_phone")

            if state_code and (len(state_code) != 2 or state_code not in US_STATE_CODES):
                row_errors.append("Invalid state_code")

            if mobile_phone and mobile_phone in existing_phones:
                row_errors.append("Duplicate mobile_phone")

            if mobile_phone and mobile_phone in seen_phones:
                row_errors.append("Duplicate mobile_phone in file")

            if row_errors:
                failed_rows += 1
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
            result = {"success": 0, "failed": failed_rows, "errors": errors}
            if actor_user_id is not None:
                try:
                    AuditService.log_event(
                        db=db,
                        actor_user_id=actor_user_id,
                        action="lead_bulk_import",
                        entity_type="LeadImport",
                        meta_data=LeadService._build_bulk_import_audit_metadata(
                            scanned_count=len(csv_data),
                            success_count=0,
                            failed_count=failed_rows,
                            errors=errors,
                        ),
                    )
                    db.commit()
                except Exception as exc:
                    db.rollback()
                    logger.error("Failed to audit rejected lead import: %s", exc)
                    raise HTTPException(status_code=500, detail="Failed to import leads")
            return result

        try:
            leads = [Lead(**row) for row in valid_rows]
            db.add_all(leads)
            if actor_user_id is not None:
                AuditService.log_event(
                    db=db,
                    actor_user_id=actor_user_id,
                    action="lead_bulk_import",
                    entity_type="LeadImport",
                    meta_data=LeadService._build_bulk_import_audit_metadata(
                        scanned_count=len(csv_data),
                        success_count=len(leads),
                        failed_count=0,
                        errors=[],
                    ),
                )
            db.commit()
            imported_states = sorted({lead.state_code for lead in leads if lead.state_code})
            LeadService._reconcile_pending_purchases_best_effort(
                db=db,
                state_codes=imported_states,
                source_event="lead_bulk_import",
            )
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
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")

        if not LeadService._user_has_outcome_write_access(
            db=db,
            user_id=user.id,
            lead_id=lead_id,
        ):
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
        email_alerts_enabled = False
        sms_alerts_enabled = False
        if user.role == "advisor":
            delivery_settings = DeliverySettingsService.get_or_create_for_user(
                db=db,
                user_id=user.id,
            )
            email_alerts_enabled = bool(delivery_settings.email_alerts_enabled)
            sms_alerts_enabled = bool(delivery_settings.sms_alerts_enabled)

        recent_owned_lead_ids = (
            select(LeadOwnership.lead_id)
            .filter(
                LeadOwnership.user_id == user.id,
                LeadOwnership.assigned_at >= seven_days_ago,
            )
            .distinct()
        )
        # Backward compatibility for legacy delivered rows that predate ownership rollout.
        recent_legacy_downloaded_lead_ids = (
            select(LeadDownload.lead_id)
            .filter(
                LeadDownload.user_id == user.id,
                LeadDownload.downloaded_at >= seven_days_ago,
                ~select(LeadOwnership.id)
                .filter(
                    LeadOwnership.user_id == user.id,
                    LeadOwnership.lead_id == LeadDownload.lead_id,
                )
                .exists(),
            )
            .distinct()
        )
        recent_delivered_lead_ids = (
            recent_owned_lead_ids.union(recent_legacy_downloaded_lead_ids)
        ).subquery(name="recent_delivered_lead_ids")

        leads_delivered_7_days = (
            db.query(func.count())
            .select_from(recent_delivered_lead_ids)
            .scalar()
        ) or 0

        appointments_set_7_days = (
            db.query(func.count(func.distinct(LeadOutcome.lead_id)))
            .filter(
                LeadOutcome.user_id == user.id,
                LeadOutcome.status == "appointment_set",
                LeadOutcome.lead_id.in_(select(recent_delivered_lead_ids.c.lead_id)),
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
            total_spend_cents=int(latest_completed_purchase.amount_cents) if latest_completed_purchase else 0,
            appointments_set=appointments_set_7_days,
        )

        currency = (latest_completed_purchase.currency or "USD").upper() if latest_completed_purchase else "USD"

        return {
            "leads_delivered_7_days": int(leads_delivered_7_days),
            "appointments_set_7_days": int(appointments_set_7_days),
            "cost_per_appointment": cost_per_appointment,
            "currency": currency,
            "settings": {
                "email_alerts_enabled": email_alerts_enabled,
                "sms_alerts_enabled": sms_alerts_enabled,
                "target_states": states,
                "min_assets": None,
                "daily_download_limit": None,
            },
        }
