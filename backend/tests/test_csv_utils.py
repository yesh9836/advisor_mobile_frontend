import csv
import io

import pytest
from fastapi import HTTPException
from starlette.datastructures import UploadFile

from app.core.config import settings
from app.models.lead import Lead
from app.utils.csv_generator import LEAD_CSV_HEADERS, generate_leads_csv_stream, parse_leads_csv


def _build_csv_bytes(*, fieldnames: list[str], row: dict[str, str]) -> bytes:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerow(row)
    return buffer.getvalue().encode("utf-8")


def _build_valid_csv_bytes() -> bytes:
    row = {header: "" for header in LEAD_CSV_HEADERS}
    row["state_code"] = "CA"
    row["mobile_phone"] = "555-CSV-1001"
    row["first_name"] = "CSV"
    row["main_purpose_for_investing"] = "income | growth"
    return _build_csv_bytes(fieldnames=LEAD_CSV_HEADERS, row=row)


def _build_upload_file(
    *,
    payload: bytes,
    filename: str = "leads.csv",
    content_type: str | None = None,
) -> UploadFile:
    headers = {"content-type": content_type} if content_type is not None else None
    return UploadFile(
        file=io.BytesIO(payload),
        filename=filename,
        headers=headers,
    )


@pytest.mark.unit
def test_parse_leads_csv_valid_payload():
    upload = _build_upload_file(payload=_build_valid_csv_bytes(), filename="leads.csv")
    parsed = parse_leads_csv(upload)

    assert len(parsed) == 1
    assert parsed[0]["state_code"] == "CA"
    assert parsed[0]["mobile_phone"] == "555-CSV-1001"
    assert parsed[0]["main_purpose_for_investing"] == ["income", "growth"]


@pytest.mark.unit
def test_parse_leads_csv_accepts_reordered_headers():
    reordered_headers = list(reversed(LEAD_CSV_HEADERS))
    row = {header: "" for header in reordered_headers}
    row["state_code"] = "NV"
    row["mobile_phone"] = "555-CSV-2002"
    row["first_name"] = "Reordered"
    payload = _build_csv_bytes(fieldnames=reordered_headers, row=row)
    upload = _build_upload_file(payload=payload, filename="reordered.csv")

    parsed = parse_leads_csv(upload)
    assert len(parsed) == 1
    assert parsed[0]["state_code"] == "NV"
    assert parsed[0]["mobile_phone"] == "555-CSV-2002"
    assert parsed[0]["first_name"] == "Reordered"


@pytest.mark.unit
def test_parse_leads_csv_accepts_case_and_spacing_header_variants():
    varied_headers = [header.replace("_", " ").title() for header in LEAD_CSV_HEADERS]
    row = {header: "" for header in varied_headers}
    row["State Code"] = "TX"
    row["Mobile Phone"] = "555-CSV-3003"
    row["Main Purpose For Investing"] = "income | growth"
    payload = _build_csv_bytes(fieldnames=varied_headers, row=row)
    upload = _build_upload_file(payload=payload, filename="variant-headers.csv")

    parsed = parse_leads_csv(upload)
    assert len(parsed) == 1
    assert parsed[0]["state_code"] == "TX"
    assert parsed[0]["mobile_phone"] == "555-CSV-3003"
    assert parsed[0]["main_purpose_for_investing"] == ["income", "growth"]


@pytest.mark.unit
def test_parse_leads_csv_invalid_header_raises():
    payload = "bad,header\n1,2\n"
    upload = _build_upload_file(payload=payload.encode("utf-8"), filename="bad.csv")

    with pytest.raises(HTTPException) as exc_info:
        parse_leads_csv(upload)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Invalid CSV headers."


@pytest.mark.unit
def test_parse_leads_csv_rejects_non_csv_extension():
    upload = _build_upload_file(payload=_build_valid_csv_bytes(), filename="leads.txt")

    with pytest.raises(HTTPException) as exc_info:
        parse_leads_csv(upload)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Invalid file type. Expected .csv file"


@pytest.mark.unit
def test_parse_leads_csv_accepts_content_type_with_charset_parameter():
    upload = _build_upload_file(
        payload=_build_valid_csv_bytes(),
        filename="leads.csv",
        content_type="text/csv; charset=utf-8",
    )

    parsed = parse_leads_csv(upload)
    assert len(parsed) == 1


@pytest.mark.unit
def test_parse_leads_csv_accepts_generic_octet_stream_content_type():
    upload = _build_upload_file(
        payload=_build_valid_csv_bytes(),
        filename="leads.csv",
        content_type="application/octet-stream",
    )

    parsed = parse_leads_csv(upload)
    assert len(parsed) == 1


@pytest.mark.unit
def test_parse_leads_csv_rejects_non_csv_content_type_when_provided():
    upload = _build_upload_file(
        payload=_build_valid_csv_bytes(),
        filename="leads.csv",
        content_type="application/json",
    )

    with pytest.raises(HTTPException) as exc_info:
        parse_leads_csv(upload)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Invalid CSV content type"


@pytest.mark.unit
def test_parse_leads_csv_rejects_empty_payload():
    upload = _build_upload_file(payload=b"", filename="leads.csv")

    with pytest.raises(HTTPException) as exc_info:
        parse_leads_csv(upload)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "CSV file is empty"


@pytest.mark.unit
def test_parse_leads_csv_allows_size_exactly_at_limit(monkeypatch: pytest.MonkeyPatch):
    payload = _build_valid_csv_bytes()
    monkeypatch.setattr(settings, "MAX_CSV_UPLOAD_SIZE", len(payload))
    upload = _build_upload_file(payload=payload, filename="leads.csv")

    parsed = parse_leads_csv(upload)
    assert len(parsed) == 1


@pytest.mark.unit
def test_parse_leads_csv_rejects_payload_over_size_limit(monkeypatch: pytest.MonkeyPatch):
    payload = _build_valid_csv_bytes()
    monkeypatch.setattr(settings, "MAX_CSV_UPLOAD_SIZE", len(payload) - 1)
    upload = _build_upload_file(payload=payload, filename="leads.csv")

    with pytest.raises(HTTPException) as exc_info:
        parse_leads_csv(upload)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == (
        f"CSV file too large. Limit: {settings.MAX_CSV_UPLOAD_SIZE / 1024 / 1024}MB"
    )


@pytest.mark.unit
def test_generate_leads_csv_stream_includes_header_and_rows():
    lead = Lead(
        state_code="CA",
        mobile_phone="555-CSV-2001",
        first_name="Generator",
        last_name="Test",
        source="manual_entry",
        main_purpose_for_investing=["income", "stability"],
    )

    content = "".join(generate_leads_csv_stream([lead]))
    assert "state_code" in content
    assert "Generator" in content
    assert "income | stability" in content
