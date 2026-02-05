import csv
import io
from typing import List, Optional, Generator, Union

from fastapi import HTTPException, UploadFile

from app.models.lead import Lead


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

JSON_LIST_FIELDS = {
    "main_purpose_for_investing",
    "current_investment_strategies",
}

LIST_SEPARATOR = " | "

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

    # 1. Yield Prepend Message (if any)
    if prepend_message:
        yield prepend_message + "\n"

    # 2. Write Header
    writer.writeheader()
    yield buffer.getvalue()
    
    # Clear buffer
    buffer.seek(0)
    buffer.truncate(0)

    # 3. Write Rows
    for lead in leads:
        row = {}
        for field in LEAD_CSV_HEADERS:
            value = getattr(lead, field, None)
            if field in JSON_LIST_FIELDS:
                row[field] = _join_json_list(value)
            else:
                row[field] = "" if value is None else str(value)
        
        writer.writerow(row)
        yield buffer.getvalue()
        
        # Clear buffer for next row
        buffer.seek(0)
        buffer.truncate(0)


def parse_leads_csv(file: UploadFile) -> List[dict]:
    """
    Parse uploaded CSV file into list of dicts.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    try:
        raw = file.file.read()
        if not raw:
            raise HTTPException(status_code=400, detail="CSV file is empty")

        text = raw.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))

        if reader.fieldnames is None:
            raise HTTPException(status_code=400, detail="CSV file missing header row")

        fieldnames = [name.strip() for name in reader.fieldnames]
        if fieldnames != LEAD_CSV_HEADERS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid CSV headers.",
            )

        rows: List[dict] = []
        for row in reader:
            if row is None:
                continue
            parsed = {}
            for field in LEAD_CSV_HEADERS:
                raw_value = row.get(field, "")
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
