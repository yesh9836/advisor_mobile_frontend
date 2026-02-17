from datetime import datetime, timedelta, timezone

from app.models.audit_log import AuditLog
from app.models.lead import LeadDownload, LeadOwnership
from app.models.user import User


def _create_admin_and_headers(user_factory, auth_headers):
    admin = user_factory(
        role="admin",
        password="AdminSuite123!",
        email="admin.suite@example.com",
        name="Admin Suite",
    )
    return admin, auth_headers(admin.email, "AdminSuite123!")


def test_admin_endpoints_require_admin(client, user_factory, auth_headers):
    admin, admin_headers = _create_admin_and_headers(user_factory, auth_headers)
    advisor = user_factory(
        role="advisor",
        password="AdvisorSuite123!",
        email="advisor.suite@example.com",
        name="Advisor Suite",
    )
    target_user = user_factory(
        role="advisor",
        password="TargetSuite123!",
        email="target.suite@example.com",
        name="Target Suite",
    )
    advisor_headers = auth_headers(advisor.email, "AdvisorSuite123!")

    ok_dashboard = client.get("/api/v1/admin/dashboard", headers=admin_headers)
    assert ok_dashboard.status_code == 200, ok_dashboard.text

    ok_analytics = client.get("/api/v1/admin/analytics", headers=admin_headers)
    assert ok_analytics.status_code == 200, ok_analytics.text

    ok_users = client.get("/api/v1/admin/users", headers=admin_headers)
    assert ok_users.status_code == 200, ok_users.text

    ok_orders = client.get("/api/v1/admin/orders", headers=admin_headers)
    assert ok_orders.status_code == 200, ok_orders.text

    ok_lead_inventory = client.get("/api/v1/admin/lead-inventory", headers=admin_headers)
    assert ok_lead_inventory.status_code == 200, ok_lead_inventory.text

    ok_license_status_summary = client.get(
        "/api/v1/admin/license-status-summary",
        headers=admin_headers,
    )
    assert ok_license_status_summary.status_code == 200, ok_license_status_summary.text

    ok_user_details = client.get(
        f"/api/v1/admin/users/{advisor.id}", headers=admin_headers
    )
    assert ok_user_details.status_code == 200, ok_user_details.text

    ok_deactivate = client.post(
        f"/api/v1/admin/users/{target_user.id}/deactivate",
        headers=admin_headers,
        json={"reason": "Validation"},
    )
    assert ok_deactivate.status_code == 200, ok_deactivate.text

    ok_audit_logs = client.get("/api/v1/admin/audit-logs", headers=admin_headers)
    assert ok_audit_logs.status_code == 200, ok_audit_logs.text

    wordpress_placeholder = client.post(
        "/api/v1/admin/sync/wordpress",
        headers=admin_headers,
    )
    assert wordpress_placeholder.status_code == 501
    assert wordpress_placeholder.json() == {
        "detail": "WordPress sync not implemented yet"
    }

    forbidden_paths = [
        ("GET", "/api/v1/admin/dashboard"),
        ("GET", "/api/v1/admin/analytics"),
        ("GET", "/api/v1/admin/users"),
        ("GET", "/api/v1/admin/orders"),
        ("GET", "/api/v1/admin/lead-inventory"),
        ("GET", "/api/v1/admin/license-status-summary"),
        ("GET", f"/api/v1/admin/users/{admin.id}"),
        ("POST", f"/api/v1/admin/users/{admin.id}/deactivate"),
        ("GET", "/api/v1/admin/audit-logs"),
        ("POST", "/api/v1/admin/sync/wordpress"),
    ]

    for method, path in forbidden_paths:
        if method == "GET":
            response = client.get(path, headers=advisor_headers)
        else:
            response = client.post(path, headers=advisor_headers, json={"reason": "No"})

        assert response.status_code == 403
        assert response.json()["detail"] == "Admin access required"


def test_admin_analytics_overview_returns_aggregates(
    client,
    db,
    user_factory,
    auth_headers,
    plan_factory,
    purchase_factory,
    lead_factory,
):
    _admin, admin_headers = _create_admin_and_headers(user_factory, auth_headers)

    advisor_a = user_factory(
        role="advisor",
        password="AnalyticsA123!",
        email="analytics.a@example.com",
        name="Analytics Advisor A",
    )
    advisor_b = user_factory(
        role="advisor",
        password="AnalyticsB123!",
        email="analytics.b@example.com",
        name="Analytics Advisor B",
    )

    advisor_a.created_at = datetime(2026, 1, 8, tzinfo=timezone.utc)
    advisor_b.created_at = datetime(2026, 2, 12, tzinfo=timezone.utc)

    starter_plan = plan_factory(name="AnalyticsStarter", price_cents=10000)
    pro_plan = plan_factory(name="AnalyticsPro", price_cents=20000)

    january_purchase = purchase_factory(
        user_id=advisor_a.id,
        package_id=starter_plan.id,
        status="completed",
    )
    january_purchase.purchased_at = datetime(2026, 1, 10, tzinfo=timezone.utc)
    january_purchase.amount_cents = 10000

    february_purchase = purchase_factory(
        user_id=advisor_b.id,
        package_id=pro_plan.id,
        status="completed",
    )
    february_purchase.purchased_at = datetime(2026, 2, 14, tzinfo=timezone.utc)
    february_purchase.amount_cents = 20000
    db.add_all([january_purchase, february_purchase])

    lead_factory(state_code="CA", first_name="A")
    lead_factory(state_code="CA", first_name="B")
    lead_factory(state_code="TX", first_name="C")

    db.commit()

    response = client.get("/api/v1/admin/analytics", headers=admin_headers)
    assert response.status_code == 200, response.text

    payload = response.json()

    assert payload["monthly_revenue"] == [
        {"month": "2026-01", "revenue_cents": 10000},
        {"month": "2026-02", "revenue_cents": 20000},
    ]
    assert len(payload["plan_breakdown"]) == 2
    by_revenue = {
        item["revenue_cents"]: item
        for item in payload["plan_breakdown"]
    }
    assert by_revenue[20000]["purchases"] == 1
    assert by_revenue[20000]["package_name"].startswith("AnalyticsPro")
    assert by_revenue[10000]["purchases"] == 1
    assert by_revenue[10000]["package_name"].startswith("AnalyticsStarter")
    assert payload["state_distribution"] == [
        {"state_code": "CA", "lead_count": 2},
        {"state_code": "TX", "lead_count": 1},
    ]
    assert payload["user_growth"] == [
        {"month": "2026-01", "new_users": 1},
        {"month": "2026-02", "new_users": 1},
    ]


def test_admin_dashboard_counts_match_seeded_data(
    client,
    db,
    user_factory,
    auth_headers,
    plan_factory,
    purchase_factory,
    license_factory,
    lead_factory,
):
    admin, admin_headers = _create_admin_and_headers(user_factory, auth_headers)
    advisor_a = user_factory(
        role="advisor",
        password="AdvisorA123!",
        email="advisor.a@example.com",
        name="Advisor A",
    )
    advisor_b = user_factory(
        role="advisor",
        password="AdvisorB123!",
        email="advisor.b@example.com",
        name="Advisor B",
    )

    starter_plan = plan_factory(name="Starter", price_cents=120000)
    pro_plan = plan_factory(name="Pro", price_cents=250000)

    completed_purchase = purchase_factory(
        user_id=advisor_a.id,
        package_id=starter_plan.id,
        status="completed",
    )
    completed_purchase.amount_cents = 120000

    purchase_factory(
        user_id=advisor_b.id,
        package_id=pro_plan.id,
        status="failed",
    )
    db.add(completed_purchase)
    db.commit()

    license_factory(user_id=advisor_a.id, state="CA", status="pending")
    license_factory(user_id=advisor_b.id, state="TX", status="pending")
    license_factory(user_id=advisor_b.id, state="FL", status="verified")

    lead_factory(state_code="CA", first_name="One")
    lead_factory(state_code="TX", first_name="Two")
    lead_factory(state_code="FL", first_name="Three")

    response = client.get("/api/v1/admin/dashboard", headers=admin_headers)
    assert response.status_code == 200, response.text

    payload = response.json()
    assert payload["total_users"] == 3
    assert payload["completed_purchases"] == 1
    assert payload["advisors_with_credits"] == 1
    assert payload["pending_licenses"] == 2
    assert payload["total_leads"] == 3
    assert payload["total_revenue_cents"] == 120000
    assert payload["currency"] == "USD"


def test_admin_users_list_pagination_filtering_and_search(
    client,
    db,
    user_factory,
    auth_headers,
    plan_factory,
    purchase_factory,
    license_factory,
):
    _admin, admin_headers = _create_admin_and_headers(user_factory, auth_headers)

    advisor_jane = user_factory(
        role="advisor",
        password="JanePass123!",
        email="jane.advisor@example.com",
        name="Jane Advisor",
    )
    advisor_john = user_factory(
        role="advisor",
        password="JohnPass123!",
        email="john.advisor@example.com",
        name="John Advisor",
    )

    advisor_john.is_active = False
    db.commit()

    starter_plan = plan_factory(name="ListStarter", price_cents=10000)
    purchase_factory(
        user_id=advisor_jane.id,
        package_id=starter_plan.id,
        status="completed",
    )

    license_factory(user_id=advisor_jane.id, state="CA", status="verified")
    license_factory(user_id=advisor_jane.id, state="NY", status="pending")

    page_response = client.get(
        "/api/v1/admin/users?page=1&size=1",
        headers=admin_headers,
    )
    assert page_response.status_code == 200, page_response.text
    page_payload = page_response.json()
    assert page_payload["page"] == 1
    assert page_payload["size"] == 1
    assert page_payload["total"] >= 3
    assert len(page_payload["items"]) == 1

    search_response = client.get(
        "/api/v1/admin/users?page=1&size=20&search=jane&role=advisor&status=active",
        headers=admin_headers,
    )
    assert search_response.status_code == 200, search_response.text

    search_payload = search_response.json()
    assert search_payload["total"] == 1
    assert len(search_payload["items"]) == 1

    row = search_payload["items"][0]
    assert row["id"] == advisor_jane.id
    assert row["name"] == "Jane Advisor"
    assert row["email"] == "jane.advisor@example.com"
    assert row["role"] == "advisor"
    assert row["is_active"] is True
    assert row["license_count"] == 2
    assert row["current_credits"] > 0
    assert row["total_purchases"] == 1

    inactive_response = client.get(
        "/api/v1/admin/users?page=1&size=20&status=inactive",
        headers=admin_headers,
    )
    assert inactive_response.status_code == 200, inactive_response.text
    inactive_payload = inactive_response.json()
    assert any(item["id"] == advisor_john.id for item in inactive_payload["items"])


def test_admin_orders_list_and_status_filter(
    client,
    user_factory,
    auth_headers,
    plan_factory,
    purchase_factory,
):
    _admin, admin_headers = _create_admin_and_headers(user_factory, auth_headers)

    advisor_a = user_factory(
        role="advisor",
        password="OrdersA123!",
        email="orders.a@example.com",
        name="Orders Advisor A",
    )
    advisor_b = user_factory(
        role="advisor",
        password="OrdersB123!",
        email="orders.b@example.com",
        name="Orders Advisor B",
    )

    starter_plan = plan_factory(name="OrderStarter", price_cents=10000, daily_download_limit=5)
    pro_plan = plan_factory(name="OrderPro", price_cents=20000, daily_download_limit=25)

    completed_purchase = purchase_factory(
        user_id=advisor_a.id,
        package_id=starter_plan.id,
        status="completed",
    )
    canceled_purchase = purchase_factory(
        user_id=advisor_b.id,
        package_id=pro_plan.id,
        status="canceled",
    )

    all_orders = client.get(
        "/api/v1/admin/orders?page=1&size=20",
        headers=admin_headers,
    )
    assert all_orders.status_code == 200, all_orders.text
    payload = all_orders.json()
    assert payload["total"] == 2
    assert len(payload["items"]) == 2

    ids = {item["id"] for item in payload["items"]}
    assert ids == {completed_purchase.id, canceled_purchase.id}

    first = payload["items"][0]
    assert "order_reference" in first
    assert "advisor_name" in first
    assert "advisor_email" in first
    assert "package_name" in first
    assert "quantity" in first
    assert "remaining_credits" in first
    assert "status" in first
    assert "created_at" in first
    assert "amount_cents" in first
    assert "currency" in first

    completed_only = client.get(
        "/api/v1/admin/orders?page=1&size=20&status=completed",
        headers=admin_headers,
    )
    assert completed_only.status_code == 200, completed_only.text
    completed_payload = completed_only.json()
    assert completed_payload["total"] == 1
    assert len(completed_payload["items"]) == 1
    assert completed_payload["items"][0]["id"] == completed_purchase.id
    assert completed_payload["items"][0]["status"] == "completed"


def test_admin_lead_inventory_filters_and_license_status_summary(
    client,
    db,
    user_factory,
    auth_headers,
    lead_factory,
    license_factory,
    plan_factory,
    purchase_factory,
):
    _admin, admin_headers = _create_admin_and_headers(user_factory, auth_headers)
    advisor = user_factory(
        role="advisor",
        password="LeadInventory123!",
        email="inventory.advisor@example.com",
        name="Inventory Advisor",
    )
    advisor_two = user_factory(
        role="advisor",
        password="LeadInventory456!",
        email="inventory.advisor.two@example.com",
        name="Inventory Advisor Two",
    )

    lead_a = lead_factory(
        state_code="CA",
        first_name="Alice",
        last_name="North",
        mobile_phone="555-100-0001",
    )
    lead_b = lead_factory(
        state_code="TX",
        first_name="Bob",
        last_name="South",
        mobile_phone="555-200-0002",
    )
    lead_b.source = "csv_import"
    lead_c = lead_factory(
        state_code="CA",
        first_name="Cara",
        last_name="West",
        mobile_phone="555-300-0003",
    )
    plan = plan_factory(
        daily_download_limit=5,
        state_limit=1,
        stripe_price_id="price_inventory_owned",
    )
    purchase = purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        status="completed",
        stripe_checkout_session_id="cs_inventory_owned",
    )
    db.add(
        LeadOwnership(
            user_id=advisor.id,
            lead_id=lead_b.id,
            purchase_id=purchase.id,
        )
    )

    db.add_all(
        [
            LeadDownload(user_id=advisor.id, lead_id=lead_b.id, csv_batch_id="batch-a"),
        ]
    )

    license_factory(user_id=advisor.id, state="CA", status="pending")
    license_factory(user_id=advisor.id, state="TX", status="verified")
    license_factory(user_id=advisor.id, state="FL", status="rejected")
    db.commit()

    list_response = client.get(
        "/api/v1/admin/lead-inventory?page=1&size=20",
        headers=admin_headers,
    )
    assert list_response.status_code == 200, list_response.text
    payload = list_response.json()
    assert payload["total"] == 3
    assert len(payload["items"]) == 3

    by_id = {item["id"]: item for item in payload["items"]}
    assert by_id[lead_a.id]["download_count"] == 0
    assert by_id[lead_b.id]["download_count"] == 1
    assert by_id[lead_c.id]["download_count"] == 0
    assert by_id[lead_a.id]["assigned_advisor_id"] is None
    assert by_id[lead_a.id]["assigned_advisor_name"] is None
    assert by_id[lead_a.id]["purchase_reference"] is None
    assert by_id[lead_b.id]["assigned_advisor_id"] == advisor.id
    assert by_id[lead_b.id]["assigned_advisor_name"] == advisor.name
    assert by_id[lead_b.id]["assigned_advisor_email"] == advisor.email
    assert by_id[lead_b.id]["purchase_id"] == purchase.id
    assert by_id[lead_b.id]["purchase_reference"] == "cs_inventory_owned"

    filtered_state = client.get(
        "/api/v1/admin/lead-inventory?page=1&size=20&state_code=CA",
        headers=admin_headers,
    )
    assert filtered_state.status_code == 200, filtered_state.text
    state_payload = filtered_state.json()
    assert state_payload["total"] == 2
    assert all(item["state_code"] == "CA" for item in state_payload["items"])

    filtered_sold = client.get(
        "/api/v1/admin/lead-inventory?page=1&size=20&delivery_status=sold",
        headers=admin_headers,
    )
    assert filtered_sold.status_code == 200, filtered_sold.text
    sold_payload = filtered_sold.json()
    assert sold_payload["total"] == 1
    assert sold_payload["items"][0]["id"] == lead_b.id

    filtered_search = client.get(
        "/api/v1/admin/lead-inventory?page=1&size=20&search=alice",
        headers=admin_headers,
    )
    assert filtered_search.status_code == 200, filtered_search.text
    search_payload = filtered_search.json()
    assert search_payload["total"] == 1
    assert search_payload["items"][0]["id"] == lead_a.id

    invalid_range = client.get(
        "/api/v1/admin/lead-inventory",
        headers=admin_headers,
        params={
            "page": 1,
            "size": 20,
            "created_from": "2026-02-01T00:00:00Z",
            "created_to": "2026-01-01T00:00:00Z",
        },
    )
    assert invalid_range.status_code == 400
    assert invalid_range.json() == {
        "detail": "created_to must be greater than or equal to created_from"
    }

    license_summary = client.get(
        "/api/v1/admin/license-status-summary",
        headers=admin_headers,
    )
    assert license_summary.status_code == 200, license_summary.text
    summary_payload = license_summary.json()
    assert summary_payload == [
        {"status": "pending", "count": 1},
        {"status": "verified", "count": 1},
        {"status": "rejected", "count": 1},
    ]

def test_admin_user_details_200_and_404(
    client,
    db,
    user_factory,
    auth_headers,
    plan_factory,
    purchase_factory,
    license_factory,
    lead_factory,
):
    admin, admin_headers = _create_admin_and_headers(user_factory, auth_headers)

    advisor = user_factory(
        role="advisor",
        password="DetailPass123!",
        email="detail.advisor@example.com",
        name="Detail Advisor",
    )

    plan = plan_factory(name="DetailPlan", price_cents=30000)
    purchase_factory(user_id=advisor.id, package_id=plan.id, status="completed")

    license_factory(user_id=advisor.id, state="CA", status="verified")

    lead = lead_factory(state_code="CA", first_name="Detail", last_name="Lead")
    db.add(
        LeadDownload(
            user_id=advisor.id,
            lead_id=lead.id,
            csv_batch_id="batch-1",
        )
    )
    db.add(
        AuditLog(
            actor_user_id=advisor.id,
            action="lead_downloaded",
            entity_type="Lead",
            entity_id=lead.id,
            meta_data={"state": "CA"},
            ip_address="203.0.113.11",
        )
    )
    db.commit()

    details_response = client.get(
        f"/api/v1/admin/users/{advisor.id}",
        headers=admin_headers,
    )
    assert details_response.status_code == 200, details_response.text

    payload = details_response.json()
    assert payload["id"] == advisor.id
    assert payload["email"] == "detail.advisor@example.com"
    assert payload["is_active"] is True
    assert isinstance(payload["licenses"], list)
    assert len(payload["licenses"]) == 1
    assert payload["credit_summary"]["completed_purchases"] == 1
    assert payload["credit_summary"]["remaining_credits"] > 0
    assert len(payload["purchase_history"]) == 1
    assert payload["purchase_history"][0]["status"] == "completed"
    assert len(payload["download_history"]) == 1
    assert len(payload["recent_activity"]) == 1

    not_found = client.get("/api/v1/admin/users/999999", headers=admin_headers)
    assert not_found.status_code == 404
    assert not_found.json() == {"detail": "User not found"}


def test_admin_deactivate_user_and_block_deactivated_user_auth(
    client,
    db,
    user_factory,
    auth_headers,
):
    admin, admin_headers = _create_admin_and_headers(user_factory, auth_headers)

    advisor = user_factory(
        role="advisor",
        password="Deactivate123!",
        email="deactivate.advisor@example.com",
        name="Deactivate Advisor",
    )
    advisor_headers = auth_headers(advisor.email, "Deactivate123!")

    deactivate_response = client.post(
        f"/api/v1/admin/users/{advisor.id}/deactivate",
        headers=admin_headers,
        json={"reason": "Fraud review"},
    )
    assert deactivate_response.status_code == 200, deactivate_response.text
    assert deactivate_response.json() == {"detail": "User deactivated"}

    db.expire_all()
    refreshed_user = db.query(User).filter(User.id == advisor.id).first()
    assert refreshed_user is not None
    assert refreshed_user.is_active is False
    assert refreshed_user.deactivated_by == admin.id
    assert refreshed_user.deactivated_at is not None

    deactivate_audit = (
        db.query(AuditLog)
        .filter(
            AuditLog.actor_user_id == admin.id,
            AuditLog.action == "user_deactivated",
            AuditLog.entity_type == "User",
            AuditLog.entity_id == advisor.id,
        )
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .first()
    )
    assert deactivate_audit is not None
    assert deactivate_audit.meta_data is not None
    assert deactivate_audit.meta_data["target_user_id"] == advisor.id
    assert deactivate_audit.meta_data["reason"] == "Fraud review"

    already_inactive = client.post(
        f"/api/v1/admin/users/{advisor.id}/deactivate",
        headers=admin_headers,
        json={"reason": "Duplicate"},
    )
    assert already_inactive.status_code == 400
    assert already_inactive.json() == {"detail": "User already inactive"}

    me_response = client.get("/api/v1/auth/me", headers=advisor_headers)
    assert me_response.status_code == 403
    assert me_response.json() == {"detail": "Inactive user account"}


def test_admin_audit_logs_filters_and_ordering(client, db, user_factory, auth_headers):
    admin, admin_headers = _create_admin_and_headers(user_factory, auth_headers)

    advisor = user_factory(
        role="advisor",
        password="AuditAdvisor123!",
        email="audit.advisor@example.com",
        name="Audit Advisor",
    )

    older = datetime.now(timezone.utc) - timedelta(minutes=10)
    newer = datetime.now(timezone.utc)

    older_log = AuditLog(
        actor_user_id=admin.id,
        action="license_approved",
        entity_type="License",
        entity_id=101,
        meta_data={"state": "CA"},
        ip_address="203.0.113.5",
        created_at=older,
    )
    newer_log = AuditLog(
        actor_user_id=admin.id,
        action="license_approved",
        entity_type="License",
        entity_id=102,
        meta_data={"state": "TX"},
        ip_address="203.0.113.6",
        created_at=newer,
    )
    third_log = AuditLog(
        actor_user_id=advisor.id,
        action="lead_downloaded",
        entity_type="Lead",
        entity_id=501,
        meta_data={"state": "FL"},
        ip_address="203.0.113.7",
        created_at=newer + timedelta(seconds=1),
    )

    db.add_all([older_log, newer_log, third_log])
    db.commit()

    all_logs_response = client.get(
        "/api/v1/admin/audit-logs?page=1&size=2",
        headers=admin_headers,
    )
    assert all_logs_response.status_code == 200, all_logs_response.text
    all_payload = all_logs_response.json()
    assert all_payload["total"] == 3
    assert all_payload["page"] == 1
    assert all_payload["size"] == 2
    assert len(all_payload["items"]) == 2
    assert all_payload["items"][0]["id"] > all_payload["items"][1]["id"]

    filtered = client.get(
        f"/api/v1/admin/audit-logs?page=1&size=20&action=license_approved&actor_user_id={admin.id}",
        headers=admin_headers,
    )
    assert filtered.status_code == 200, filtered.text
    filtered_payload = filtered.json()
    assert filtered_payload["total"] == 2
    assert len(filtered_payload["items"]) == 2
    assert all(item["action"] == "license_approved" for item in filtered_payload["items"])
    assert all(item["actor_user_id"] == admin.id for item in filtered_payload["items"])

    from_iso = (newer - timedelta(seconds=1)).isoformat()
    to_iso = (newer + timedelta(seconds=1)).isoformat()
    range_filtered = client.get(
        "/api/v1/admin/audit-logs",
        headers=admin_headers,
        params={
            "page": 1,
            "size": 20,
            "created_from": from_iso,
            "created_to": to_iso,
        },
    )
    assert range_filtered.status_code == 200, range_filtered.text
    range_payload = range_filtered.json()
    assert range_payload["total"] == 2
    assert all(item["id"] in {newer_log.id, third_log.id} for item in range_payload["items"])

    invalid_range = client.get(
        "/api/v1/admin/audit-logs",
        headers=admin_headers,
        params={
            "page": 1,
            "size": 20,
            "created_from": to_iso,
            "created_to": from_iso,
        },
    )
    assert invalid_range.status_code == 400
    assert invalid_range.json() == {
        "detail": "created_to must be greater than or equal to created_from"
    }
