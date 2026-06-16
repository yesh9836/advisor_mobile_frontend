import csv
import io
import re
from pathlib import Path
from typing import Generator, List, Optional

from fastapi import HTTPException, UploadFile

from app.core.config import settings
from app.models.lead import Lead
from app.utils.csv_safety import neutralize_csv_row


LEAD_CSV_HEADERS = [
    "state_code",
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
]

LEAD_CSV_REQUIRED_VALUE_FIELDS = [
    "state_code",
    "mobile_phone",
]

JSON_LIST_FIELDS = {
    "main_purpose_for_investing",
    "current_investment_strategies",
}

LIST_SEPARATOR = " | "


def _canonicalize_csv_header(value: Optional[str]) -> str:
    normalized = str(value or "").strip().lower()
    normalized = re.sub(r"[\s\-]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized)
    return normalized.strip("_")


_CANONICAL_HEADER_TO_EXPECTED = {
    _canonicalize_csv_header(header): header for header in LEAD_CSV_HEADERS
}

def _join_json_list(value: Optional[object]) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return LIST_SEPARATOR.join(
            [str(item).strip() for item in value if item is not None and str(item).strip()]
        )
    if isinstance(value, str):
        return value
    return str(value)


def generate_leads_csv_stream(leads: List[Lead], prepend_message: str = "") -> Generator[str, None, None]:
    """
    Generator that yields CSV rows one by one.
    This prevents building a massive string in memory.
    """
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=LEAD_CSV_HEADERS)

    if prepend_message:
        yield prepend_message + "\n"

    writer.writeheader()
    yield buffer.getvalue()
    
    buffer.seek(0)
    buffer.truncate(0)

    for lead in leads:
        row = {}
        for field in LEAD_CSV_HEADERS:
            value = getattr(lead, field, None)
            if field in JSON_LIST_FIELDS:
                row[field] = _join_json_list(value)
            else:
                row[field] = "" if value is None else str(value)

        writer.writerow(neutralize_csv_row(row))
        yield buffer.getvalue()
        
        buffer.seek(0)
        buffer.truncate(0)


def parse_leads_csv(file: UploadFile) -> List[dict]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    try:
        file_ext = Path(file.filename).suffix.lower()
        if file_ext != ".csv":
            raise HTTPException(status_code=400, detail="Invalid file type. Expected .csv file")

        content_type = (file.content_type or "").lower().strip()
        media_type = content_type.split(";", 1)[0].strip()
        allowed_mimes = {mime.lower() for mime in settings.ALLOWED_CSV_MIME_TYPES}
        fallback_generic_mimes = {
            "application/octet-stream",
            "binary/octet-stream",
            "text/plain",
        }
        if (
            media_type
            and media_type not in allowed_mimes
            and media_type not in fallback_generic_mimes
            and "csv" not in media_type
        ):
            raise HTTPException(status_code=400, detail="Invalid CSV content type")

        raw = file.file.read()
        if not raw:
            raise HTTPException(status_code=400, detail="CSV file is empty")
        if len(raw) > settings.MAX_CSV_UPLOAD_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"CSV file too large. Limit: {settings.MAX_CSV_UPLOAD_SIZE / 1024 / 1024}MB",
            )

        text = raw.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))

        if reader.fieldnames is None:
            raise HTTPException(status_code=400, detail="CSV file missing header row")

        expected_headers = set(LEAD_CSV_HEADERS)
        observed_headers: set[str] = set()
        header_aliases: dict[str, str] = {}
        for header_name in reader.fieldnames:
            canonical_header = _canonicalize_csv_header(header_name)
            expected_header = _CANONICAL_HEADER_TO_EXPECTED.get(canonical_header)
            if not expected_header or expected_header in observed_headers:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid CSV headers.",
                )
            observed_headers.add(expected_header)
            header_aliases[expected_header] = str(header_name)

        if observed_headers != expected_headers:
            raise HTTPException(
                status_code=400,
                detail="Invalid CSV headers.",
            )

        rows: List[dict] = []
        for row in reader:
            if row is None:
                continue
            parsed = {}
            for field in LEAD_CSV_HEADERS:
                raw_value = row.get(header_aliases[field], "")
                if raw_value is None:
                    raw_value = ""

                value = raw_value.strip()

                if field in JSON_LIST_FIELDS:
                    parsed[field] = (
                        [v.strip() for v in value.split(LIST_SEPARATOR.strip()) if v.strip()]
                        if value else None
                    )
                else:
                    parsed[field] = value if value else None
            rows.append(parsed)

        return rows
    finally:
        try:
            file.file.seek(0)
        except Exception:
            pass
