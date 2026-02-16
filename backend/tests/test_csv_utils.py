import csv
import io

import pytest
from fastapi import HTTPException
from starlette.datastructures import UploadFile

from app.models.lead import Lead
from app.utils.csv_generator import LEAD_CSV_HEADERS, generate_leads_csv_stream, parse_leads_csv


@pytest.mark.unit
def test_parse_leads_csv_valid_payload():
    row = {header: "" for header in LEAD_CSV_HEADERS}
    row["state_code"] = "CA"
    row["mobile_phone"] = "555-CSV-1001"
    row["first_name"] = "CSV"
    row["main_purpose_for_investing"] = "income | growth"

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=LEAD_CSV_HEADERS)
    writer.writeheader()
    writer.writerow(row)

    upload = UploadFile(filename="leads.csv", file=io.BytesIO(buffer.getvalue().encode("utf-8")))
    parsed = parse_leads_csv(upload)

    assert len(parsed) == 1
    assert parsed[0]["state_code"] == "CA"
    assert parsed[0]["mobile_phone"] == "555-CSV-1001"
    assert parsed[0]["main_purpose_for_investing"] == ["income", "growth"]


@pytest.mark.unit
def test_parse_leads_csv_invalid_header_raises():
    payload = "bad,header\n1,2\n"
    upload = UploadFile(filename="bad.csv", file=io.BytesIO(payload.encode("utf-8")))

    with pytest.raises(HTTPException) as exc_info:
        parse_leads_csv(upload)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Invalid CSV headers."


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
