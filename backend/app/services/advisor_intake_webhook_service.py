import hashlib
import hmac
import json
import logging
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Mapping, Optional
from urllib.parse import parse_qs

from fastapi import HTTPException, status
from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_password_hash
from app.models.advisor_intake import AdvisorIntakeWebhookEvent
from app.models.user import User
from app.services.auth_service import AuthService
from app.utils.phone import normalize_phone_number

logger = logging.getLogger(__name__)

_CANONICALIZE_PATTERN = re.compile(r"[^a-z0-9]+")
_US_E164_PHONE_PATTERN = re.compile(r"^\+1\d{10}$")
_EMAIL_ADAPTER = TypeAdapter(EmailStr)

_META_KEYS = {
    "entry",
    "entry id",
    "entryid",
    "form",
    "form id",
    "formid",
    "form name",
    "formname",
    "fields",
    "form fields",
    "all fields",
    "data",
    "created at",
    "date",
    "time",
}


@dataclass(frozen=True)
class AdvisorIntakeSubmission:
    entry_id: str
    email: str
    name: str
    phone: Optional[str] = None
    company: Optional[str] = None
    state: Optional[str] = None
    notes: Optional[str] = None


class AdvisorIntakeWebhookService:
    PROVIDER = "elementor"

    _FIELD_ALIASES: Dict[str, tuple[str, ...]] = {
        "name": (
            "name",
            "full name",
            "advisor name",
            "first last name",
            "first and last name",
        ),
        "email": (
            "email",
            "email address",
            "advisor email",
            "business email",
        ),
        "phone": (
            "phone",
            "phone number",
            "mobile phone",
            "mobile phone number",
            "advisor phone",
        ),
        "company": (
            "company",
            "company name",
            "firm",
            "firm name",
            "business name",
        ),
        "state": (
            "state",
            "licensed state",
            "license state",
            "advisor state",
        ),
        "notes": (
            "notes",
            "message",
            "additional notes",
            "anything else",
        ),
    }

    @staticmethod
    def process_submission(
        db: Session,
        *,
        raw_body: bytes,
        headers: Mapping[str, str],
        content_type: str | None,
    ) -> Dict[str, Any]:
        AdvisorIntakeWebhookService._verify_signature(raw_body=raw_body, headers=headers)
        payload = AdvisorIntakeWebhookService._parse_payload(raw_body, content_type=content_type)
        submission = AdvisorIntakeWebhookService._map_payload_to_submission(payload)
        payload_hash = hashlib.sha256(raw_body).hexdigest()

        return AdvisorIntakeWebhookService._persist_submission(
            db=db,
            submission=submission,
            payload_hash=payload_hash,
        )

    @staticmethod
    def _parse_payload(raw_body: bytes, *, content_type: str | None) -> Dict[str, Any]:
        body_text = raw_body.decode("utf-8", errors="replace")
        normalized_content_type = (content_type or "").split(";", 1)[0].strip().lower()

        if normalized_content_type == "application/x-www-form-urlencoded":
            return AdvisorIntakeWebhookService._parse_form_urlencoded(body_text)

        if normalized_content_type in {"", "application/json"}:
            try:
                parsed = json.loads(body_text)
            except Exception:
                if normalized_content_type == "application/json":
                    raise HTTPException(status_code=400, detail="Invalid JSON payload")
                return AdvisorIntakeWebhookService._parse_form_urlencoded(body_text)
            if not isinstance(parsed, dict):
                raise HTTPException(status_code=400, detail="Webhook payload must be a JSON object")
            return parsed

        raise HTTPException(status_code=415, detail="Unsupported advisor intake webhook content type")

    @staticmethod
    def _parse_form_urlencoded(body_text: str) -> Dict[str, Any]:
        parsed = parse_qs(body_text, keep_blank_values=True)
        if not parsed:
            raise HTTPException(status_code=400, detail="Invalid form payload")
        return {
            key: values[0] if len(values) == 1 else values
            for key, values in parsed.items()
        }

    @staticmethod
    def _verify_signature(*, raw_body: bytes, headers: Mapping[str, str]) -> None:
        secret = settings.ADVISOR_INTAKE_WEBHOOK_HMAC_SECRET.strip()
        if not secret:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Advisor intake webhook signing secret is not configured",
            )

        signature_header_value = headers.get(settings.ADVISOR_INTAKE_WEBHOOK_SIGNATURE_HEADER.strip())
        if not signature_header_value:
            raise HTTPException(status_code=400, detail="Missing advisor intake webhook signature")

        timestamp_value = headers.get(settings.ADVISOR_INTAKE_WEBHOOK_TIMESTAMP_HEADER.strip())
        if not timestamp_value:
            raise HTTPException(status_code=400, detail="Missing advisor intake webhook timestamp")

        timestamp = AdvisorIntakeWebhookService._parse_timestamp(timestamp_value)
        tolerance_seconds = int(settings.ADVISOR_INTAKE_WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS)
        now = int(datetime.now(tz=timezone.utc).timestamp())
        if abs(now - timestamp) > tolerance_seconds:
            raise HTTPException(status_code=400, detail="Advisor intake webhook timestamp is outside tolerance window")

        signed_payload = f"{timestamp}.".encode("utf-8") + raw_body
        expected_signature = hmac.new(
            secret.encode("utf-8"),
            signed_payload,
            hashlib.sha256,
        ).hexdigest()
        candidates = AdvisorIntakeWebhookService._extract_signature_candidates(signature_header_value)
        if not AdvisorIntakeWebhookService._matches_any_signature(expected_signature, candidates):
            raise HTTPException(status_code=400, detail="Invalid advisor intake webhook signature")

    @staticmethod
    def _parse_timestamp(value: str) -> int:
        clean = str(value or "").strip()
        try:
            raw = int(clean)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid advisor intake webhook timestamp")
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
    def _map_payload_to_submission(payload: Dict[str, Any]) -> AdvisorIntakeSubmission:
        answers = AdvisorIntakeWebhookService._collect_answers(payload)
        entry_id = AdvisorIntakeWebhookService._extract_entry_id(payload)

        raw_email = AdvisorIntakeWebhookService._find_answer(
            answers,
            AdvisorIntakeWebhookService._FIELD_ALIASES["email"],
        )
        email = AdvisorIntakeWebhookService._normalize_email(raw_email)
        if not email:
            raise HTTPException(status_code=400, detail="Missing or invalid advisor email")

        name = AdvisorIntakeWebhookService._to_clean_text(
            AdvisorIntakeWebhookService._find_answer(
                answers,
                AdvisorIntakeWebhookService._FIELD_ALIASES["name"],
            )
        )
        if not name:
            raise HTTPException(status_code=400, detail="Missing advisor name")

        phone = AdvisorIntakeWebhookService._to_clean_text(
            AdvisorIntakeWebhookService._find_answer(
                answers,
                AdvisorIntakeWebhookService._FIELD_ALIASES["phone"],
            )
        )
        normalized_phone = normalize_phone_number(phone)
        if not normalized_phone:
            raise HTTPException(status_code=400, detail="Missing advisor phone")
        if not _US_E164_PHONE_PATTERN.fullmatch(normalized_phone):
            raise HTTPException(status_code=400, detail="Advisor phone must be a valid US number")

        return AdvisorIntakeSubmission(
            entry_id=entry_id,
            email=email,
            name=name,
            phone=normalized_phone,
            company=AdvisorIntakeWebhookService._to_clean_text(
                AdvisorIntakeWebhookService._find_answer(
                    answers,
                    AdvisorIntakeWebhookService._FIELD_ALIASES["company"],
                )
            ),
            state=AdvisorIntakeWebhookService._to_clean_text(
                AdvisorIntakeWebhookService._find_answer(
                    answers,
                    AdvisorIntakeWebhookService._FIELD_ALIASES["state"],
                )
            ),
            notes=AdvisorIntakeWebhookService._to_clean_text(
                AdvisorIntakeWebhookService._find_answer(
                    answers,
                    AdvisorIntakeWebhookService._FIELD_ALIASES["notes"],
                )
            ),
        )

    @staticmethod
    def _persist_submission(
        db: Session,
        *,
        submission: AdvisorIntakeSubmission,
        payload_hash: str,
    ) -> Dict[str, Any]:
        existing_event = (
            db.query(AdvisorIntakeWebhookEvent)
            .filter(
                AdvisorIntakeWebhookEvent.provider == AdvisorIntakeWebhookService.PROVIDER,
                AdvisorIntakeWebhookEvent.external_entry_id == submission.entry_id,
            )
            .first()
        )
        if existing_event is not None:
            if existing_event.payload_hash and existing_event.payload_hash != payload_hash:
                logger.warning(
                    "Advisor intake replay with mismatched payload hash: entry_id=%s",
                    submission.entry_id,
                )
            return AdvisorIntakeWebhookService._result_from_event(existing_event, idempotent_replay=True)

        existing_user = AuthService._find_user_by_email(db, submission.email)
        if existing_user is not None:
            if existing_user.role != "advisor":
                raise HTTPException(
                    status_code=409,
                    detail="Advisor intake email already belongs to a non-advisor account",
                )
            if not existing_user.is_active:
                raise HTTPException(
                    status_code=409,
                    detail="Advisor intake email belongs to a deactivated account",
                )
            user = existing_user
            event_status = "existing_advisor"
            account_created = False
        else:
            user = User(
                email=submission.email,
                name=submission.name,
                phone=submission.phone,
                password_hash=get_password_hash(secrets.token_urlsafe(48)),
                role="advisor",
            )
            db.add(user)
            event_status = "account_created"
            account_created = True

        event = AdvisorIntakeWebhookEvent(
            provider=AdvisorIntakeWebhookService.PROVIDER,
            external_entry_id=submission.entry_id,
            payload_hash=payload_hash,
            email=submission.email,
            status=event_status,
            status_reason=AdvisorIntakeWebhookService._build_status_reason(submission),
            user=user,
        )

        try:
            db.add(event)
            db.commit()
            db.refresh(event)
        except IntegrityError as exc:
            db.rollback()
            if AdvisorIntakeWebhookService._is_duplicate_entry_integrity_error(exc):
                replay = AdvisorIntakeWebhookService._get_existing_event(
                    db,
                    entry_id=submission.entry_id,
                )
                if replay is None:
                    raise HTTPException(status_code=500, detail="Failed to process advisor intake submission")
                return AdvisorIntakeWebhookService._result_from_event(replay, idempotent_replay=True)

            if AuthService._is_duplicate_email_integrity_error(exc):
                return AdvisorIntakeWebhookService._persist_existing_user_after_email_race(
                    db=db,
                    submission=submission,
                    payload_hash=payload_hash,
                )

            logger.error("Advisor intake insert failed with integrity error: %s", exc)
            raise HTTPException(status_code=500, detail="Failed to process advisor intake submission")
        except Exception as exc:
            db.rollback()
            logger.error("Advisor intake processing failed: %s", exc)
            raise HTTPException(status_code=500, detail="Failed to process advisor intake submission")

        return {
            "user_id": int(event.user_id) if event.user_id is not None else int(user.id),
            "idempotent_replay": False,
            "account_created": account_created,
            "existing_user": not account_created,
            "setup_email_queued": False,
        }

    @staticmethod
    def _result_from_event(
        event: AdvisorIntakeWebhookEvent,
        *,
        idempotent_replay: bool,
    ) -> Dict[str, Any]:
        return {
            "user_id": int(event.user_id) if event.user_id is not None else None,
            "idempotent_replay": idempotent_replay,
            "account_created": False,
            "existing_user": event.user_id is not None,
            "setup_email_queued": False,
        }

    @staticmethod
    def _get_existing_event(
        db: Session,
        *,
        entry_id: str,
    ) -> AdvisorIntakeWebhookEvent | None:
        return (
            db.query(AdvisorIntakeWebhookEvent)
            .filter(
                AdvisorIntakeWebhookEvent.provider == AdvisorIntakeWebhookService.PROVIDER,
                AdvisorIntakeWebhookEvent.external_entry_id == entry_id,
            )
            .first()
        )

    @staticmethod
    def _persist_existing_user_after_email_race(
        db: Session,
        *,
        submission: AdvisorIntakeSubmission,
        payload_hash: str,
    ) -> Dict[str, Any]:
        existing_user = AuthService._find_user_by_email(db, submission.email)
        if existing_user is None or existing_user.role != "advisor" or not existing_user.is_active:
            raise HTTPException(status_code=500, detail="Failed to process advisor intake submission")

        event = AdvisorIntakeWebhookEvent(
            provider=AdvisorIntakeWebhookService.PROVIDER,
            external_entry_id=submission.entry_id,
            payload_hash=payload_hash,
            email=submission.email,
            status="existing_advisor",
            status_reason=AdvisorIntakeWebhookService._build_status_reason(submission),
            user=existing_user,
        )
        try:
            db.add(event)
            db.commit()
            db.refresh(event)
        except IntegrityError as exc:
            db.rollback()
            if AdvisorIntakeWebhookService._is_duplicate_entry_integrity_error(exc):
                replay = AdvisorIntakeWebhookService._get_existing_event(
                    db,
                    entry_id=submission.entry_id,
                )
                if replay is not None:
                    return AdvisorIntakeWebhookService._result_from_event(replay, idempotent_replay=True)
            logger.error("Advisor intake event insert failed after email race: %s", exc)
            raise HTTPException(status_code=500, detail="Failed to process advisor intake submission")

        return AdvisorIntakeWebhookService._result_from_event(event, idempotent_replay=False)

    @staticmethod
    def _build_status_reason(submission: AdvisorIntakeSubmission) -> Optional[str]:
        details = {
            "company": submission.company,
            "state": submission.state,
            "notes": submission.notes,
        }
        filtered = {key: value for key, value in details.items() if value}
        if not filtered:
            return None
        return json.dumps(filtered, sort_keys=True)

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
        has_table_marker = "advisor_intake_webhook_events" in details
        has_constraint_marker = "uq_advisor_intake_webhook_events_provider_entry" in details
        return has_duplicate_marker and (has_table_marker or has_constraint_marker)

    @staticmethod
    def _extract_entry_id(payload: Dict[str, Any]) -> str:
        candidates: list[Any] = [
            payload.get("entry_id"),
            payload.get("entryId"),
            payload.get("submission_id"),
            payload.get("submissionId"),
            payload.get("id"),
        ]
        entry = payload.get("entry")
        if isinstance(entry, dict):
            candidates.extend([entry.get("id"), entry.get("entry_id"), entry.get("submission_id")])
        form = payload.get("form")
        if isinstance(form, dict):
            candidates.extend([form.get("submission_id"), form.get("id")])

        for value in candidates:
            clean = str(value or "").strip()
            if clean:
                return clean
        raise HTTPException(status_code=400, detail="Missing advisor intake entry ID")

    @staticmethod
    def _collect_answers(payload: Dict[str, Any]) -> Dict[str, Any]:
        answers: Dict[str, Any] = {}
        for container_key in ("fields", "form_fields", "all_fields", "data"):
            AdvisorIntakeWebhookService._collect_field_container_answers(answers, payload.get(container_key))

        entry = payload.get("entry")
        if isinstance(entry, dict):
            for container_key in ("fields", "form_fields", "all_fields", "data"):
                AdvisorIntakeWebhookService._collect_field_container_answers(answers, entry.get(container_key))

        for key, value in payload.items():
            key_clean = AdvisorIntakeWebhookService._canonicalize_key(key)
            if key_clean in _META_KEYS:
                continue
            AdvisorIntakeWebhookService._add_answer(answers, key, value)
        return answers

    @staticmethod
    def _collect_field_container_answers(answers: Dict[str, Any], fields: Any) -> None:
        if isinstance(fields, str):
            clean = fields.strip()
            if clean.startswith("{") or clean.startswith("["):
                try:
                    fields = json.loads(clean)
                except Exception:
                    return

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
                        extracted_value = value.get("raw_value") or value.get("text")
                    AdvisorIntakeWebhookService._add_answer(answers, label, extracted_value)
                else:
                    AdvisorIntakeWebhookService._add_answer(answers, str(key), value)
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
                    extracted_value = value.get("raw_value") or value.get("text")
                AdvisorIntakeWebhookService._add_answer(answers, label, extracted_value)

    @staticmethod
    def _add_answer(answers: Dict[str, Any], key: Any, value: Any) -> None:
        canonical = AdvisorIntakeWebhookService._canonicalize_key(key)
        if not canonical or value is None:
            return
        if canonical not in answers:
            answers[canonical] = value

    @staticmethod
    def _find_answer(answers: Dict[str, Any], aliases: Iterable[str]) -> Any:
        canonical_aliases = [AdvisorIntakeWebhookService._canonicalize_key(alias) for alias in aliases]
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
                AdvisorIntakeWebhookService._to_clean_text(item)
                for item in value.values()
            ]
            joined = " ".join([part for part in parts if part])
            return joined or None
        if isinstance(value, list):
            parts = [
                AdvisorIntakeWebhookService._to_clean_text(item)
                for item in value
            ]
            joined = " ".join([part for part in parts if part])
            return joined or None
        clean = " ".join(str(value).split())
        return clean if clean else None

    @staticmethod
    def _normalize_email(value: Any) -> Optional[str]:
        clean = AdvisorIntakeWebhookService._to_clean_text(value)
        if not clean:
            return None
        try:
            return str(_EMAIL_ADAPTER.validate_python(clean)).strip().lower()
        except ValidationError:
            return None
