import csv
import io
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.models.audit_log import AuditLog
from app.models.auth_session import RefreshTokenSession
from app.models.lead import LeadDownload, LeadOwnership
from app.models.purchase import FirstPurchaseAddonOffer, LeadPackage, StripePlanCleanupOutbox
from app.models.user import User
from app.services.first_purchase_offer_service import FirstPurchaseOfferService


def _create_admin_and_headers(user_factory, auth_headers):
    admin = user_factory(
        role="admin",
        password="AdminSuite123!",
        email="admin.suite@example.com",
        name="Admin Suite",
    )
    return admin, auth_headers(admin.email, "AdminSuite123!")


def test_admin_endpoints_require_admin(client, user_factory, auth_headers, plan_factory, monkeypatch):
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
    target_plan = plan_factory(name="PlanTarget", price_cents=14000, daily_download_limit=14)
    advisor_headers = auth_headers(advisor.email, "AdvisorSuite123!")

    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.create_stripe_price_for_plan",
        lambda **kwargs: {
            "stripe_price_id": f"price_admin_plan_{kwargs['request_id']}",
            "stripe_product_id": "prod_admin_plan",
        },
    )
    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.deactivate_stripe_plan_artifacts",
        lambda **_kwargs: {"price_deactivated": True, "product_deactivated": True},
    )
    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.activate_stripe_plan_artifacts",
        lambda **_kwargs: {"price_activated": True, "product_activated": True},
    )

    ok_dashboard = client.get("/api/v1/admin/dashboard", headers=admin_headers)
    assert ok_dashboard.status_code == 200, ok_dashboard.text

    ok_analytics = client.get("/api/v1/admin/analytics", headers=admin_headers)
    assert ok_analytics.status_code == 200, ok_analytics.text

    ok_users = client.get("/api/v1/admin/users", headers=admin_headers)
    assert ok_users.status_code == 200, ok_users.text

    ok_orders = client.get("/api/v1/admin/orders", headers=admin_headers)
    assert ok_orders.status_code == 200, ok_orders.text

    ok_orders_export = client.get("/api/v1/admin/orders/export", headers=admin_headers)
    assert ok_orders_export.status_code == 200, ok_orders_export.text

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

    ok_plan_list = client.get("/api/v1/admin/plans", headers=admin_headers)
    assert ok_plan_list.status_code == 200, ok_plan_list.text

    ok_plan_create = client.post(
        "/api/v1/admin/plans",
        headers=admin_headers,
        json={
            "name": "Growth 25",
            "price_cents": 25000,
            "credits_total": 25,
            "state_limit": 3,
            "catalog_visible": True,
            "request_id": "admin_plan_create_123",
        },
    )
    assert ok_plan_create.status_code == 200, ok_plan_create.text

    ok_plan_update = client.put(
        f"/api/v1/admin/plans/{target_plan.id}",
        headers=admin_headers,
        json={
            "name": "PlanTarget Renamed",
            "catalog_visible": True,
        },
    )
    assert ok_plan_update.status_code == 200, ok_plan_update.text

    ok_plan_archive = client.post(
        f"/api/v1/admin/plans/{target_plan.id}/archive",
        headers=admin_headers,
        json={"reason": "Retiring"},
    )
    assert ok_plan_archive.status_code == 200, ok_plan_archive.text

    ok_plan_unarchive = client.post(
        f"/api/v1/admin/plans/{target_plan.id}/unarchive",
        headers=admin_headers,
        json={"reason": "Rollback"},
    )
    assert ok_plan_unarchive.status_code == 200, ok_plan_unarchive.text

    ok_offer_get = client.get(
        "/api/v1/admin/first-purchase-offer",
        headers=admin_headers,
    )
    assert ok_offer_get.status_code == 200, ok_offer_get.text

    ok_offer_put = client.put(
        "/api/v1/admin/first-purchase-offer",
        headers=admin_headers,
        json={"is_enabled": False},
    )
    assert ok_offer_put.status_code == 200, ok_offer_put.text

    wordpress_placeholder = client.post(
        "/api/v1/admin/sync/wordpress",
        headers=admin_headers,
    )
    assert wordpress_placeholder.status_code == 404

    forbidden_paths = [
        ("GET", "/api/v1/admin/dashboard"),
        ("GET", "/api/v1/admin/analytics"),
        ("GET", "/api/v1/admin/users"),
        ("GET", "/api/v1/admin/orders"),
        ("GET", "/api/v1/admin/orders/export"),
        ("GET", "/api/v1/admin/lead-inventory"),
        ("GET", "/api/v1/admin/license-status-summary"),
        ("GET", f"/api/v1/admin/users/{admin.id}"),
        ("POST", f"/api/v1/admin/users/{admin.id}/deactivate"),
        ("GET", "/api/v1/admin/audit-logs"),
        ("GET", "/api/v1/admin/plans"),
        ("GET", "/api/v1/admin/first-purchase-offer"),
        ("PUT", "/api/v1/admin/first-purchase-offer"),
    ]

    for method, path in forbidden_paths:
        if method == "GET":
            response = client.get(path, headers=advisor_headers)
        elif method == "PUT":
            response = client.put(path, headers=advisor_headers, json={"is_enabled": False})
        else:
            response = client.post(path, headers=advisor_headers, json={"reason": "No"})

        assert response.status_code == 403
        assert response.json()["detail"] == "Admin access required"

    forbidden_plan_create = client.post(
        "/api/v1/admin/plans",
        headers=advisor_headers,
        json={
            "name": "Advisor Forbidden Plan",
            "price_cents": 15000,
            "credits_total": 15,
            "state_limit": 2,
            "catalog_visible": True,
            "request_id": "advisor_forbidden_plan_01",
        },
    )
    assert forbidden_plan_create.status_code == 403
    assert forbidden_plan_create.json()["detail"] == "Admin access required"

    forbidden_plan_update = client.put(
        f"/api/v1/admin/plans/{target_plan.id}",
        headers=advisor_headers,
        json={"name": "Forbidden Rename"},
    )
    assert forbidden_plan_update.status_code == 403
    assert forbidden_plan_update.json()["detail"] == "Admin access required"

    forbidden_plan_archive = client.post(
        f"/api/v1/admin/plans/{target_plan.id}/archive",
        headers=advisor_headers,
        json={"reason": "No"},
    )
    assert forbidden_plan_archive.status_code == 403
    assert forbidden_plan_archive.json()["detail"] == "Admin access required"

    forbidden_plan_unarchive = client.post(
        f"/api/v1/admin/plans/{target_plan.id}/unarchive",
        headers=advisor_headers,
        json={"reason": "No"},
    )
    assert forbidden_plan_unarchive.status_code == 403
    assert forbidden_plan_unarchive.json()["detail"] == "Admin access required"


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


def test_admin_can_configure_first_purchase_addon_offer(
    client,
    db,
    user_factory,
    auth_headers,
    plan_factory,
):
    admin, admin_headers = _create_admin_and_headers(user_factory, auth_headers)
    trigger_package = plan_factory(name="TriggerStarter", price_cents=12000, daily_download_limit=10)

    initial = client.get("/api/v1/admin/first-purchase-offer", headers=admin_headers)
    assert initial.status_code == 200, initial.text
    assert initial.json()["is_enabled"] is False
    assert initial.json()["trigger_package_id"] is None
    assert initial.json()["offer_package_id"] is None

    update_response = client.put(
        "/api/v1/admin/first-purchase-offer",
        headers=admin_headers,
        json={
            "is_enabled": True,
            "trigger_package_id": trigger_package.id,
            "offer_credits_total": 5,
            "offer_price_cents": 7500,
            "offer_currency": "USD",
            "headline": "First order bonus",
            "message": "Upgrade this order and receive extra credits.",
            "cta_label": "Upgrade to bonus package",
        },
    )
    assert update_response.status_code == 200, update_response.text
    payload = update_response.json()
    assert payload["is_enabled"] is True
    assert payload["trigger_package_id"] == trigger_package.id
    assert payload["trigger_package_name"].startswith("TriggerStarter")
    assert payload["offer_package_id"] is not None
    assert payload["offer_package_name"].startswith("First Purchase Add-on")
    assert payload["offer_price_cents"] == 7500
    assert payload["offer_credits_total"] == 5
    assert payload["offer_currency"] == "USD"
    assert payload["updated_by"] == admin.id
    assert "inventory_ready" in payload
    assert "inventory_available_count" in payload
    assert "inventory_required_count" in payload
    assert "inventory_gate_code" in payload
    assert "inventory_gate_message" in payload

    refreshed = client.get("/api/v1/admin/first-purchase-offer", headers=admin_headers)
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["is_enabled"] is True
    assert refreshed.json()["offer_package_id"] == payload["offer_package_id"]

    audit_event = (
        db.query(AuditLog)
        .filter(
            AuditLog.actor_user_id == admin.id,
            AuditLog.action == "first_purchase_addon_offer_updated",
            AuditLog.entity_type == "FirstPurchaseAddonOffer",
        )
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert audit_event is not None
    assert (audit_event.meta_data or {}).get("after", {}).get("is_enabled") is True


def test_admin_first_purchase_offer_update_rejects_non_usd_currency(
    client,
    user_factory,
    auth_headers,
    plan_factory,
):
    _admin, admin_headers = _create_admin_and_headers(user_factory, auth_headers)
    trigger_package = plan_factory(name="TriggerCurrencyGuard", price_cents=12000, daily_download_limit=10)

    response = client.put(
        "/api/v1/admin/first-purchase-offer",
        headers=admin_headers,
        json={
            "is_enabled": True,
            "trigger_package_id": trigger_package.id,
            "offer_credits_total": 5,
            "offer_price_cents": 7500,
            "offer_currency": "EUR",
            "headline": "First order bonus",
            "message": "Upgrade this order and receive extra credits.",
            "cta_label": "Upgrade to bonus package",
        },
    )

    assert response.status_code == 422, response.text
    assert "offer_currency must be USD" in response.text


def test_admin_first_purchase_offer_update_preserves_client_http_errors(
    client,
    db,
    user_factory,
    auth_headers,
    plan_factory,
):
    admin, admin_headers = _create_admin_and_headers(user_factory, auth_headers)
    trigger_package = plan_factory(name="TriggerConfig", price_cents=11000, daily_download_limit=5)
    unmanaged_offer_package = plan_factory(name="LegacyOffer", price_cents=9000, daily_download_limit=3)

    db.add(
        FirstPurchaseAddonOffer(
            is_enabled=True,
            trigger_package_id=trigger_package.id,
            offer_package_id=unmanaged_offer_package.id,
            offer_credits_total=4,
            offer_price_cents=5500,
            offer_currency="USD",
            updated_by=admin.id,
        )
    )
    db.commit()

    response = client.put(
        "/api/v1/admin/first-purchase-offer",
        headers=admin_headers,
        json={
            "is_enabled": True,
            "trigger_package_id": trigger_package.id,
            "offer_credits_total": 6,
            "offer_price_cents": 6500,
            "offer_currency": "USD",
        },
    )
    assert response.status_code == 400, response.text
    assert response.json() == {
        "detail": "Configured offer_package_id is not a managed first-purchase add-on package"
    }


def test_admin_first_purchase_offer_update_maps_unknown_errors_to_500(
    client,
    user_factory,
    auth_headers,
    plan_factory,
    monkeypatch,
):
    _admin, admin_headers = _create_admin_and_headers(user_factory, auth_headers)
    trigger_package = plan_factory(name="TriggerRuntime", price_cents=10000, daily_download_limit=8)

    def _raise_runtime_error(*args, **kwargs):
        _ = (args, kwargs)
        raise RuntimeError("forced runtime failure")

    monkeypatch.setattr(
        FirstPurchaseOfferService,
        "_upsert_internal_offer_package",
        staticmethod(_raise_runtime_error),
    )

    response = client.put(
        "/api/v1/admin/first-purchase-offer",
        headers=admin_headers,
        json={
            "is_enabled": True,
            "trigger_package_id": trigger_package.id,
            "offer_credits_total": 5,
            "offer_price_cents": 6000,
            "offer_currency": "USD",
        },
    )
    assert response.status_code == 500, response.text
    assert response.json() == {"detail": "Failed to save first-purchase add-on offer"}


def test_admin_first_purchase_offer_archive_unarchive_reuses_internal_package(
    client,
    db,
    user_factory,
    auth_headers,
    plan_factory,
):
    _admin, admin_headers = _create_admin_and_headers(user_factory, auth_headers)
    trigger_package = plan_factory(name="TriggerReuse", price_cents=12000, daily_download_limit=10)

    enable_response = client.put(
        "/api/v1/admin/first-purchase-offer",
        headers=admin_headers,
        json={
            "is_enabled": True,
            "trigger_package_id": trigger_package.id,
            "offer_credits_total": 5,
            "offer_price_cents": 7500,
            "offer_currency": "USD",
        },
    )
    assert enable_response.status_code == 200, enable_response.text
    enabled_payload = enable_response.json()
    first_offer_package_id = enabled_payload["offer_package_id"]
    assert first_offer_package_id is not None

    archive_response = client.put(
        "/api/v1/admin/first-purchase-offer",
        headers=admin_headers,
        json={
            "is_enabled": False,
            "trigger_package_id": trigger_package.id,
            "offer_credits_total": 5,
            "offer_price_cents": 7500,
            "offer_currency": "USD",
        },
    )
    assert archive_response.status_code == 200, archive_response.text
    assert archive_response.json()["offer_package_id"] == first_offer_package_id

    unarchive_response = client.put(
        "/api/v1/admin/first-purchase-offer",
        headers=admin_headers,
        json={
            "is_enabled": True,
            "trigger_package_id": trigger_package.id,
            "offer_credits_total": 5,
            "offer_price_cents": 7500,
            "offer_currency": "USD",
        },
    )
    assert unarchive_response.status_code == 200, unarchive_response.text
    assert unarchive_response.json()["offer_package_id"] == first_offer_package_id

    managed_rows = [
        row
        for row in db.query(LeadPackage).order_by(LeadPackage.id.asc()).all()
        if FirstPurchaseOfferService._is_managed_internal_offer_package(row)
    ]
    assert len(managed_rows) == 1
    assert int(managed_rows[0].id) == int(first_offer_package_id)


def test_admin_first_purchase_offer_update_recovers_legacy_null_offer_package_link(
    client,
    db,
    user_factory,
    auth_headers,
    plan_factory,
):
    admin, admin_headers = _create_admin_and_headers(user_factory, auth_headers)
    trigger_package = plan_factory(name="TriggerLegacy", price_cents=12000, daily_download_limit=10)

    legacy_config = FirstPurchaseAddonOffer(
        is_enabled=False,
        trigger_package_id=trigger_package.id,
        offer_package_id=None,
        offer_credits_total=4,
        offer_price_cents=5600,
        offer_currency="USD",
        updated_by=admin.id,
    )
    db.add(legacy_config)
    db.commit()
    db.refresh(legacy_config)

    existing_managed_package = LeadPackage(
        name=FirstPurchaseOfferService._build_internal_offer_package_name(
            config_id=int(legacy_config.id),
            offer_credits_total=4,
        ),
        price_cents=5600,
        currency="USD",
        stripe_price_id=f"dynamic_addon_legacy_{legacy_config.id}",
        state_limit=trigger_package.state_limit,
        daily_download_limit=4,
        features={
            "managed_by": "first_purchase_offer",
            "catalog_visible": False,
            "trigger_package_id": int(trigger_package.id),
        },
    )
    db.add(existing_managed_package)
    db.commit()
    db.refresh(existing_managed_package)

    response = client.put(
        "/api/v1/admin/first-purchase-offer",
        headers=admin_headers,
        json={
            "is_enabled": True,
            "trigger_package_id": trigger_package.id,
            "offer_credits_total": 6,
            "offer_price_cents": 6800,
            "offer_currency": "USD",
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["offer_package_id"] == existing_managed_package.id
    assert payload["offer_price_cents"] == 6800
    assert payload["offer_credits_total"] == 6

    db.expire_all()
    refreshed_package = (
        db.query(LeadPackage)
        .filter(LeadPackage.id == existing_managed_package.id)
        .first()
    )
    assert refreshed_package is not None
    assert refreshed_package.name.startswith("First Purchase Add-on")
    assert refreshed_package.price_cents == 6800
    assert refreshed_package.daily_download_limit == 6
    assert isinstance(refreshed_package.features, dict)
    assert refreshed_package.features.get("managed_config_id") == legacy_config.id
    assert refreshed_package.features.get("trigger_package_id") == trigger_package.id


def test_admin_first_purchase_offer_update_recovers_when_unmanaged_name_collision_exists(
    client,
    db,
    user_factory,
    auth_headers,
    plan_factory,
):
    admin, admin_headers = _create_admin_and_headers(user_factory, auth_headers)
    trigger_package = plan_factory(name="TriggerCollision", price_cents=12000, daily_download_limit=10)

    collision_config = FirstPurchaseAddonOffer(
        is_enabled=False,
        trigger_package_id=trigger_package.id,
        offer_package_id=None,
        offer_credits_total=5,
        offer_price_cents=5900,
        offer_currency="USD",
        updated_by=admin.id,
    )
    db.add(collision_config)
    db.commit()
    db.refresh(collision_config)

    unmanaged_collision_row = LeadPackage(
        name=FirstPurchaseOfferService._build_internal_offer_package_name(
            config_id=int(collision_config.id),
            offer_credits_total=5,
        ),
        price_cents=9900,
        currency="USD",
        stripe_price_id=f"price_collision_{collision_config.id}",
        state_limit=trigger_package.state_limit,
        daily_download_limit=9,
        features={"catalog_visible": True},
    )
    db.add(unmanaged_collision_row)
    db.commit()

    response = client.put(
        "/api/v1/admin/first-purchase-offer",
        headers=admin_headers,
        json={
            "is_enabled": True,
            "trigger_package_id": trigger_package.id,
            "offer_credits_total": 5,
            "offer_price_cents": 5900,
            "offer_currency": "USD",
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["offer_package_id"] is not None
    assert int(payload["offer_package_id"]) != int(unmanaged_collision_row.id)
    assert payload["is_enabled"] is True
    assert payload["offer_price_cents"] == 5900
    assert payload["offer_credits_total"] == 5

    resolved_offer_package = (
        db.query(LeadPackage)
        .filter(LeadPackage.id == int(payload["offer_package_id"]))
        .first()
    )
    assert resolved_offer_package is not None
    assert isinstance(resolved_offer_package.features, dict)
    assert resolved_offer_package.features.get("managed_by") == "first_purchase_offer"
    assert resolved_offer_package.features.get("managed_config_id") == collision_config.id
    assert resolved_offer_package.features.get("catalog_visible") is False


def test_admin_plan_lifecycle_create_update_archive_and_audit(
    client,
    db,
    user_factory,
    auth_headers,
    purchase_factory,
    monkeypatch,
):
    admin, admin_headers = _create_admin_and_headers(user_factory, auth_headers)
    stripe_toggles = {"deactivate": [], "activate": []}

    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.create_stripe_price_for_plan",
        lambda **kwargs: {
            "stripe_price_id": f"price_admin_{kwargs['request_id']}",
            "stripe_product_id": f"prod_admin_{kwargs['request_id']}",
        },
    )
    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.deactivate_stripe_plan_artifacts",
        lambda **kwargs: stripe_toggles["deactivate"].append(kwargs)
        or {"price_deactivated": True, "product_deactivated": True},
    )
    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.activate_stripe_plan_artifacts",
        lambda **kwargs: stripe_toggles["activate"].append(kwargs)
        or {"price_activated": True, "product_activated": True},
    )

    create_response = client.post(
        "/api/v1/admin/plans",
        headers=admin_headers,
        json={
            "name": "Plan Lifecycle 25",
            "price_cents": 25000,
            "credits_total": 25,
            "state_limit": 4,
            "catalog_visible": True,
            "effective_from": "2026-02-01T00:00:00Z",
            "effective_to": "2026-12-31T23:59:59Z",
            "request_id": "admin_plan_lifecycle_create_01",
        },
    )
    assert create_response.status_code == 200, create_response.text
    created = create_response.json()
    assert created["name"] == "Plan Lifecycle 25"
    assert created["stripe_price_id"] == "price_admin_admin_plan_lifecycle_create_01"
    assert created["stripe_product_id"] == "prod_admin_admin_plan_lifecycle_create_01"
    assert created["is_archived"] is False
    assert created["catalog_visible"] is True
    assert created["credits_total"] == 25

    plan_id = int(created["id"])
    update_response = client.put(
        f"/api/v1/admin/plans/{plan_id}",
        headers=admin_headers,
        json={
            "name": "Plan Lifecycle 30",
            "price_cents": 30000,
            "credits_total": 30,
            "request_id": "admin_plan_lifecycle_update_01",
        },
    )
    assert update_response.status_code == 200, update_response.text
    updated = update_response.json()
    assert updated["name"] == "Plan Lifecycle 30"
    assert updated["price_cents"] == 30000
    assert updated["credits_total"] == 30
    assert updated["stripe_price_id"] == "price_admin_admin_plan_lifecycle_update_01"
    assert updated["stripe_product_id"] == "prod_admin_admin_plan_lifecycle_update_01"

    advisor = user_factory(
        role="advisor",
        password="PlanAdvisor123!",
        email="plan.advisor@example.com",
        name="Plan Advisor",
    )
    purchase_factory(
        user_id=advisor.id,
        package_id=plan_id,
        credits_total=30,
    )

    blocked_update = client.put(
        f"/api/v1/admin/plans/{plan_id}",
        headers=admin_headers,
        json={
            "price_cents": 31000,
            "request_id": "admin_plan_lifecycle_update_02",
        },
    )
    assert blocked_update.status_code == 409, blocked_update.text
    assert "immutable after activation" in blocked_update.json()["detail"]

    archive_response = client.post(
        f"/api/v1/admin/plans/{plan_id}/archive",
        headers=admin_headers,
        json={"reason": "Retire price tier"},
    )
    assert archive_response.status_code == 200, archive_response.text
    archived = archive_response.json()
    assert archived["is_archived"] is True
    assert archived["archived_at"] is not None

    unarchive_response = client.post(
        f"/api/v1/admin/plans/{plan_id}/unarchive",
        headers=admin_headers,
        json={"reason": "Rollback archive"},
    )
    assert unarchive_response.status_code == 200, unarchive_response.text
    unarchived = unarchive_response.json()
    assert unarchived["is_archived"] is False
    assert unarchived["archived_at"] is None
    assert stripe_toggles["deactivate"] == [
        {
            "stripe_price_id": "price_admin_admin_plan_lifecycle_update_01",
            "stripe_product_id": "prod_admin_admin_plan_lifecycle_update_01",
        }
    ]
    assert stripe_toggles["activate"] == [
        {
            "stripe_price_id": "price_admin_admin_plan_lifecycle_update_01",
            "stripe_product_id": "prod_admin_admin_plan_lifecycle_update_01",
        }
    ]

    actions = {
        row.action
        for row in db.query(AuditLog)
        .filter(
            AuditLog.actor_user_id == admin.id,
            AuditLog.entity_type == "LeadPackage",
            AuditLog.entity_id == plan_id,
        )
        .all()
    }
    assert "admin_plan_created" in actions
    assert "admin_plan_updated" in actions
    assert "admin_plan_archived" in actions
    assert "admin_plan_unarchived" in actions


def test_admin_plan_update_duplicate_name_rejected_before_stripe_side_effects(
    client,
    user_factory,
    auth_headers,
    plan_factory,
    monkeypatch,
):
    _admin, admin_headers = _create_admin_and_headers(user_factory, auth_headers)
    target_plan = plan_factory(name="TargetPlan", price_cents=20000, daily_download_limit=20)
    conflicting_plan = plan_factory(name="ConflictPlan", price_cents=25000, daily_download_limit=25)

    call_counter = {"count": 0}

    def _mock_create_price(**kwargs):
        _ = kwargs
        call_counter["count"] += 1
        return {
            "stripe_price_id": "price_should_not_be_created",
            "stripe_product_id": "prod_should_not_be_created",
        }

    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.create_stripe_price_for_plan",
        _mock_create_price,
    )

    response = client.put(
        f"/api/v1/admin/plans/{target_plan.id}",
        headers=admin_headers,
        json={
            "name": conflicting_plan.name,
            "price_cents": 30000,
            "credits_total": 30,
            "request_id": "admin_plan_duplicate_guard_01",
        },
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"] == "Plan name already exists"
    assert call_counter["count"] == 0


def test_admin_plan_create_commit_failure_enqueues_stripe_cleanup_outbox_when_inline_cleanup_fails(
    client,
    db,
    user_factory,
    auth_headers,
    plan_factory,
    monkeypatch,
):
    _admin, admin_headers = _create_admin_and_headers(user_factory, auth_headers)
    conflicting_plan = plan_factory(
        name="ExistingPlan",
        price_cents=19000,
        daily_download_limit=19,
        stripe_price_id="price_conflict_for_cleanup_create",
    )
    assert conflicting_plan is not None

    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.create_stripe_price_for_plan",
        lambda **_kwargs: {
            "stripe_price_id": "price_conflict_for_cleanup_create",
            "stripe_product_id": "prod_conflict_for_cleanup_create",
        },
    )
    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.deactivate_stripe_plan_artifacts",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("forced cleanup failure")),
    )

    response = client.post(
        "/api/v1/admin/plans",
        headers=admin_headers,
        json={
            "name": "Plan Cleanup Create Failure",
            "price_cents": 21000,
            "credits_total": 21,
            "state_limit": 2,
            "catalog_visible": True,
            "request_id": "admin_plan_cleanup_create_01",
        },
    )
    assert response.status_code == 500, response.text
    assert response.json() == {"detail": "Failed to persist plan creation"}

    outbox_row = (
        db.query(StripePlanCleanupOutbox)
        .filter(StripePlanCleanupOutbox.source == "admin_plan_create")
        .first()
    )
    assert outbox_row is not None
    assert outbox_row.status == "pending"
    assert outbox_row.stripe_price_id == "price_conflict_for_cleanup_create"
    assert outbox_row.stripe_product_id == "prod_conflict_for_cleanup_create"


def test_admin_plan_update_commit_failure_enqueues_stripe_cleanup_outbox_when_inline_cleanup_fails(
    client,
    db,
    user_factory,
    auth_headers,
    plan_factory,
    monkeypatch,
):
    _admin, admin_headers = _create_admin_and_headers(user_factory, auth_headers)
    target_plan = plan_factory(name="CleanupUpdateTarget", price_cents=22000, daily_download_limit=22)
    conflicting_plan = plan_factory(
        name="CleanupUpdateConflict",
        price_cents=23000,
        daily_download_limit=23,
        stripe_price_id="price_conflict_for_cleanup_update",
    )
    assert conflicting_plan is not None

    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.create_stripe_price_for_plan",
        lambda **_kwargs: {
            "stripe_price_id": "price_conflict_for_cleanup_update",
            "stripe_product_id": "prod_conflict_for_cleanup_update",
        },
    )
    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.deactivate_stripe_plan_artifacts",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("forced cleanup failure")),
    )

    response = client.put(
        f"/api/v1/admin/plans/{target_plan.id}",
        headers=admin_headers,
        json={
            "price_cents": 24000,
            "credits_total": 24,
            "request_id": "admin_plan_cleanup_update_01",
        },
    )
    assert response.status_code == 500, response.text
    assert response.json() == {"detail": "Failed to persist plan update"}

    outbox_row = (
        db.query(StripePlanCleanupOutbox)
        .filter(
            StripePlanCleanupOutbox.source == "admin_plan_update",
            StripePlanCleanupOutbox.stripe_price_id == "price_conflict_for_cleanup_update",
        )
        .first()
    )
    assert outbox_row is not None
    assert outbox_row.status == "pending"
    assert outbox_row.stripe_product_id == "prod_conflict_for_cleanup_update"


def test_admin_plan_archive_stripe_deactivation_failure_enqueues_cleanup_outbox(
    client,
    db,
    user_factory,
    auth_headers,
    plan_factory,
    monkeypatch,
):
    _admin, admin_headers = _create_admin_and_headers(user_factory, auth_headers)
    plan = plan_factory(
        name="Archive Stripe Failure Plan",
        stripe_price_id="price_archive_deactivate_fail",
    )
    plan.stripe_product_id = "prod_archive_deactivate_fail"
    db.add(plan)
    db.commit()

    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.deactivate_stripe_plan_artifacts",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("forced archive deactivation failure")),
    )

    response = client.post(
        f"/api/v1/admin/plans/{plan.id}/archive",
        headers=admin_headers,
        json={"reason": "retire"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["is_archived"] is True

    outbox_row = (
        db.query(StripePlanCleanupOutbox)
        .filter(
            StripePlanCleanupOutbox.source == "admin_plan_archive",
            StripePlanCleanupOutbox.stripe_price_id == "price_archive_deactivate_fail",
        )
        .first()
    )
    assert outbox_row is not None
    assert outbox_row.status == "pending"
    assert outbox_row.stripe_product_id == "prod_archive_deactivate_fail"


def test_admin_plan_unarchive_rejects_when_stripe_activation_fails(
    client,
    db,
    user_factory,
    auth_headers,
    plan_factory,
    monkeypatch,
):
    _admin, admin_headers = _create_admin_and_headers(user_factory, auth_headers)
    plan = plan_factory(
        name="Unarchive Stripe Failure Plan",
        stripe_price_id="price_unarchive_activate_fail",
    )
    plan.stripe_product_id = "prod_unarchive_activate_fail"
    plan.is_archived = True
    plan.archived_at = datetime.now(timezone.utc)
    db.add(plan)
    db.commit()

    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.activate_stripe_plan_artifacts",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("forced unarchive activation failure")),
    )

    response = client.post(
        f"/api/v1/admin/plans/{plan.id}/unarchive",
        headers=admin_headers,
        json={"reason": "restore"},
    )
    assert response.status_code == 502, response.text
    assert response.json() == {"detail": "Failed to reactivate Stripe plan artifacts"}

    db.refresh(plan)
    assert plan.is_archived is True
    assert plan.archived_at is not None


def test_admin_plan_archive_commit_failure_returns_persistence_error(
    client,
    db,
    user_factory,
    auth_headers,
    plan_factory,
    monkeypatch,
):
    from sqlalchemy.orm.session import Session as SQLAlchemySession

    _admin, admin_headers = _create_admin_and_headers(user_factory, auth_headers)
    plan = plan_factory(name="Archive Commit Failure Plan", stripe_price_id="price_archive_commit_fail")
    db.add(plan)
    db.commit()

    original_commit = SQLAlchemySession.commit
    commit_calls = {"count": 0}

    def _fail_first_commit(self, *args, **kwargs):
        if commit_calls["count"] == 0:
            commit_calls["count"] += 1
            raise SQLAlchemyError("forced archive commit failure")
        return original_commit(self, *args, **kwargs)

    monkeypatch.setattr(SQLAlchemySession, "commit", _fail_first_commit)

    response = client.post(
        f"/api/v1/admin/plans/{plan.id}/archive",
        headers=admin_headers,
        json={"reason": "retire"},
    )
    assert response.status_code == 500, response.text
    assert response.json() == {"detail": "Failed to persist plan archive"}

    db.refresh(plan)
    assert plan.is_archived is False
    assert plan.archived_at is None


def test_admin_plan_unarchive_commit_failure_returns_persistence_error(
    client,
    db,
    user_factory,
    auth_headers,
    plan_factory,
    monkeypatch,
):
    from sqlalchemy.orm.session import Session as SQLAlchemySession

    _admin, admin_headers = _create_admin_and_headers(user_factory, auth_headers)
    plan = plan_factory(name="Unarchive Commit Failure Plan", stripe_price_id="price_unarchive_commit_fail")
    plan.stripe_product_id = "prod_unarchive_commit_fail"
    plan.is_archived = True
    plan.archived_at = datetime.now(timezone.utc)
    db.add(plan)
    db.commit()

    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.activate_stripe_plan_artifacts",
        lambda **_kwargs: {"price_activated": True, "product_activated": True},
    )
    deactivate_calls = {"count": 0}

    def _deactivate_artifacts(**_kwargs):
        deactivate_calls["count"] += 1
        return {"price_deactivated": True, "product_deactivated": True}

    monkeypatch.setattr(
        "app.services.payment_service.PaymentService.deactivate_stripe_plan_artifacts",
        _deactivate_artifacts,
    )

    original_commit = SQLAlchemySession.commit
    commit_calls = {"count": 0}

    def _fail_first_commit(self, *args, **kwargs):
        if commit_calls["count"] == 0:
            commit_calls["count"] += 1
            raise SQLAlchemyError("forced unarchive commit failure")
        return original_commit(self, *args, **kwargs)

    monkeypatch.setattr(SQLAlchemySession, "commit", _fail_first_commit)

    response = client.post(
        f"/api/v1/admin/plans/{plan.id}/unarchive",
        headers=admin_headers,
        json={"reason": "restore"},
    )
    assert response.status_code == 500, response.text
    assert response.json() == {"detail": "Failed to persist plan unarchive"}
    assert deactivate_calls["count"] == 1

    db.refresh(plan)
    assert plan.is_archived is True
    assert plan.archived_at is not None


def test_admin_plan_list_filters(client, db, user_factory, auth_headers, plan_factory):
    _admin, admin_headers = _create_admin_and_headers(user_factory, auth_headers)
    now = datetime.now(timezone.utc)

    active_plan = plan_factory(name="FilterActive", stripe_price_id="price_filter_active")
    archived_plan = plan_factory(name="FilterArchived", stripe_price_id="price_filter_archived")
    future_plan = plan_factory(name="FilterFuture", stripe_price_id="price_filter_future")

    archived_plan.is_archived = True
    archived_plan.archived_at = now
    archived_plan.features = {"credits_total": 10, "catalog_visible": True}
    future_plan.effective_from = now + timedelta(days=3)
    future_plan.features = {"credits_total": 10, "catalog_visible": True}
    active_plan.features = {"credits_total": 10, "catalog_visible": True}
    db.commit()

    archived_only = client.get(
        "/api/v1/admin/plans?archived=archived",
        headers=admin_headers,
    )
    assert archived_only.status_code == 200, archived_only.text
    archived_ids = {item["id"] for item in archived_only.json()["items"]}
    assert archived_plan.id in archived_ids
    assert active_plan.id not in archived_ids

    unarchived_only = client.get(
        "/api/v1/admin/plans?archived=unarchived",
        headers=admin_headers,
    )
    assert unarchived_only.status_code == 200, unarchived_only.text
    unarchived_ids = {item["id"] for item in unarchived_only.json()["items"]}
    assert active_plan.id in unarchived_ids
    assert archived_plan.id not in unarchived_ids

    effective_now = client.get(
        "/api/v1/admin/plans",
        headers=admin_headers,
        params={"effective_at": now.isoformat()},
    )
    assert effective_now.status_code == 200, effective_now.text
    effective_ids = {item["id"] for item in effective_now.json()["items"]}
    assert active_plan.id in effective_ids
    assert future_plan.id not in effective_ids


def test_admin_plan_list_pagination_and_managed_offer_exclusion(
    client,
    db,
    user_factory,
    auth_headers,
    plan_factory,
):
    _admin, admin_headers = _create_admin_and_headers(user_factory, auth_headers)

    paged_plans = []
    for index in range(5):
        plan = plan_factory(
            name=f"PagedPlan{index}",
            stripe_price_id=f"price_paged_plan_{index}",
        )
        plan.features = {"credits_total": 10, "catalog_visible": True}
        paged_plans.append(plan)

    managed_plan = plan_factory(
        name="PagedPlan Managed",
        stripe_price_id="price_paged_plan_managed",
    )
    managed_plan.features = {
        "managed_by": "first_purchase_offer",
        "catalog_visible": False,
    }
    db.commit()

    page_one = client.get(
        "/api/v1/admin/plans?page=1&size=2&search=PagedPlan",
        headers=admin_headers,
    )
    assert page_one.status_code == 200, page_one.text
    page_one_payload = page_one.json()
    assert page_one_payload["total"] == 5
    assert len(page_one_payload["items"]) == 2

    page_two = client.get(
        "/api/v1/admin/plans?page=2&size=2&search=PagedPlan",
        headers=admin_headers,
    )
    assert page_two.status_code == 200, page_two.text
    page_two_payload = page_two.json()
    assert page_two_payload["total"] == 5
    assert len(page_two_payload["items"]) == 2

    page_three = client.get(
        "/api/v1/admin/plans?page=3&size=2&search=PagedPlan",
        headers=admin_headers,
    )
    assert page_three.status_code == 200, page_three.text
    page_three_payload = page_three.json()
    assert page_three_payload["total"] == 5
    assert len(page_three_payload["items"]) == 1
    assert {
        item["id"]
        for item in [*page_one_payload["items"], *page_two_payload["items"], *page_three_payload["items"]]
    } == {int(plan.id) for plan in paged_plans}
    assert all(
        item["id"] != managed_plan.id
        for item in [*page_one_payload["items"], *page_two_payload["items"], *page_three_payload["items"]]
    )


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


def test_admin_orders_export_returns_csv_with_dollar_amounts(
    client,
    db,
    user_factory,
    auth_headers,
    plan_factory,
    purchase_factory,
):
    _admin, admin_headers = _create_admin_and_headers(user_factory, auth_headers)
    advisor = user_factory(
        role="advisor",
        password="OrdersExport123!",
        email="orders.export@example.com",
        name="Orders Export Advisor",
    )
    starter_plan = plan_factory(name="OrderExportStarter", price_cents=12345, daily_download_limit=7)
    pro_plan = plan_factory(name="OrderExportPro", price_cents=25000, daily_download_limit=25)

    completed_purchase = purchase_factory(
        user_id=advisor.id,
        package_id=starter_plan.id,
        status="completed",
        credits_total=7,
        credits_remaining=5,
        stripe_checkout_session_id="cs_orders_export_completed_1",
    )
    purchase_factory(
        user_id=advisor.id,
        package_id=pro_plan.id,
        status="canceled",
        credits_total=25,
        credits_remaining=25,
        stripe_checkout_session_id="cs_orders_export_canceled_1",
    )
    completed_purchase.amount_cents = 12345
    completed_purchase.currency = "USD"
    db.add(completed_purchase)
    db.commit()
    db.refresh(completed_purchase)

    export_response = client.get(
        "/api/v1/admin/orders/export?status=completed",
        headers=admin_headers,
    )
    assert export_response.status_code == 200, export_response.text
    assert export_response.headers["content-type"].startswith("text/csv")
    assert "attachment; filename=admin_orders_" in export_response.headers.get("content-disposition", "")

    reader = csv.DictReader(io.StringIO(export_response.text))
    rows = list(reader)
    assert len(rows) == 1
    row = rows[0]
    assert row["order_reference"] == "cs_orders_export_completed_1"
    assert row["advisor_name"] == advisor.name
    assert row["advisor_email"] == advisor.email
    assert row["package_name"] == starter_plan.name
    assert row["quantity"] == "7"
    assert row["remaining_credits"] == "5"
    assert row["status"] == "completed"
    assert row["amount_dollars"] == "123.45"
    assert row["currency"] == "USD"
    assert row["created_at"] == completed_purchase.purchased_at.isoformat()


def test_admin_orders_export_neutralizes_formula_like_advisor_identity_cells(
    client,
    db,
    user_factory,
    auth_headers,
    plan_factory,
    purchase_factory,
):
    _admin, admin_headers = _create_admin_and_headers(user_factory, auth_headers)
    advisor = user_factory(
        role="advisor",
        password="OrdersExportInject123!",
        email="+orders.inject@example.com",
        name="=Orders Export Advisor",
    )
    plan = plan_factory(name="OrderExportInjectPlan", price_cents=18000, daily_download_limit=12)
    purchase = purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        status="completed",
        credits_total=12,
        credits_remaining=10,
        stripe_checkout_session_id="cs_orders_export_inject_1",
    )
    purchase.amount_cents = 18000
    purchase.currency = "USD"
    db.add(purchase)
    db.commit()
    db.refresh(purchase)

    export_response = client.get(
        "/api/v1/admin/orders/export?status=completed",
        headers=admin_headers,
    )
    assert export_response.status_code == 200, export_response.text

    reader = csv.DictReader(io.StringIO(export_response.text))
    rows = list(reader)
    assert len(rows) == 1
    row = rows[0]
    assert row["advisor_name"] == "'=Orders Export Advisor"
    assert row["advisor_email"] == "'+orders.inject@example.com"


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
    user_factory(
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
    assert payload["recent_activity"][0]["actor_user_id"] == advisor.id

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
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": advisor.email, "password": "Deactivate123!"},
    )
    assert login_response.status_code == 204, login_response.text
    advisor_access = login_response.cookies.get(settings.AUTH_ACCESS_COOKIE_NAME)
    advisor_refresh = login_response.cookies.get(settings.AUTH_REFRESH_COOKIE_NAME)
    advisor_csrf = login_response.cookies.get(settings.AUTH_CSRF_COOKIE_NAME)
    assert advisor_access
    assert advisor_refresh
    assert advisor_csrf

    advisor_cookie_header = (
        f"{settings.AUTH_ACCESS_COOKIE_NAME}={advisor_access}; "
        f"{settings.AUTH_REFRESH_COOKIE_NAME}={advisor_refresh}; "
        f"{settings.AUTH_CSRF_COOKIE_NAME}={advisor_csrf}"
    )
    advisor_headers = {
        "Cookie": advisor_cookie_header,
        settings.AUTH_CSRF_HEADER_NAME: advisor_csrf,
    }

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

    refresh_response = client.post("/api/v1/auth/refresh", headers=advisor_headers)
    assert refresh_response.status_code == 401

    me_response = client.get("/api/v1/auth/me", headers=advisor_headers)
    assert me_response.status_code == 401

    login_after_deactivation = client.post(
        "/api/v1/auth/login",
        json={"email": advisor.email, "password": "Deactivate123!"},
    )
    assert login_after_deactivation.status_code == 403
    assert login_after_deactivation.json() == {"detail": "Inactive user account"}

    db.expire_all()
    sessions = (
        db.query(RefreshTokenSession)
        .filter(RefreshTokenSession.user_id == advisor.id)
        .all()
    )
    assert sessions
    assert all(session.revoked_at is not None for session in sessions)
    assert all(session.revoked_reason == "user_deactivated" for session in sessions)


def test_admin_deactivate_blocks_self_and_admin_targets(
    client,
    db,
    user_factory,
    auth_headers,
):
    admin, admin_headers = _create_admin_and_headers(user_factory, auth_headers)
    peer_admin = user_factory(
        role="admin",
        password="PeerAdmin123!",
        email="peer.admin@example.com",
        name="Peer Admin",
    )

    self_response = client.post(
        f"/api/v1/admin/users/{admin.id}/deactivate",
        headers=admin_headers,
        json={"reason": "Self attempt"},
    )
    assert self_response.status_code == 400, self_response.text
    assert self_response.json() == {"detail": "Admins cannot deactivate their own account"}

    peer_response = client.post(
        f"/api/v1/admin/users/{peer_admin.id}/deactivate",
        headers=admin_headers,
        json={"reason": "Peer attempt"},
    )
    assert peer_response.status_code == 400, peer_response.text
    assert peer_response.json() == {
        "detail": "Admin accounts cannot be deactivated from this endpoint"
    }

    db.expire_all()
    refreshed_admin = db.query(User).filter(User.id == admin.id).first()
    refreshed_peer_admin = db.query(User).filter(User.id == peer_admin.id).first()
    assert refreshed_admin is not None
    assert refreshed_peer_admin is not None
    assert refreshed_admin.is_active is True
    assert refreshed_peer_admin.is_active is True
    assert refreshed_admin.deactivated_at is None
    assert refreshed_peer_admin.deactivated_at is None

    deactivation_audits = (
        db.query(AuditLog)
        .filter(
            AuditLog.actor_user_id == admin.id,
            AuditLog.action == "user_deactivated",
            AuditLog.entity_type == "User",
            AuditLog.entity_id.in_([admin.id, peer_admin.id]),
        )
        .all()
    )
    assert deactivation_audits == []


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
