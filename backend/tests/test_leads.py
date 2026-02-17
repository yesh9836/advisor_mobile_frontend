from datetime import datetime, timedelta, timezone

import pytest

from app.models.lead import LeadDownload, LeadOwnership
from app.models.purchase import LeadCreditLedger, LeadPurchase


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
    assert second_new_download.status_code == 403
    assert second_new_download.json()["detail"] == "No remaining lead credits"

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
    _advisor, _, headers = _create_advisor_with_access(
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

    lead_factory(state_code="CA", mobile_phone="555-CA-3503", first_name="Available", last_name="One")

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
def test_admin_can_create_lead_and_advisor_can_update_outcome(
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
def test_dashboard_summary_delivered_counts_only_downloaded_leads(
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
    lead_factory(state_code="CA", mobile_phone="555-CA-5101", first_name="Created", last_name="Only")

    response = client.get("/api/v1/leads/dashboard/summary", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["leads_delivered_7_days"] == 0


@pytest.mark.integration
def test_dashboard_summary_delivered_excludes_downloads_older_than_7_days(
    client,
    db,
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
    lead_factory(state_code="CA", mobile_phone="555-CA-5201", first_name="Recent", last_name="Lead")
    lead_factory(state_code="CA", mobile_phone="555-CA-5202", first_name="Old", last_name="Lead")

    download_response = client.post("/api/v1/leads/download", headers=headers)
    assert download_response.status_code == 200, download_response.text

    downloads = db.query(LeadDownload).order_by(LeadDownload.id.asc()).all()
    assert len(downloads) == 2
    downloads[0].downloaded_at = datetime.now(timezone.utc) - timedelta(days=8)
    db.commit()

    summary_response = client.get("/api/v1/leads/dashboard/summary", headers=headers)
    assert summary_response.status_code == 200, summary_response.text
    body = summary_response.json()
    assert body["leads_delivered_7_days"] == 1


@pytest.mark.integration
def test_dashboard_summary_excludes_downloads_outside_allowed_states(
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
        LeadDownload(
            user_id=advisor.id,
            lead_id=ca_lead.id,
            downloaded_at=datetime.now(timezone.utc),
            csv_batch_id="batch_state_scope",
        )
    )
    db.add(
        LeadDownload(
            user_id=advisor.id,
            lead_id=ny_lead.id,
            downloaded_at=datetime.now(timezone.utc),
            csv_batch_id="batch_state_scope",
        )
    )
    db.commit()

    response = client.get("/api/v1/leads/dashboard/summary", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["settings"]["target_states"] == ["CA"]
    assert body["leads_delivered_7_days"] == 2
