import csv
import io
from datetime import datetime, timedelta, timezone

import pytest

from app.models.audit_log import AuditLog
from app.models.lead import Lead, LeadDownload, LeadOutcome, LeadOwnership
from app.models.purchase import LeadCreditLedger, LeadPurchase
from app.utils.csv_generator import LEAD_CSV_HEADERS


def _create_admin_and_headers(user_factory, auth_headers):
    admin = user_factory(
        role="admin",
        password="AdminPass123!",
        email="admin.leads@example.com",
        name="Admin User",
    )
    headers = auth_headers(admin.email, "AdminPass123!")
    return admin, headers


def _create_advisor_with_access(
    user_factory,
    license_factory,
    plan_factory,
    purchase_factory,
    auth_headers,
):
    advisor = user_factory(
        role="advisor",
        password="AdvisorPass123!",
        email="advisor.leads@example.com",
        name="Advisor User",
    )
    plan = plan_factory(state_limit=1, daily_download_limit=10)
    license_factory(user_id=advisor.id, state="CA", status="verified")
    purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        credits_total=50,
        credits_remaining=50,
        status="completed",
    )
    headers = auth_headers(advisor.email, "AdvisorPass123!")
    return advisor, plan, headers


def _create_advisor_with_purchase_access(
    user_factory,
    license_factory,
    plan_factory,
    purchase_factory,
    auth_headers,
):
    advisor = user_factory(
        role="advisor",
        password="AdvisorPurchase123!",
        email="advisor.purchase.leads@example.com",
        name="Advisor Purchase User",
    )
    plan = plan_factory(state_limit=1, daily_download_limit=10)
    license_factory(user_id=advisor.id, state="CA", status="verified")
    purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        credits_total=3,
        credits_remaining=3,
    )
    headers = auth_headers(advisor.email, "AdvisorPurchase123!")
    return advisor, plan, headers


def _build_leads_csv_file(rows):
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=LEAD_CSV_HEADERS)
    writer.writeheader()
    for row in rows:
        writer.writerow({header: row.get(header, "") for header in LEAD_CSV_HEADERS})
    return ("leads.csv", buffer.getvalue().encode("utf-8"), "text/csv")


@pytest.mark.integration
def test_list_available_leads_filters_to_verified_states(
    client,
    user_factory,
    lead_factory,
    license_factory,
    plan_factory,
    purchase_factory,
    auth_headers,
):
    advisor, _, headers = _create_advisor_with_access(
        user_factory,
        license_factory,
        plan_factory,
        purchase_factory,
        auth_headers,
    )
    _ = advisor  # explicit for readability

    lead_factory(state_code="CA", mobile_phone="555-CA-1001", first_name="Cali", last_name="One")
    lead_factory(state_code="CA", mobile_phone="555-CA-1002", first_name="Cali", last_name="Two")
    lead_factory(state_code="NY", mobile_phone="555-NY-1001", first_name="Nora", last_name="York")

    response = client.get("/api/v1/leads/", headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert {item["state_code"] for item in data["items"]} == {"CA"}
    assert all("source" in item for item in data["items"])
    assert {item["source"] for item in data["items"]} == {"manual_entry"}


@pytest.mark.integration
def test_list_leads_redacts_pre_delivery_unsold_pii(
    client,
    db,
    user_factory,
    lead_factory,
    license_factory,
    plan_factory,
    purchase_factory,
    auth_headers,
):
    advisor, _, headers = _create_advisor_with_access(
        user_factory,
        license_factory,
        plan_factory,
        purchase_factory,
        auth_headers,
    )

    delivered_lead = lead_factory(
        state_code="CA",
        mobile_phone="555-PII-DELIV-01",
        first_name="Delivered",
        last_name="Lead",
    )
    unsold_lead = lead_factory(
        state_code="CA",
        mobile_phone="555-PII-UNSOLD-01",
        first_name="Unsold",
        last_name="Lead",
    )
    delivered_lead.most_important_retirement_activity = "Travel"
    unsold_lead.most_important_retirement_activity = "Golf"
    db.add(delivered_lead)
    db.add(unsold_lead)
    db.add(
        LeadDownload(
            user_id=advisor.id,
            lead_id=delivered_lead.id,
            purchase_id=None,
            csv_batch_id="batch_redaction_check",
        )
    )
    db.commit()

    response = client.get("/api/v1/leads/?delivery_status=all", headers=headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["total"] == 2

    items_by_id = {item["id"]: item for item in payload["items"]}
    delivered_item = items_by_id[delivered_lead.id]
    unsold_item = items_by_id[unsold_lead.id]

    assert delivered_item["pii_unlocked"] is True
    assert delivered_item["first_name"] == "Delivered"
    assert delivered_item["last_name"] == "Lead"
    assert delivered_item["mobile_phone"] == "555-PII-DELIV-01"
    assert delivered_item["most_important_retirement_activity"] == "Travel"

    assert unsold_item["pii_unlocked"] is False
    assert unsold_item["first_name"] is None
    assert unsold_item["last_name"] is None
    assert unsold_item["mobile_phone"] is None
    assert unsold_item["most_important_retirement_activity"] is None
    assert unsold_item["is_downloaded"] is False


@pytest.mark.integration
def test_list_leads_blocks_undelivered_unsold_name_and_phone_search(
    client,
    db,
    user_factory,
    lead_factory,
    license_factory,
    plan_factory,
    purchase_factory,
    auth_headers,
):
    advisor, _, headers = _create_advisor_with_access(
        user_factory,
        license_factory,
        plan_factory,
        purchase_factory,
        auth_headers,
    )

    delivered_casey = lead_factory(
        state_code="CA",
        mobile_phone="555-CA-SRCH-0001",
        first_name="Casey",
        last_name="Delivered",
    )
    lead_factory(
        state_code="CA",
        mobile_phone="555-CA-SRCH-9012",
        first_name="Casey",
        last_name="Unsold",
    )
    db.add(
        LeadDownload(
            user_id=advisor.id,
            lead_id=delivered_casey.id,
            purchase_id=None,
            csv_batch_id="batch_search_gate",
        )
    )
    db.commit()

    available_name_response = client.get(
        "/api/v1/leads/?delivery_status=available&search=casey",
        headers=headers,
    )
    assert available_name_response.status_code == 200, available_name_response.text
    assert available_name_response.json()["total"] == 0

    available_phone_response = client.get(
        "/api/v1/leads/?delivery_status=available&search=9012",
        headers=headers,
    )
    assert available_phone_response.status_code == 200, available_phone_response.text
    assert available_phone_response.json()["total"] == 0

    all_response = client.get("/api/v1/leads/?delivery_status=all&search=casey", headers=headers)
    assert all_response.status_code == 200, all_response.text
    all_payload = all_response.json()
    assert all_payload["total"] == 1
    assert all_payload["items"][0]["id"] == delivered_casey.id

    delivered_response = client.get(
        "/api/v1/leads/?delivery_status=delivered&search=casey",
        headers=headers,
    )
    assert delivered_response.status_code == 200, delivered_response.text
    delivered_payload = delivered_response.json()
    assert delivered_payload["total"] == 1
    assert delivered_payload["items"][0]["id"] == delivered_casey.id


@pytest.mark.integration
def test_save_outcome_rejects_lead_outside_licensed_states(
    client,
    user_factory,
    lead_factory,
    license_factory,
    plan_factory,
    purchase_factory,
    auth_headers,
):
    _advisor, _, headers = _create_advisor_with_access(
        user_factory,
        license_factory,
        plan_factory,
        purchase_factory,
        auth_headers,
    )
    ny_lead = lead_factory(state_code="NY", mobile_phone="555-NY-2001")

    response = client.put(
        f"/api/v1/leads/{ny_lead.id}/outcome",
        headers=headers,
        json={"status": "contacted", "notes": "Should not be allowed"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Lead not found"


@pytest.mark.integration
def test_save_outcome_rejects_licensed_state_lead_when_not_delivered_or_owned(
    client,
    user_factory,
    lead_factory,
    license_factory,
    plan_factory,
    purchase_factory,
    auth_headers,
):
    _advisor, _, headers = _create_advisor_with_access(
        user_factory,
        license_factory,
        plan_factory,
        purchase_factory,
        auth_headers,
    )
    ca_lead = lead_factory(state_code="CA", mobile_phone="555-CA-2002")

    response = client.put(
        f"/api/v1/leads/{ca_lead.id}/outcome",
        headers=headers,
        json={"status": "contacted", "notes": "Should still be denied"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Lead not found"


@pytest.mark.integration
def test_save_outcome_allows_delivered_lead(
    client,
    db,
    user_factory,
    lead_factory,
    license_factory,
    plan_factory,
    purchase_factory,
    auth_headers,
):
    advisor, _, headers = _create_advisor_with_access(
        user_factory,
        license_factory,
        plan_factory,
        purchase_factory,
        auth_headers,
    )
    ca_lead = lead_factory(state_code="CA", mobile_phone="555-CA-2003")
    db.add(
        LeadDownload(
            user_id=advisor.id,
            lead_id=ca_lead.id,
            csv_batch_id="batch_outcome_delivered_access",
        )
    )
    db.commit()

    response = client.put(
        f"/api/v1/leads/{ca_lead.id}/outcome",
        headers=headers,
        json={"status": "contacted", "notes": "Delivered lead"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "contacted"
    assert data["notes"] == "Delivered lead"


@pytest.mark.integration
def test_save_outcome_allows_owned_lead_before_download(
    client,
    db,
    user_factory,
    lead_factory,
    license_factory,
    plan_factory,
    purchase_factory,
    auth_headers,
):
    advisor, _, headers = _create_advisor_with_access(
        user_factory,
        license_factory,
        plan_factory,
        purchase_factory,
        auth_headers,
    )
    ca_lead = lead_factory(state_code="CA", mobile_phone="555-CA-2004")
    db.add(
        LeadOwnership(
            user_id=advisor.id,
            lead_id=ca_lead.id,
        )
    )
    db.commit()

    response = client.put(
        f"/api/v1/leads/{ca_lead.id}/outcome",
        headers=headers,
        json={"status": "appointment_set", "notes": "Owned lead"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "appointment_set"
    assert data["notes"] == "Owned lead"


@pytest.mark.integration
def test_download_csv_marks_leads_as_downloaded_in_default_list(
    client,
    db,
    user_factory,
    lead_factory,
    license_factory,
    plan_factory,
    purchase_factory,
    auth_headers,
):
    _advisor, _, headers = _create_advisor_with_access(
        user_factory,
        license_factory,
        plan_factory,
        purchase_factory,
        auth_headers,
    )

    lead_factory(state_code="CA", mobile_phone="555-CA-3001", first_name="Download", last_name="One")
    lead_factory(state_code="CA", mobile_phone="555-CA-3002", first_name="Download", last_name="Two")

    download_response = client.post("/api/v1/leads/download", headers=headers)
    assert download_response.status_code == 200, download_response.text
    assert "state_code" in download_response.text
    assert "Download" in download_response.text

    download_count = db.query(LeadDownload).count()
    assert download_count == 2

    list_response = client.get("/api/v1/leads/", headers=headers)
    assert list_response.status_code == 200, list_response.text
    payload = list_response.json()
    assert payload["total"] == 2
    assert len(payload["items"]) == 2
    assert all(item["is_downloaded"] is True for item in payload["items"])
    assert all(item["downloaded_at"] is not None for item in payload["items"])


@pytest.mark.integration
def test_download_csv_consumes_purchase_credits_and_tags_downloads(
    client,
    db,
    user_factory,
    lead_factory,
    license_factory,
    plan_factory,
    purchase_factory,
    auth_headers,
):
    advisor, _plan, headers = _create_advisor_with_purchase_access(
        user_factory,
        license_factory,
        plan_factory,
        purchase_factory,
        auth_headers,
    )

    lead_factory(state_code="CA", mobile_phone="555-CA-3011", first_name="Credit", last_name="One")
    lead_factory(state_code="CA", mobile_phone="555-CA-3012", first_name="Credit", last_name="Two")

    download_response = client.post("/api/v1/leads/download", headers=headers)
    assert download_response.status_code == 200, download_response.text

    downloads = db.query(LeadDownload).filter(LeadDownload.user_id == advisor.id).all()
    assert len(downloads) == 2
    assert all(item.purchase_id is not None for item in downloads)

    ledger_consumed_entries = (
        db.query(LeadCreditLedger)
        .filter(
            LeadCreditLedger.user_id == advisor.id,
            LeadCreditLedger.movement_type == "lead_consumed",
        )
        .all()
    )
    assert len(ledger_consumed_entries) == 2
    assert sum(entry.credits_delta for entry in ledger_consumed_entries) == -2


@pytest.mark.integration
def test_download_delivered_csv_allows_redownload_after_credits_exhausted(
    client,
    db,
    user_factory,
    lead_factory,
    license_factory,
    plan_factory,
    purchase_factory,
    auth_headers,
):
    advisor, plan, headers = _create_advisor_with_purchase_access(
        user_factory,
        license_factory,
        plan_factory,
        purchase_factory,
        auth_headers,
    )
    purchase = (
        db.query(LeadPurchase)
        .filter(LeadPurchase.user_id == advisor.id, LeadPurchase.package_id == plan.id)
        .order_by(LeadPurchase.id.desc())
        .first()
    )
    assert purchase is not None
    purchase.credits_total = 1
    purchase.credits_remaining = 1
    db.add(purchase)
    db.commit()

    lead_factory(state_code="CA", mobile_phone="555-CA-REDL-0001", first_name="Repeat", last_name="Lead")

    first_download = client.post("/api/v1/leads/download", headers=headers)
    assert first_download.status_code == 200, first_download.text

    second_new_download = client.post("/api/v1/leads/download", headers=headers)
    assert second_new_download.status_code == 200, second_new_download.text
    assert "555-CA-REDL-0001" in second_new_download.text

    delivered_download = client.post("/api/v1/leads/download/delivered", headers=headers)
    assert delivered_download.status_code == 200, delivered_download.text
    assert "Previously delivered leads export." in delivered_download.text
    assert "555-CA-REDL-0001" in delivered_download.text


@pytest.mark.integration
def test_download_delivered_csv_deduplicates_old_leads_after_new_package_delivery(
    client,
    db,
    user_factory,
    lead_factory,
    license_factory,
    plan_factory,
    purchase_factory,
    auth_headers,
):
    advisor, plan, headers = _create_advisor_with_purchase_access(
        user_factory,
        license_factory,
        plan_factory,
        purchase_factory,
        auth_headers,
    )
    first_purchase = (
        db.query(LeadPurchase)
        .filter(LeadPurchase.user_id == advisor.id, LeadPurchase.package_id == plan.id)
        .order_by(LeadPurchase.id.asc())
        .first()
    )
    assert first_purchase is not None

    first_lead = lead_factory(state_code="CA", mobile_phone="555-OWN-REDL-1001")
    db.add(
        LeadOwnership(
            user_id=advisor.id,
            lead_id=first_lead.id,
            purchase_id=first_purchase.id,
        )
    )
    db.commit()

    first_download = client.post("/api/v1/leads/download", headers=headers)
    assert first_download.status_code == 200, first_download.text
    assert "555-OWN-REDL-1001" in first_download.text

    second_purchase = purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        credits_total=2,
        credits_remaining=2,
        status="completed",
    )
    second_lead = lead_factory(state_code="CA", mobile_phone="555-OWN-REDL-1002")
    db.add(
        LeadOwnership(
            user_id=advisor.id,
            lead_id=second_lead.id,
            purchase_id=second_purchase.id,
        )
    )
    db.commit()

    second_download = client.post("/api/v1/leads/download", headers=headers)
    assert second_download.status_code == 200, second_download.text
    assert "555-OWN-REDL-1001" in second_download.text
    assert "555-OWN-REDL-1002" in second_download.text

    download_rows = (
        db.query(LeadDownload)
        .filter(LeadDownload.user_id == advisor.id, LeadDownload.lead_id == first_lead.id)
        .all()
    )
    assert len(download_rows) == 2

    delivered_download = client.post("/api/v1/leads/download/delivered", headers=headers)
    assert delivered_download.status_code == 200, delivered_download.text
    assert "Previously delivered leads export." in delivered_download.text
    assert delivered_download.text.count("555-OWN-REDL-1001") == 1
    assert delivered_download.text.count("555-OWN-REDL-1002") == 1


@pytest.mark.integration
def test_list_leads_hides_unsold_inventory_when_purchase_credits_exhausted(
    client,
    db,
    user_factory,
    lead_factory,
    license_factory,
    plan_factory,
    purchase_factory,
    auth_headers,
):
    advisor, plan, headers = _create_advisor_with_purchase_access(
        user_factory,
        license_factory,
        plan_factory,
        purchase_factory,
        auth_headers,
    )
    purchase = (
        db.query(LeadPurchase)
        .filter(LeadPurchase.user_id == advisor.id, LeadPurchase.package_id == plan.id)
        .order_by(LeadPurchase.id.desc())
        .first()
    )
    assert purchase is not None
    purchase.credits_total = 1
    purchase.credits_remaining = 1
    db.add(purchase)
    db.commit()

    delivered_lead = lead_factory(
        state_code="CA",
        mobile_phone="555-CA-LIST-EXH-0001",
        first_name="Delivered",
        last_name="Only",
    )
    first_download = client.post("/api/v1/leads/download", headers=headers)
    assert first_download.status_code == 200, first_download.text

    lead_factory(
        state_code="CA",
        mobile_phone="555-CA-LIST-EXH-0002",
        first_name="Unsold",
        last_name="Hidden",
    )

    all_response = client.get("/api/v1/leads/?delivery_status=all", headers=headers)
    assert all_response.status_code == 200, all_response.text
    all_payload = all_response.json()
    assert all_payload["total"] == 1
    assert len(all_payload["items"]) == 1
    assert all_payload["items"][0]["id"] == delivered_lead.id

    available_response = client.get("/api/v1/leads/?delivery_status=available", headers=headers)
    assert available_response.status_code == 200, available_response.text
    available_payload = available_response.json()
    assert available_payload["total"] == 0
    assert available_payload["items"] == []

    delivered_response = client.get("/api/v1/leads/?delivery_status=delivered", headers=headers)
    assert delivered_response.status_code == 200, delivered_response.text
    delivered_payload = delivered_response.json()
    assert delivered_payload["total"] == 1
    assert len(delivered_payload["items"]) == 1
    assert delivered_payload["items"][0]["id"] == delivered_lead.id
    assert delivered_payload["items"][0]["is_downloaded"] is True


@pytest.mark.integration
def test_global_single_sale_blocks_second_advisor_from_same_lead(
    client,
    db,
    user_factory,
    lead_factory,
    license_factory,
    plan_factory,
    purchase_factory,
    auth_headers,
):
    first_advisor, first_plan, first_headers = _create_advisor_with_purchase_access(
        user_factory,
        license_factory,
        plan_factory,
        purchase_factory,
        auth_headers,
    )
    first_purchase = (
        db.query(LeadPurchase)
        .filter(LeadPurchase.user_id == first_advisor.id)
        .order_by(LeadPurchase.id.desc())
        .first()
    )
    assert first_purchase is not None
    first_purchase.credits_total = 1
    first_purchase.credits_remaining = 1
    db.add(first_purchase)
    db.commit()

    second_advisor = user_factory(
        role="advisor",
        password="AdvisorSecond123!",
        email="advisor.second.leads@example.com",
        name="Advisor Second User",
    )
    license_factory(user_id=second_advisor.id, state="CA", status="verified")
    purchase_factory(
        user_id=second_advisor.id,
        package_id=first_plan.id,
        credits_total=3,
        credits_remaining=3,
    )
    second_headers = auth_headers(second_advisor.email, "AdvisorSecond123!")

    sold_lead = lead_factory(state_code="CA", mobile_phone="555-CA-3021", first_name="Sold", last_name="Lead")
    unsold_lead = lead_factory(state_code="CA", mobile_phone="555-CA-3022", first_name="Fresh", last_name="Lead")
    _ = sold_lead
    _ = unsold_lead

    first_download = client.post("/api/v1/leads/download", headers=first_headers)
    assert first_download.status_code == 200, first_download.text

    second_download = client.post("/api/v1/leads/download", headers=second_headers)
    assert second_download.status_code == 200, second_download.text

    first_user_downloads = (
        db.query(LeadDownload)
        .filter(LeadDownload.user_id == first_advisor.id)
        .all()
    )
    second_user_downloads = (
        db.query(LeadDownload)
        .filter(LeadDownload.user_id == second_advisor.id)
        .all()
    )
    assert len(first_user_downloads) == 1
    assert len(second_user_downloads) == 1
    assert second_user_downloads[0].lead_id != first_user_downloads[0].lead_id


@pytest.mark.integration
def test_download_csv_get_method_is_not_allowed(
    client,
    user_factory,
    lead_factory,
    license_factory,
    plan_factory,
    purchase_factory,
    auth_headers,
):
    _advisor, _, headers = _create_advisor_with_access(
        user_factory,
        license_factory,
        plan_factory,
        purchase_factory,
        auth_headers,
    )
    lead_factory(state_code="CA", mobile_phone="555-CA-3003", first_name="Method", last_name="Check")

    response = client.get("/api/v1/leads/download", headers=headers)
    assert response.status_code == 405, response.text


@pytest.mark.integration
def test_download_csv_post_requires_csrf_header(
    client,
    user_factory,
    lead_factory,
    license_factory,
    plan_factory,
    purchase_factory,
    auth_headers,
):
    _advisor, _, headers = _create_advisor_with_access(
        user_factory,
        license_factory,
        plan_factory,
        purchase_factory,
        auth_headers,
    )
    lead_factory(state_code="CA", mobile_phone="555-CA-3004", first_name="Csrf", last_name="Check")

    response = client.post(
        "/api/v1/leads/download",
        headers={"Cookie": headers["Cookie"]},
    )
    assert response.status_code == 403, response.text
    assert response.json()["detail"] == "CSRF token validation failed"


@pytest.mark.integration
def test_list_leads_delivery_status_filter_returns_expected_records(
    client,
    db,
    user_factory,
    lead_factory,
    license_factory,
    plan_factory,
    purchase_factory,
    auth_headers,
):
    advisor, _, headers = _create_advisor_with_access(
        user_factory,
        license_factory,
        plan_factory,
        purchase_factory,
        auth_headers,
    )

    lead_factory(state_code="CA", mobile_phone="555-CA-3501", first_name="Delivered", last_name="One")
    lead_factory(state_code="CA", mobile_phone="555-CA-3502", first_name="Delivered", last_name="Two")

    download_response = client.post("/api/v1/leads/download", headers=headers)
    assert download_response.status_code == 200, download_response.text

    purchase = (
        db.query(LeadPurchase)
        .filter(LeadPurchase.user_id == advisor.id)
        .order_by(LeadPurchase.id.desc())
        .first()
    )
    assert purchase is not None

    newly_received = lead_factory(state_code="CA", mobile_phone="555-CA-3503", first_name="Available", last_name="One")
    db.add(
        LeadOwnership(
            user_id=advisor.id,
            lead_id=newly_received.id,
            purchase_id=purchase.id,
        )
    )
    db.commit()

    all_response = client.get("/api/v1/leads/?delivery_status=all", headers=headers)
    assert all_response.status_code == 200, all_response.text
    all_payload = all_response.json()
    assert all_payload["total"] == 3

    available_response = client.get("/api/v1/leads/?delivery_status=available", headers=headers)
    assert available_response.status_code == 200, available_response.text
    available_payload = available_response.json()
    assert available_payload["total"] == 1
    assert available_payload["items"][0]["is_downloaded"] is False

    delivered_response = client.get("/api/v1/leads/?delivery_status=delivered", headers=headers)
    assert delivered_response.status_code == 200, delivered_response.text
    delivered_payload = delivered_response.json()
    assert delivered_payload["total"] == 2
    assert all(item["is_downloaded"] is True for item in delivered_payload["items"])


@pytest.mark.integration
def test_list_leads_search_filters_delivered_results(
    client,
    user_factory,
    lead_factory,
    license_factory,
    plan_factory,
    purchase_factory,
    auth_headers,
):
    _advisor, _, headers = _create_advisor_with_access(
        user_factory,
        license_factory,
        plan_factory,
        purchase_factory,
        auth_headers,
    )

    casey_lead = lead_factory(
        state_code="CA",
        mobile_phone="555-CA-SEARCH-001",
        first_name="Casey",
        last_name="Owned",
    )
    lead_factory(
        state_code="CA",
        mobile_phone="555-CA-SEARCH-002",
        first_name="Taylor",
        last_name="Owned",
    )

    download_response = client.post("/api/v1/leads/download", headers=headers)
    assert download_response.status_code == 200, download_response.text

    search_response = client.get(
        "/api/v1/leads/?delivery_status=delivered&search=casey",
        headers=headers,
    )
    assert search_response.status_code == 200, search_response.text
    payload = search_response.json()
    assert payload["total"] == 1
    assert len(payload["items"]) == 1
    assert payload["items"][0]["id"] == casey_lead.id


@pytest.mark.integration
def test_list_leads_outcome_status_filter_returns_expected_records(
    client,
    db,
    user_factory,
    lead_factory,
    license_factory,
    plan_factory,
    purchase_factory,
    auth_headers,
):
    advisor, _, headers = _create_advisor_with_access(
        user_factory,
        license_factory,
        plan_factory,
        purchase_factory,
        auth_headers,
    )

    contacted_lead = lead_factory(
        state_code="CA",
        mobile_phone="555-CA-3601",
        first_name="Contacted",
        last_name="Lead",
    )
    appointment_lead = lead_factory(
        state_code="CA",
        mobile_phone="555-CA-3602",
        first_name="Appointment",
        last_name="Lead",
    )
    explicit_new_lead = lead_factory(
        state_code="CA",
        mobile_phone="555-CA-3603",
        first_name="Explicit",
        last_name="New",
    )
    implicit_new_lead = lead_factory(
        state_code="CA",
        mobile_phone="555-CA-3604",
        first_name="Implicit",
        last_name="New",
    )
    db.add_all(
        [
            LeadOwnership(user_id=advisor.id, lead_id=contacted_lead.id),
            LeadOwnership(user_id=advisor.id, lead_id=appointment_lead.id),
            LeadOwnership(user_id=advisor.id, lead_id=explicit_new_lead.id),
            LeadOwnership(user_id=advisor.id, lead_id=implicit_new_lead.id),
        ]
    )
    db.commit()

    contacted_response = client.put(
        f"/api/v1/leads/{contacted_lead.id}/outcome",
        headers=headers,
        json={"status": "contacted", "notes": "Reached advisor"},
    )
    assert contacted_response.status_code == 200, contacted_response.text

    appointment_response = client.put(
        f"/api/v1/leads/{appointment_lead.id}/outcome",
        headers=headers,
        json={"status": "appointment_set", "notes": "Booked meeting"},
    )
    assert appointment_response.status_code == 200, appointment_response.text

    explicit_new_response = client.put(
        f"/api/v1/leads/{explicit_new_lead.id}/outcome",
        headers=headers,
        json={"status": "new", "notes": "Reset to new"},
    )
    assert explicit_new_response.status_code == 200, explicit_new_response.text

    all_response = client.get("/api/v1/leads/?outcome_status=all", headers=headers)
    assert all_response.status_code == 200, all_response.text
    assert all_response.json()["total"] == 4

    contacted_filter_response = client.get(
        "/api/v1/leads/?outcome_status=contacted",
        headers=headers,
    )
    assert contacted_filter_response.status_code == 200, contacted_filter_response.text
    contacted_payload = contacted_filter_response.json()
    assert contacted_payload["total"] == 1
    assert contacted_payload["items"][0]["id"] == contacted_lead.id
    assert contacted_payload["items"][0]["outcome_status"] == "contacted"

    appointment_filter_response = client.get(
        "/api/v1/leads/?outcome_status=appointment_set",
        headers=headers,
    )
    assert appointment_filter_response.status_code == 200, appointment_filter_response.text
    appointment_payload = appointment_filter_response.json()
    assert appointment_payload["total"] == 1
    assert appointment_payload["items"][0]["id"] == appointment_lead.id
    assert appointment_payload["items"][0]["outcome_status"] == "appointment_set"

    new_filter_response = client.get(
        "/api/v1/leads/?outcome_status=new",
        headers=headers,
    )
    assert new_filter_response.status_code == 200, new_filter_response.text
    new_payload = new_filter_response.json()
    assert new_payload["total"] == 2
    assert {item["id"] for item in new_payload["items"]} == {
        explicit_new_lead.id,
        implicit_new_lead.id,
    }


@pytest.mark.integration
def test_admin_can_create_lead_and_assigned_advisor_can_update_outcome(
    client,
    user_factory,
    license_factory,
    plan_factory,
    purchase_factory,
    auth_headers,
):
    _admin, admin_headers = _create_admin_and_headers(user_factory, auth_headers)
    _advisor, _, advisor_headers = _create_advisor_with_access(
        user_factory,
        license_factory,
        plan_factory,
        purchase_factory,
        auth_headers,
    )

    create_response = client.post(
        "/api/v1/leads/",
        headers=admin_headers,
        json={
            "state_code": "CA",
            "first_name": "Outcome",
            "last_name": "Target",
            "mobile_phone": "555-CA-4001",
        },
    )
    assert create_response.status_code == 201, create_response.text
    lead_id = create_response.json()["id"]

    outcome_response = client.put(
        f"/api/v1/leads/{lead_id}/outcome",
        headers=advisor_headers,
        json={"status": "appointment_set", "notes": "Meeting booked"},
    )
    assert outcome_response.status_code == 200, outcome_response.text
    data = outcome_response.json()
    assert data["status"] == "appointment_set"
    assert data["notes"] == "Meeting booked"


@pytest.mark.integration
def test_dashboard_summary_returns_expected_shape(
    client,
    user_factory,
    lead_factory,
    license_factory,
    plan_factory,
    purchase_factory,
    auth_headers,
):
    _advisor, _plan, headers = _create_advisor_with_access(
        user_factory,
        license_factory,
        plan_factory,
        purchase_factory,
        auth_headers,
    )
    lead_factory(state_code="CA", mobile_phone="555-CA-5001", first_name="Dash", last_name="One")

    response = client.get("/api/v1/leads/dashboard/summary", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert "leads_delivered_7_days" in body
    assert "appointments_set_7_days" in body
    assert "cost_per_appointment" in body
    assert body["settings"]["target_states"] == ["CA"]


@pytest.mark.integration
def test_dashboard_summary_delivered_counts_only_recent_assignments(
    client,
    db,
    user_factory,
    lead_factory,
    license_factory,
    plan_factory,
    purchase_factory,
    auth_headers,
):
    advisor, _plan, headers = _create_advisor_with_access(
        user_factory,
        license_factory,
        plan_factory,
        purchase_factory,
        auth_headers,
    )
    assigned_lead = lead_factory(
        state_code="CA",
        mobile_phone="555-CA-5101",
        first_name="Assigned",
        last_name="Lead",
    )
    lead_factory(
        state_code="CA",
        mobile_phone="555-CA-5102",
        first_name="Unassigned",
        last_name="Lead",
    )
    db.add(
        LeadOwnership(
            user_id=advisor.id,
            lead_id=assigned_lead.id,
            assigned_at=datetime.now(timezone.utc),
        )
    )
    db.commit()

    response = client.get("/api/v1/leads/dashboard/summary", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["leads_delivered_7_days"] == 1


@pytest.mark.integration
def test_dashboard_summary_delivered_excludes_assignments_older_than_7_days(
    client,
    db,
    user_factory,
    lead_factory,
    license_factory,
    plan_factory,
    purchase_factory,
    auth_headers,
):
    advisor, _plan, headers = _create_advisor_with_access(
        user_factory,
        license_factory,
        plan_factory,
        purchase_factory,
        auth_headers,
    )
    recent_lead = lead_factory(
        state_code="CA",
        mobile_phone="555-CA-5201",
        first_name="Recent",
        last_name="Lead",
    )
    old_lead = lead_factory(
        state_code="CA",
        mobile_phone="555-CA-5202",
        first_name="Old",
        last_name="Lead",
    )
    db.add(
        LeadOwnership(
            user_id=advisor.id,
            lead_id=recent_lead.id,
            assigned_at=datetime.now(timezone.utc),
        )
    )
    db.add(
        LeadOwnership(
            user_id=advisor.id,
            lead_id=old_lead.id,
            assigned_at=datetime.now(timezone.utc) - timedelta(days=8),
        )
    )
    db.commit()

    summary_response = client.get("/api/v1/leads/dashboard/summary", headers=headers)
    assert summary_response.status_code == 200, summary_response.text
    body = summary_response.json()
    assert body["leads_delivered_7_days"] == 1


@pytest.mark.integration
def test_dashboard_summary_counts_recent_assignments_across_owned_states(
    client,
    db,
    user_factory,
    lead_factory,
    license_factory,
    plan_factory,
    purchase_factory,
    auth_headers,
):
    advisor, _plan, headers = _create_advisor_with_access(
        user_factory,
        license_factory,
        plan_factory,
        purchase_factory,
        auth_headers,
    )

    ca_lead = lead_factory(state_code="CA", mobile_phone="555-CA-5301", first_name="Allowed", last_name="Lead")
    ny_lead = lead_factory(state_code="NY", mobile_phone="555-NY-5301", first_name="Blocked", last_name="Lead")

    db.add(
        LeadOwnership(
            user_id=advisor.id,
            lead_id=ca_lead.id,
            assigned_at=datetime.now(timezone.utc),
        )
    )
    db.add(
        LeadOwnership(
            user_id=advisor.id,
            lead_id=ny_lead.id,
            assigned_at=datetime.now(timezone.utc),
        )
    )
    db.commit()

    response = client.get("/api/v1/leads/dashboard/summary", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["settings"]["target_states"] == ["CA"]
    assert body["leads_delivered_7_days"] == 2


@pytest.mark.integration
def test_dashboard_summary_appointments_count_uses_recent_deliveries_not_outcome_update_time(
    client,
    db,
    user_factory,
    lead_factory,
    license_factory,
    plan_factory,
    purchase_factory,
    auth_headers,
):
    advisor, _plan, headers = _create_advisor_with_access(
        user_factory,
        license_factory,
        plan_factory,
        purchase_factory,
        auth_headers,
    )

    recent_appt_lead = lead_factory(
        state_code="CA",
        mobile_phone="555-CA-5401",
        first_name="Recent",
        last_name="Appointment",
    )
    recent_contacted_lead = lead_factory(
        state_code="CA",
        mobile_phone="555-CA-5402",
        first_name="Recent",
        last_name="Contacted",
    )
    old_delivery_appt_lead = lead_factory(
        state_code="CA",
        mobile_phone="555-CA-5403",
        first_name="Old",
        last_name="Delivery",
    )

    db.add(
        LeadOwnership(
            user_id=advisor.id,
            lead_id=recent_appt_lead.id,
            assigned_at=datetime.now(timezone.utc),
        )
    )
    db.add(
        LeadOwnership(
            user_id=advisor.id,
            lead_id=recent_contacted_lead.id,
            assigned_at=datetime.now(timezone.utc),
        )
    )
    db.add(
        LeadOwnership(
            user_id=advisor.id,
            lead_id=old_delivery_appt_lead.id,
            assigned_at=datetime.now(timezone.utc) - timedelta(days=8),
        )
    )

    db.add(
        LeadOutcome(
            user_id=advisor.id,
            lead_id=recent_appt_lead.id,
            status="appointment_set",
            notes="Set before this week window",
            updated_at=datetime.now(timezone.utc) - timedelta(days=30),
        )
    )
    db.add(
        LeadOutcome(
            user_id=advisor.id,
            lead_id=recent_contacted_lead.id,
            status="contacted",
            notes="Still contacted",
            updated_at=datetime.now(timezone.utc),
        )
    )
    db.add(
        LeadOutcome(
            user_id=advisor.id,
            lead_id=old_delivery_appt_lead.id,
            status="appointment_set",
            notes="Old delivered lead should be excluded",
            updated_at=datetime.now(timezone.utc),
        )
    )
    db.commit()

    response = client.get("/api/v1/leads/dashboard/summary", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["leads_delivered_7_days"] == 2
    assert body["appointments_set_7_days"] == 1


@pytest.mark.integration
def test_dashboard_summary_does_not_count_recent_exports_for_old_assignments(
    client,
    db,
    user_factory,
    lead_factory,
    license_factory,
    plan_factory,
    purchase_factory,
    auth_headers,
):
    advisor, _plan, headers = _create_advisor_with_access(
        user_factory,
        license_factory,
        plan_factory,
        purchase_factory,
        auth_headers,
    )

    lead = lead_factory(
        state_code="CA",
        mobile_phone="555-CA-5451",
        first_name="Old",
        last_name="Assigned",
    )
    db.add(
        LeadOwnership(
            user_id=advisor.id,
            lead_id=lead.id,
            assigned_at=datetime.now(timezone.utc) - timedelta(days=8),
        )
    )
    db.add(
        LeadDownload(
            user_id=advisor.id,
            lead_id=lead.id,
            downloaded_at=datetime.now(timezone.utc),
            csv_batch_id="batch_old_assignment_export",
        )
    )
    db.commit()

    response = client.get("/api/v1/leads/dashboard/summary", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["leads_delivered_7_days"] == 0


@pytest.mark.integration
def test_dashboard_summary_keeps_legacy_download_fallback_when_no_ownership_exists(
    client,
    db,
    user_factory,
    lead_factory,
    license_factory,
    plan_factory,
    purchase_factory,
    auth_headers,
):
    advisor, _plan, headers = _create_advisor_with_access(
        user_factory,
        license_factory,
        plan_factory,
        purchase_factory,
        auth_headers,
    )

    legacy_lead = lead_factory(
        state_code="CA",
        mobile_phone="555-CA-5452",
        first_name="Legacy",
        last_name="Download",
    )
    db.add(
        LeadDownload(
            user_id=advisor.id,
            lead_id=legacy_lead.id,
            downloaded_at=datetime.now(timezone.utc),
            csv_batch_id="batch_legacy_download",
        )
    )
    db.commit()

    response = client.get("/api/v1/leads/dashboard/summary", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["leads_delivered_7_days"] == 1


@pytest.mark.integration
def test_admin_bulk_import_rolls_back_when_audit_write_fails(
    client,
    db,
    user_factory,
    auth_headers,
    monkeypatch,
):
    admin, headers = _create_admin_and_headers(user_factory, auth_headers)

    def fail_audit(**_kwargs):
        raise RuntimeError("audit insert failed")

    monkeypatch.setattr(
        "app.services.lead_service.AuditService.log_event",
        fail_audit,
    )

    response = client.post(
        "/api/v1/leads/bulk",
        headers=headers,
        files={
            "csv_file": _build_leads_csv_file(
                [
                    {
                        "state_code": "CA",
                        "mobile_phone": "555-BULK-AUDIT-0001",
                        "first_name": "Audit",
                        "last_name": "Rollback",
                    }
                ]
            )
        },
    )
    assert response.status_code == 500, response.text
    assert response.json() == {"detail": "Failed to import leads"}
    assert db.query(Lead).filter(Lead.mobile_phone == "555-BULK-AUDIT-0001").count() == 0
    assert (
        db.query(AuditLog)
        .filter(
            AuditLog.actor_user_id == admin.id,
            AuditLog.action == "lead_bulk_import",
            AuditLog.entity_type == "LeadImport",
        )
        .count()
        == 0
    )


@pytest.mark.integration
def test_dashboard_summary_cost_uses_latest_completed_purchase_amount(
    client,
    db,
    user_factory,
    lead_factory,
    license_factory,
    plan_factory,
    purchase_factory,
    auth_headers,
):
    advisor, _plan, headers = _create_advisor_with_access(
        user_factory,
        license_factory,
        plan_factory,
        purchase_factory,
        auth_headers,
    )

    purchase = (
        db.query(LeadPurchase)
        .filter(LeadPurchase.user_id == advisor.id, LeadPurchase.status == "completed")
        .first()
    )
    assert purchase is not None
    purchase.purchased_at = datetime.now(timezone.utc) - timedelta(days=8)
    db.add(purchase)

    lead = lead_factory(
        state_code="CA",
        mobile_phone="555-CA-5501",
        first_name="Cost",
        last_name="Metric",
    )
    db.add(
        LeadOwnership(
            user_id=advisor.id,
            lead_id=lead.id,
            assigned_at=datetime.now(timezone.utc),
        )
    )
    db.add(
        LeadOutcome(
            user_id=advisor.id,
            lead_id=lead.id,
            status="appointment_set",
            notes="Booked appointment",
            updated_at=datetime.now(timezone.utc),
        )
    )
    db.commit()

    response = client.get("/api/v1/leads/dashboard/summary", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["appointments_set_7_days"] == 1
    assert body["cost_per_appointment"] == 100.0
