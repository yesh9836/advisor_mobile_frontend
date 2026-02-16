import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.models.lead import LeadDownload
from app.services.lead_service import LeadService


@pytest.mark.unit
def test_can_user_download_leads_returns_false_without_credits_or_subscription(
    db,
    user_factory,
):
    advisor = user_factory(
        role="advisor",
        password="LeadUnit123!",
        email="lead.unit.no.sub@example.com",
    )

    result = LeadService.can_user_download_leads(db=db, user=advisor)
    assert result == {
        "can_download": False,
        "reason": "No remaining lead credits",
        "remaining": 0,
    }


@pytest.mark.unit
def test_can_user_download_leads_uses_purchase_credits_without_subscription(
    db,
    user_factory,
    plan_factory,
    license_factory,
    purchase_factory,
    lead_factory,
):
    advisor = user_factory(
        role="advisor",
        password="LeadUnitCredit123!",
        email="lead.unit.credit@example.com",
    )
    plan = plan_factory(
        daily_download_limit=5,
        state_limit=1,
        stripe_price_id="price_credit_mode",
    )
    license_factory(user_id=advisor.id, state="CA", status="verified")
    purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        credits_total=3,
        credits_remaining=2,
    )
    lead_factory(state_code="CA", mobile_phone="555-CREDIT-0001")
    _ = plan

    result = LeadService.can_user_download_leads(db=db, user=advisor)
    assert result["can_download"] is True
    assert result["remaining"] == 2


@pytest.mark.unit
def test_can_user_download_leads_requires_verified_license_states(
    db,
    user_factory,
    plan_factory,
    purchase_factory,
    lead_factory,
):
    advisor = user_factory(
        role="advisor",
        password="LeadUnitDaily123!",
        email="lead.unit.daily@example.com",
    )
    plan = plan_factory(
        daily_download_limit=2,
        state_limit=1,
        stripe_price_id="price_daily_limit",
    )
    purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        credits_total=2,
        credits_remaining=2,
        status="completed",
    )
    lead_factory(state_code="CA", mobile_phone="555-DL-0001")

    result = LeadService.can_user_download_leads(db=db, user=advisor)
    assert result == {
        "can_download": False,
        "reason": "No verified license states",
        "remaining": 2,
    }


@pytest.mark.unit
def test_get_available_leads_for_user_returns_empty_for_no_matching_state(
    db,
    user_factory,
    plan_factory,
    license_factory,
    purchase_factory,
    lead_factory,
):
    advisor = user_factory(
        role="advisor",
        password="LeadUnitState123!",
        email="lead.unit.state@example.com",
    )
    plan = plan_factory(state_limit=1, stripe_price_id="price_state_limit")
    license_factory(user_id=advisor.id, state="CA", status="verified")
    purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        credits_total=5,
        credits_remaining=5,
        status="completed",
    )
    lead_factory(state_code="NY", mobile_phone="555-NY-9001")

    data = LeadService.get_available_leads_for_user(db=db, user=advisor, page=1, size=20)
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.unit
def test_can_user_download_leads_requires_available_new_inventory(
    db,
    user_factory,
    plan_factory,
    license_factory,
    purchase_factory,
):
    advisor = user_factory(
        role="advisor",
        password="LeadUnitInventory123!",
        email="lead.unit.inventory@example.com",
    )
    plan = plan_factory(
        daily_download_limit=5,
        state_limit=1,
        stripe_price_id="price_inventory_check",
    )
    license_factory(user_id=advisor.id, state="CA", status="verified")
    purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        credits_total=2,
        credits_remaining=2,
        status="completed",
    )

    result = LeadService.can_user_download_leads(db=db, user=advisor)
    assert result == {
        "can_download": False,
        "reason": "No leads available",
        "remaining": 2,
    }


@pytest.mark.unit
def test_bulk_import_leads_rejects_duplicate_phones_in_payload(db):
    rows = [
        {"state_code": "CA", "mobile_phone": "555-DUPE-1", "first_name": "A"},
        {"state_code": "CA", "mobile_phone": "555-DUPE-1", "first_name": "B"},
    ]

    result = LeadService.bulk_import_leads(db=db, csv_data=rows)
    assert result["success"] == 0
    assert result["failed"] >= 1
    assert any("Duplicate mobile_phone in file" in err["error"] for err in result["errors"])


@pytest.mark.unit
def test_lead_download_has_unique_user_lead_constraint(
    db,
    user_factory,
    lead_factory,
):
    advisor = user_factory(
        role="advisor",
        password="LeadUnitUnique123!",
        email="lead.unit.unique@example.com",
    )
    lead = lead_factory(state_code="CA", mobile_phone="555-UNIQ-0001")

    db.add(LeadDownload(user_id=advisor.id, lead_id=lead.id, csv_batch_id="batch_1"))
    db.commit()

    db.add(LeadDownload(user_id=advisor.id, lead_id=lead.id, csv_batch_id="batch_2"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


@pytest.mark.unit
def test_lead_download_has_global_unique_lead_owner_constraint(
    db,
    user_factory,
    lead_factory,
):
    first_advisor = user_factory(
        role="advisor",
        password="LeadUnitGlobalOwnerOne123!",
        email="lead.unit.global.owner.one@example.com",
    )
    second_advisor = user_factory(
        role="advisor",
        password="LeadUnitGlobalOwnerTwo123!",
        email="lead.unit.global.owner.two@example.com",
    )
    lead = lead_factory(state_code="CA", mobile_phone="555-GLOBAL-UNIQ-0001")

    db.add(LeadDownload(user_id=first_advisor.id, lead_id=lead.id, csv_batch_id="batch_first"))
    db.commit()

    db.add(LeadDownload(user_id=second_advisor.id, lead_id=lead.id, csv_batch_id="batch_second"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


@pytest.mark.unit
def test_download_leads_csv_enforces_credit_exhaustion_inside_transaction(
    db,
    user_factory,
    plan_factory,
    license_factory,
    purchase_factory,
    lead_factory,
):
    advisor = user_factory(
        role="advisor",
        password="LeadUnitLimit123!",
        email="lead.unit.limit@example.com",
    )
    plan = plan_factory(
        daily_download_limit=10,
        state_limit=1,
        stripe_price_id="price_download_credit_1",
    )
    license_factory(user_id=advisor.id, state="CA", status="verified")
    purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        credits_total=1,
        credits_remaining=1,
        status="completed",
    )
    lead_factory(state_code="CA", mobile_phone="555-LIMIT-0001")
    lead_factory(state_code="CA", mobile_phone="555-LIMIT-0002")

    first_csv = "".join(LeadService.download_leads_csv(db=db, user=advisor))
    assert "state_code" in first_csv
    assert db.query(LeadDownload).count() == 1

    with pytest.raises(HTTPException) as exc_info:
        LeadService.download_leads_csv(db=db, user=advisor)
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "No remaining lead credits"


@pytest.mark.unit
def test_download_leads_csv_credit_denial_emits_metrics(
    db,
    monkeypatch,
    user_factory,
):
    advisor = user_factory(
        role="advisor",
        password="LeadUnitDeniedMetrics123!",
        email="lead.unit.denied.metrics@example.com",
    )
    metric_counters = []
    metric_histograms = []

    monkeypatch.setattr(
        "app.services.lead_service.MetricsService.increment",
        lambda name, value=1, tags=None: metric_counters.append((name, value, tags or {})),
    )
    monkeypatch.setattr(
        "app.services.lead_service.MetricsService.histogram",
        lambda name, value, tags=None: metric_histograms.append((name, value, tags or {})),
    )

    with pytest.raises(HTTPException) as exc_info:
        LeadService.download_leads_csv(db=db, user=advisor)
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "No remaining lead credits"
    assert any(name == "lead_download_credit_denied_total" for name, _, _ in metric_counters)
    assert any(name == "lead_download_credit_denied_remaining_credits" for name, _, _ in metric_histograms)


@pytest.mark.unit
def test_download_leads_csv_retries_once_on_unique_conflict(
    db,
    monkeypatch,
    user_factory,
    plan_factory,
    license_factory,
    purchase_factory,
    lead_factory,
):
    advisor = user_factory(
        role="advisor",
        password="LeadUnitRetry123!",
        email="lead.unit.retry@example.com",
    )
    plan = plan_factory(
        daily_download_limit=5,
        state_limit=1,
        stripe_price_id="price_download_retry",
    )
    license_factory(user_id=advisor.id, state="CA", status="verified")
    purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        credits_total=5,
        credits_remaining=5,
        status="completed",
    )
    lead_factory(state_code="CA", mobile_phone="555-RETRY-0001")

    original_record_download_batch = LeadService._record_download_batch
    state = {"raised": False}

    def flaky_record_download_batch(*, db, user_id, leads, purchase_ids_by_lead_id=None):
        if not state["raised"]:
            state["raised"] = True
            raise IntegrityError(
                "INSERT INTO lead_downloads ...",
                {},
                Exception("Duplicate entry '1-1' for key 'uq_lead_downloads_user_lead'"),
            )
        return original_record_download_batch(
            db=db,
            user_id=user_id,
            leads=leads,
            purchase_ids_by_lead_id=purchase_ids_by_lead_id,
        )

    monkeypatch.setattr(LeadService, "_record_download_batch", staticmethod(flaky_record_download_batch))

    csv_stream = LeadService.download_leads_csv(db=db, user=advisor)
    csv_text = "".join(csv_stream)

    assert "state_code" in csv_text
    assert state["raised"] is True
    assert db.query(LeadDownload).count() == 1


@pytest.mark.unit
def test_download_delivered_leads_csv_does_not_consume_credits(
    db,
    user_factory,
    plan_factory,
    license_factory,
    purchase_factory,
    lead_factory,
):
    advisor = user_factory(
        role="advisor",
        password="LeadUnitDelivered123!",
        email="lead.unit.delivered@example.com",
    )
    plan = plan_factory(
        daily_download_limit=5,
        state_limit=1,
        stripe_price_id="price_delivered_redownload",
    )
    license_factory(user_id=advisor.id, state="CA", status="verified")
    purchase = purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        credits_total=3,
        credits_remaining=0,
        status="completed",
    )
    lead = lead_factory(state_code="CA", mobile_phone="555-DELIVERED-0001")
    db.add(
        LeadDownload(
            user_id=advisor.id,
            lead_id=lead.id,
            purchase_id=purchase.id,
            csv_batch_id="batch_delivered",
        )
    )
    db.commit()

    csv_text = "".join(LeadService.download_delivered_leads_csv(db=db, user=advisor))
    db.refresh(purchase)

    assert "state_code" in csv_text
    assert "555-DELIVERED-0001" in csv_text
    assert purchase.credits_remaining == 0


@pytest.mark.unit
def test_download_leads_csv_emits_purchase_credit_consumed_audit_events(
    db,
    monkeypatch,
    user_factory,
    plan_factory,
    license_factory,
    purchase_factory,
    lead_factory,
):
    advisor = user_factory(
        role="advisor",
        password="LeadUnitConsumedAudit123!",
        email="lead.unit.consumed.audit@example.com",
    )
    plan = plan_factory(
        daily_download_limit=5,
        state_limit=1,
        stripe_price_id="price_consumed_audit",
    )
    license_factory(user_id=advisor.id, state="CA", status="verified")
    purchase = purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        credits_total=2,
        credits_remaining=2,
        status="completed",
    )
    lead_factory(state_code="CA", mobile_phone="555-CONSUMED-AUDIT-0001")
    captured_events = []
    monkeypatch.setattr(
        "app.services.lead_service.AuditService.log_purchase_event",
        lambda **kwargs: captured_events.append(kwargs),
    )

    csv_text = "".join(LeadService.download_leads_csv(db=db, user=advisor))
    assert "state_code" in csv_text

    assert len(captured_events) == 1
    consumed_event = captured_events[0]
    assert consumed_event["actor_user_id"] == advisor.id
    assert consumed_event["action"] == "purchase_credit_consumed"
    assert consumed_event["purchase_id"] == purchase.id
    assert consumed_event["credits_delta"] == -1
    assert consumed_event["correlation_ids"]["purchase_id"] == purchase.id
