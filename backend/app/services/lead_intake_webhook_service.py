import hashlib
import hmac
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Mapping, Optional

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.lead import Lead, LeadIntakeWebhookEvent
from app.schemas.lead import LeadCreate
from app.services.lead_service import LeadService, US_STATE_CODES

logger = logging.getLogger(__name__)


_CANONICALIZE_PATTERN = re.compile(r"[^a-z0-9]+")

_WPFORMS_META_KEYS = {
    "entry id",
    "entryid",
    "form id",
    "formid",
    "form name",
    "formname",
    "fields",
    "entry",
    "created at",
    "date",
    "time",
}

_STATE_NAME_TO_CODE = {
    "alabama": "AL",
    "alaska": "AK",
    "arizona": "AZ",
    "arkansas": "AR",
    "california": "CA",
    "colorado": "CO",
    "connecticut": "CT",
    "delaware": "DE",
    "district of columbia": "DC",
    "florida": "FL",
    "georgia": "GA",
    "hawaii": "HI",
    "idaho": "ID",
    "illinois": "IL",
    "indiana": "IN",
    "iowa": "IA",
    "kansas": "KS",
    "kentucky": "KY",
    "louisiana": "LA",
    "maine": "ME",
    "maryland": "MD",
    "massachusetts": "MA",
    "michigan": "MI",
    "minnesota": "MN",
    "mississippi": "MS",
    "missouri": "MO",
    "montana": "MT",
    "nebraska": "NE",
    "nevada": "NV",
    "new hampshire": "NH",
    "new jersey": "NJ",
    "new mexico": "NM",
    "new york": "NY",
    "north carolina": "NC",
    "north dakota": "ND",
    "ohio": "OH",
    "oklahoma": "OK",
    "oregon": "OR",
    "pennsylvania": "PA",
    "rhode island": "RI",
    "south carolina": "SC",
    "south dakota": "SD",
    "tennessee": "TN",
    "texas": "TX",
    "utah": "UT",
    "vermont": "VT",
    "virginia": "VA",
    "washington": "WA",
    "west virginia": "WV",
    "wisconsin": "WI",
    "wyoming": "WY",
}


class LeadIntakeWebhookService:
    PROVIDER = "wpforms"

    _FIELD_ALIASES: Dict[str, tuple[str, ...]] = {
        "full_name": (
            "what is your first last name",
            "first last name",
            "first and last name",
            "full name",
            "name",
        ),
        "retirement_timeline": ("when would you like to retire",),
        "confidence_in_long_term_plan": (
            "how confident are you in your current long term financial plan",
        ),
        "most_important_retirement_activity": (
            "what activity is most important to you in retirement",
        ),
        "overall_health": ("how would you characterize your overall health",),
        "planning_to_relocate_retirement": (
            "are you planning on relocating for retirement",
        ),
        "expected_retirement_income_source": (
            "where do you expect the majority of your retirement income to come from",
        ),
        "money_management_style": ("how do you currently manage your money",),
        "investor_profile_statement": ("which statement best describes you",),
        "main_purpose_for_investing": (
            "what is your main purpose for investing check all that apply",
        ),
        "investment_comfort_level": ("how comfortable are you with investing",),
        "retirement_savings_range": (
            "about what amount do you currently have saved for retirement",
        ),
        "wants_to_improve_strategy_timing": (
            "how quickly would you like to improve your long term financial strategy",
        ),
        "current_investment_strategies": (
            "what investment strategies are you currently using check all that apply",
        ),
        "has_financial_advisor": ("do you currently have a financial advisor",),
        "advisor_local_preference": (
            "would you prefer your financial advisor to be located in your immediate area",
        ),
        "annual_household_income_range": (
            "please estimate your annual household income",
        ),
        "total_investable_assets_range": (
            "please estimate your total investable assets",
        ),
        "monthly_savings_range": (
            "please estimate your current monthly savings",
        ),
        "owns_annuity": ("do you currently own an annuity",),
        "preferred_follow_up_method": ("which follow up method would you prefer",),
        "state_code": ("what state are you located in",),
        "zip_code": ("please enter your zip code", "zip code"),
        "mobile_phone": (
            "please provide your mobile phone number",
            "mobile phone number",
            "phone number",
        ),
        "best_time_to_reach": ("what is the best time of day to reach you",),
        "additional_notes": ("is there anything else you d like us to know",),
    }

    @staticmethod
    def process_wpforms_submission(
        db: Session,
        *,
        raw_body: bytes,
        headers: Mapping[str, str],
    ) -> Dict[str, Any]:
        payload = LeadIntakeWebhookService._parse_payload(raw_body)
        entry_id = LeadIntakeWebhookService._extract_entry_id(payload)
        LeadIntakeWebhookService._verify_signature(raw_body=raw_body, headers=headers)

        lead_input = LeadIntakeWebhookService._map_payload_to_lead(payload)
        payload_hash = hashlib.sha256(raw_body).hexdigest()

        return LeadIntakeWebhookService._persist_submission(
            db=db,
            entry_id=entry_id,
            payload_hash=payload_hash,
            lead_input=lead_input,
        )

    @staticmethod
    def _parse_payload(raw_body: bytes) -> Dict[str, Any]:
        try:
            parsed = json.loads(raw_body.decode("utf-8"))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON payload")
        if not isinstance(parsed, dict):
            raise HTTPException(status_code=400, detail="Webhook payload must be a JSON object")
        return parsed

    @staticmethod
    def _verify_signature(*, raw_body: bytes, headers: Mapping[str, str]) -> None:
        secret = settings.WPFORMS_WEBHOOK_HMAC_SECRET.strip()
        if not secret:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Webhook signing secret is not configured",
            )

        signature_header_name = settings.WPFORMS_WEBHOOK_SIGNATURE_HEADER.strip()
        timestamp_header_name = settings.WPFORMS_WEBHOOK_TIMESTAMP_HEADER.strip()

        signature_header_value = headers.get(signature_header_name)
        if not signature_header_value:
            raise HTTPException(status_code=400, detail="Missing webhook signature")

        timestamp_value = headers.get(timestamp_header_name)
        if not timestamp_value:
            raise HTTPException(status_code=400, detail="Missing webhook timestamp")

        timestamp = LeadIntakeWebhookService._parse_timestamp(timestamp_value)
        tolerance_seconds = int(settings.WPFORMS_WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS)
        now = int(datetime.now(tz=timezone.utc).timestamp())
        if abs(now - timestamp) > tolerance_seconds:
            raise HTTPException(status_code=400, detail="Webhook timestamp is outside tolerance window")

        signed_payload = f"{timestamp}.".encode("utf-8") + raw_body
        expected_with_timestamp = hmac.new(
            secret.encode("utf-8"),
            signed_payload,
            hashlib.sha256,
        ).hexdigest()
        candidates = LeadIntakeWebhookService._extract_signature_candidates(signature_header_value)
        if LeadIntakeWebhookService._matches_any_signature(
            expected_with_timestamp,
            candidates,
        ):
            return

        if settings.WPFORMS_WEBHOOK_ALLOW_BODY_ONLY_SIGNATURE:
            expected_body_only = hmac.new(
                secret.encode("utf-8"),
                raw_body,
                hashlib.sha256,
            ).hexdigest()
            if LeadIntakeWebhookService._matches_any_signature(
                expected_body_only,
                candidates,
            ):
                return

        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    @staticmethod
    def _parse_timestamp(value: str) -> int:
        clean = str(value or "").strip()
        try:
            raw = int(clean)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid webhook timestamp")
        # Support millisecond epoch values by normalizing to seconds.
        if raw > 1_000_000_000_000:
            raw = int(raw / 1000)
        return raw

    @staticmethod
    def _extract_signature_candidates(signature_header_value: str) -> list[str]:
        candidates: list[str] = []
        for raw_part in str(signature_header_value).split(","):
            part = raw_part.strip()
            if not part:
                continue
            if "=" in part:
                _, candidate = part.split("=", 1)
            else:
                candidate = part
            normalized = candidate.strip().lower()
            if normalized:
                candidates.append(normalized)
        return candidates

    @staticmethod
    def _matches_any_signature(expected: str, candidates: Iterable[str]) -> bool:
        expected_clean = expected.strip().lower()
        return any(hmac.compare_digest(expected_clean, candidate) for candidate in candidates)

    @staticmethod
    def _extract_entry_id(payload: Dict[str, Any]) -> str:
        candidates: list[Any] = [
            payload.get("entry_id"),
            payload.get("entryId"),
        ]
        entry = payload.get("entry")
        if isinstance(entry, dict):
            candidates.extend(
                [
                    entry.get("id"),
                    entry.get("entry_id"),
                ]
            )
        candidates.append(payload.get("id"))

        for value in candidates:
            clean = str(value or "").strip()
            if clean:
                return clean
        raise HTTPException(status_code=400, detail="Missing WPForms entry ID")

    @staticmethod
    def _map_payload_to_lead(payload: Dict[str, Any]) -> LeadCreate:
        answers = LeadIntakeWebhookService._collect_answers(payload)

        full_name = LeadIntakeWebhookService._find_answer(
            answers,
            LeadIntakeWebhookService._FIELD_ALIASES["full_name"],
        )
        first_name, last_name = LeadIntakeWebhookService._split_name(full_name)

        state_raw = LeadIntakeWebhookService._find_answer(
            answers,
            LeadIntakeWebhookService._FIELD_ALIASES["state_code"],
        )
        state_code = LeadIntakeWebhookService._normalize_state(state_raw)
        if not state_code:
            raise HTTPException(status_code=400, detail="Unable to map state code from payload")

        lead_payload: Dict[str, Any] = {
            "source": "api_submission",
            "state_code": state_code,
            "first_name": first_name,
            "last_name": last_name,
            "zip_code": LeadIntakeWebhookService._to_clean_text(
                LeadIntakeWebhookService._find_answer(
                    answers,
                    LeadIntakeWebhookService._FIELD_ALIASES["zip_code"],
                )
            ),
            "mobile_phone": LeadIntakeWebhookService._to_clean_text(
                LeadIntakeWebhookService._find_answer(
                    answers,
                    LeadIntakeWebhookService._FIELD_ALIASES["mobile_phone"],
                )
            ),
            "preferred_follow_up_method": LeadIntakeWebhookService._to_clean_text(
                LeadIntakeWebhookService._find_answer(
                    answers,
                    LeadIntakeWebhookService._FIELD_ALIASES["preferred_follow_up_method"],
                )
            ),
            "best_time_to_reach": LeadIntakeWebhookService._normalize_best_time(
                LeadIntakeWebhookService._find_answer(
                    answers,
                    LeadIntakeWebhookService._FIELD_ALIASES["best_time_to_reach"],
                )
            ),
            "retirement_timeline": LeadIntakeWebhookService._to_clean_text(
                LeadIntakeWebhookService._find_answer(
                    answers,
                    LeadIntakeWebhookService._FIELD_ALIASES["retirement_timeline"],
                )
            ),
            "confidence_in_long_term_plan": LeadIntakeWebhookService._to_clean_text(
                LeadIntakeWebhookService._find_answer(
                    answers,
                    LeadIntakeWebhookService._FIELD_ALIASES["confidence_in_long_term_plan"],
                )
            ),
            "most_important_retirement_activity": LeadIntakeWebhookService._to_clean_text(
                LeadIntakeWebhookService._find_answer(
                    answers,
                    LeadIntakeWebhookService._FIELD_ALIASES["most_important_retirement_activity"],
                )
            ),
            "planning_to_relocate_retirement": LeadIntakeWebhookService._to_clean_text(
                LeadIntakeWebhookService._find_answer(
                    answers,
                    LeadIntakeWebhookService._FIELD_ALIASES["planning_to_relocate_retirement"],
                )
            ),
            "expected_retirement_income_source": LeadIntakeWebhookService._to_clean_text(
                LeadIntakeWebhookService._find_answer(
                    answers,
                    LeadIntakeWebhookService._FIELD_ALIASES["expected_retirement_income_source"],
                )
            ),
            "overall_health": LeadIntakeWebhookService._to_clean_text(
                LeadIntakeWebhookService._find_answer(
                    answers,
                    LeadIntakeWebhookService._FIELD_ALIASES["overall_health"],
                )
            ),
            "money_management_style": LeadIntakeWebhookService._to_clean_text(
                LeadIntakeWebhookService._find_answer(
                    answers,
                    LeadIntakeWebhookService._FIELD_ALIASES["money_management_style"],
                )
            ),
            "investor_profile_statement": LeadIntakeWebhookService._to_clean_text(
                LeadIntakeWebhookService._find_answer(
                    answers,
                    LeadIntakeWebhookService._FIELD_ALIASES["investor_profile_statement"],
                )
            ),
            "investment_comfort_level": LeadIntakeWebhookService._to_clean_text(
                LeadIntakeWebhookService._find_answer(
                    answers,
                    LeadIntakeWebhookService._FIELD_ALIASES["investment_comfort_level"],
                )
            ),
            "main_purpose_for_investing": LeadIntakeWebhookService._to_choice_list(
                LeadIntakeWebhookService._find_answer(
                    answers,
                    LeadIntakeWebhookService._FIELD_ALIASES["main_purpose_for_investing"],
                )
            ),
            "retirement_savings_range": LeadIntakeWebhookService._to_clean_text(
                LeadIntakeWebhookService._find_answer(
                    answers,
                    LeadIntakeWebhookService._FIELD_ALIASES["retirement_savings_range"],
                )
            ),
            "annual_household_income_range": LeadIntakeWebhookService._to_clean_text(
                LeadIntakeWebhookService._find_answer(
                    answers,
                    LeadIntakeWebhookService._FIELD_ALIASES["annual_household_income_range"],
                )
            ),
            "total_investable_assets_range": LeadIntakeWebhookService._to_clean_text(
                LeadIntakeWebhookService._find_answer(
                    answers,
                    LeadIntakeWebhookService._FIELD_ALIASES["total_investable_assets_range"],
                )
            ),
            "monthly_savings_range": LeadIntakeWebhookService._to_clean_text(
                LeadIntakeWebhookService._find_answer(
                    answers,
                    LeadIntakeWebhookService._FIELD_ALIASES["monthly_savings_range"],
                )
            ),
            "wants_to_improve_strategy_timing": LeadIntakeWebhookService._to_clean_text(
                LeadIntakeWebhookService._find_answer(
                    answers,
                    LeadIntakeWebhookService._FIELD_ALIASES["wants_to_improve_strategy_timing"],
                )
            ),
            "current_investment_strategies": LeadIntakeWebhookService._to_choice_list(
                LeadIntakeWebhookService._find_answer(
                    answers,
                    LeadIntakeWebhookService._FIELD_ALIASES["current_investment_strategies"],
                )
            ),
            "has_financial_advisor": LeadIntakeWebhookService._to_clean_text(
                LeadIntakeWebhookService._find_answer(
                    answers,
                    LeadIntakeWebhookService._FIELD_ALIASES["has_financial_advisor"],
                )
            ),
            "advisor_local_preference": LeadIntakeWebhookService._to_clean_text(
                LeadIntakeWebhookService._find_answer(
                    answers,
                    LeadIntakeWebhookService._FIELD_ALIASES["advisor_local_preference"],
                )
            ),
            "owns_annuity": LeadIntakeWebhookService._to_clean_text(
                LeadIntakeWebhookService._find_answer(
                    answers,
                    LeadIntakeWebhookService._FIELD_ALIASES["owns_annuity"],
                )
            ),
            "additional_notes": LeadIntakeWebhookService._to_clean_text(
                LeadIntakeWebhookService._find_answer(
                    answers,
                    LeadIntakeWebhookService._FIELD_ALIASES["additional_notes"],
                )
            ),
        }

        filtered_payload = {
            key: value
            for key, value in lead_payload.items()
            if value is not None
        }

        try:
            return LeadCreate.model_validate(filtered_payload)
        except ValidationError:
            raise HTTPException(status_code=400, detail="Mapped lead payload failed validation")

    @staticmethod
    def _persist_submission(
        db: Session,
        *,
        entry_id: str,
        payload_hash: str,
        lead_input: LeadCreate,
    ) -> Dict[str, Any]:
        lead_data = lead_input.model_dump(exclude_unset=True)
        lead = Lead(**lead_data)

        event = LeadIntakeWebhookEvent(
            provider=LeadIntakeWebhookService.PROVIDER,
            external_entry_id=entry_id,
            payload_hash=payload_hash,
            lead=lead,
        )

        try:
            db.add(event)
            db.commit()
            db.refresh(event)
        except IntegrityError as exc:
            db.rollback()
            if not LeadIntakeWebhookService._is_duplicate_entry_integrity_error(exc):
                logger.error("WPForms intake insert failed with integrity error: %s", exc)
                raise HTTPException(status_code=500, detail="Failed to process webhook submission")

            existing = (
                db.query(LeadIntakeWebhookEvent)
                .filter(
                    LeadIntakeWebhookEvent.provider == LeadIntakeWebhookService.PROVIDER,
                    LeadIntakeWebhookEvent.external_entry_id == entry_id,
                )
                .first()
            )
            if existing is not None and existing.payload_hash and existing.payload_hash != payload_hash:
                logger.warning(
                    "WPForms webhook replay with mismatched payload hash: entry_id=%s",
                    entry_id,
                )
            return {
                "lead_id": int(existing.lead_id) if existing and existing.lead_id is not None else None,
                "idempotent_replay": True,
            }
        except Exception as exc:
            db.rollback()
            logger.error("WPForms intake processing failed: %s", exc)
            raise HTTPException(status_code=500, detail="Failed to process webhook submission")

        lead_id = int(event.lead_id) if event.lead_id is not None else int(lead.id)
        try:
            if lead.state_code:
                LeadService._reconcile_pending_purchases_best_effort(
                    db=db,
                    state_codes=[lead.state_code],
                    source_event="wpforms_webhook_intake",
                )
        except Exception:
            # Best effort and intentionally non-fatal for webhook ingestion.
            logger.exception(
                "Best-effort reconciliation failed after WPForms lead intake: lead_id=%s",
                lead_id,
            )

        return {
            "lead_id": lead_id,
            "idempotent_replay": False,
        }

    @staticmethod
    def _is_duplicate_entry_integrity_error(exc: IntegrityError) -> bool:
        details = " ".join(
            [
                str(exc).lower(),
                str(getattr(exc, "orig", "")).lower(),
                str(getattr(exc, "statement", "")).lower(),
                str(getattr(exc, "params", "")).lower(),
            ]
        )
        has_duplicate_marker = any(
            marker in details
            for marker in (
                "duplicate",
                "duplicate entry",
                "duplicate key value",
                "unique constraint",
                "unique constraint failed",
            )
        )
        has_table_marker = "lead_intake_webhook_events" in details
        has_constraint_marker = "uq_lead_intake_webhook_events_provider_entry" in details
        return has_duplicate_marker and (has_table_marker or has_constraint_marker)

    @staticmethod
    def _collect_answers(payload: Dict[str, Any]) -> Dict[str, Any]:
        answers: Dict[str, Any] = {}

        fields = payload.get("fields")
        if fields is None:
            entry = payload.get("entry")
            if isinstance(entry, dict):
                fields = entry.get("fields")
        LeadIntakeWebhookService._collect_field_container_answers(answers, fields)

        for key, value in payload.items():
            key_clean = LeadIntakeWebhookService._canonicalize_key(key)
            if key_clean in _WPFORMS_META_KEYS:
                continue
            LeadIntakeWebhookService._add_answer(answers, key, value)

        return answers

    @staticmethod
    def _collect_field_container_answers(answers: Dict[str, Any], fields: Any) -> None:
        if isinstance(fields, dict):
            for key, value in fields.items():
                if isinstance(value, dict):
                    label = (
                        value.get("name")
                        or value.get("label")
                        or value.get("field_label")
                        or value.get("title")
                        or str(key)
                    )
                    extracted_value = value.get("value")
                    if extracted_value is None:
                        first = value.get("first") or value.get("first_name")
                        last = value.get("last") or value.get("last_name")
                        if first or last:
                            extracted_value = {"first": first, "last": last}
                    LeadIntakeWebhookService._add_answer(answers, label, extracted_value)
                else:
                    LeadIntakeWebhookService._add_answer(answers, str(key), value)
            return

        if isinstance(fields, list):
            for value in fields:
                if not isinstance(value, dict):
                    continue
                label = (
                    value.get("name")
                    or value.get("label")
                    or value.get("field_label")
                    or value.get("title")
                )
                extracted_value = value.get("value")
                if extracted_value is None:
                    first = value.get("first") or value.get("first_name")
                    last = value.get("last") or value.get("last_name")
                    if first or last:
                        extracted_value = {"first": first, "last": last}
                LeadIntakeWebhookService._add_answer(answers, label, extracted_value)

    @staticmethod
    def _add_answer(answers: Dict[str, Any], key: Any, value: Any) -> None:
        canonical = LeadIntakeWebhookService._canonicalize_key(key)
        if not canonical or value is None:
            return
        if canonical not in answers:
            answers[canonical] = value

    @staticmethod
    def _find_answer(answers: Dict[str, Any], aliases: Iterable[str]) -> Any:
        canonical_aliases = [LeadIntakeWebhookService._canonicalize_key(alias) for alias in aliases]
        for alias in canonical_aliases:
            if alias in answers:
                return answers[alias]
        for alias in canonical_aliases:
            for key, value in answers.items():
                if alias and alias in key:
                    return value
        return None

    @staticmethod
    def _canonicalize_key(value: Any) -> str:
        text = str(value or "").strip().lower()
        normalized = _CANONICALIZE_PATTERN.sub(" ", text)
        return " ".join(normalized.split())

    @staticmethod
    def _to_clean_text(value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, dict):
            parts = [
                LeadIntakeWebhookService._to_clean_text(item)
                for item in value.values()
            ]
            joined = " ".join([part for part in parts if part])
            return joined or None
        if isinstance(value, list):
            parts = [
                LeadIntakeWebhookService._to_clean_text(item)
                for item in value
            ]
            joined = " ".join([part for part in parts if part])
            return joined or None
        clean = " ".join(str(value).split())
        return clean if clean else None

    @staticmethod
    def _to_choice_list(value: Any) -> Optional[list[str]]:
        if value is None:
            return None

        choices: list[str] = []
        if isinstance(value, list):
            raw_values = value
        elif isinstance(value, dict):
            raw_values = list(value.values())
        else:
            raw_values = re.split(r"\s*(?:\n|,|\||;)\s*", str(value))

        for item in raw_values:
            clean = LeadIntakeWebhookService._to_clean_text(item)
            if clean:
                choices.append(clean)
        return choices or None

    @staticmethod
    def _normalize_best_time(value: Any) -> Optional[str]:
        clean = LeadIntakeWebhookService._to_clean_text(value)
        if not clean:
            return None
        lowered = clean.lower()
        if lowered.startswith("am"):
            return "AM"
        if lowered.startswith("pm"):
            return "PM"
        return clean

    @staticmethod
    def _normalize_state(value: Any) -> Optional[str]:
        clean = LeadIntakeWebhookService._to_clean_text(value)
        if not clean:
            return None

        upper = clean.upper()
        if upper in US_STATE_CODES:
            return upper
        if len(upper) == 2 and upper in US_STATE_CODES:
            return upper

        normalized_name = LeadIntakeWebhookService._canonicalize_key(clean)
        if normalized_name in _STATE_NAME_TO_CODE:
            return _STATE_NAME_TO_CODE[normalized_name]
        return upper

    @staticmethod
    def _split_name(value: Any) -> tuple[Optional[str], Optional[str]]:
        if value is None:
            return None, None

        if isinstance(value, dict):
            first = LeadIntakeWebhookService._to_clean_text(
                value.get("first") or value.get("first_name")
            )
            last = LeadIntakeWebhookService._to_clean_text(
                value.get("last") or value.get("last_name")
            )
            if first or last:
                return first, last

        clean = LeadIntakeWebhookService._to_clean_text(value)
        if not clean:
            return None, None

        lines = [line.strip() for line in str(value).splitlines() if line and line.strip()]
        if len(lines) >= 2:
            first = LeadIntakeWebhookService._to_clean_text(lines[0])
            last = LeadIntakeWebhookService._to_clean_text(" ".join(lines[1:]))
            return first, last

        parts = clean.split(" ")
        if len(parts) == 1:
            return parts[0], None
        return parts[0], " ".join(parts[1:])
