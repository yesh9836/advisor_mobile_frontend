from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.models.lead import LeadDownload, LeadOwnership
from app.models.purchase import LeadCreditLedger
from app.schemas.lead import LeadCreate, LeadOutcomeUpdateRequest
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
def test_get_available_leads_for_user_hides_unsold_inventory_without_remaining_credits(
    db,
    user_factory,
    plan_factory,
    license_factory,
    purchase_factory,
    lead_factory,
):
    advisor = user_factory(
        role="advisor",
        password="LeadUnitNoCreditList123!",
        email="lead.unit.no.credit.list@example.com",
    )
    plan = plan_factory(state_limit=1, stripe_price_id="price_list_no_credits")
    license_factory(user_id=advisor.id, state="CA", status="verified")
    purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        credits_total=2,
        credits_remaining=0,
        status="completed",
    )
    lead_factory(state_code="CA", mobile_phone="555-NOCREDIT-9001")

    data = LeadService.get_available_leads_for_user(
        db=db,
        user=advisor,
        page=1,
        size=20,
        delivery_status="available",
    )
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.unit
def test_get_available_leads_for_user_applies_search_filter(
    db,
    user_factory,
    plan_factory,
    license_factory,
    purchase_factory,
    lead_factory,
):
    advisor = user_factory(
        role="advisor",
        password="LeadUnitSearch123!",
        email="lead.unit.search@example.com",
    )
    plan = plan_factory(state_limit=1, stripe_price_id="price_state_search")
    license_factory(user_id=advisor.id, state="CA", status="verified")
    purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        credits_total=5,
        credits_remaining=5,
        status="completed",
    )
    casey = lead_factory(
        state_code="CA",
        mobile_phone="555-SEARCH-9001",
        first_name="Casey",
        last_name="Advisor",
    )
    lead_factory(
        state_code="CA",
        mobile_phone="555-SEARCH-9002",
        first_name="Taylor",
        last_name="Advisor",
    )

    data = LeadService.get_available_leads_for_user(
        db=db,
        user=advisor,
        page=1,
        size=20,
        search=" casey ",
    )

    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0].id == casey.id


@pytest.mark.unit
def test_get_available_leads_for_user_search_supports_tokenized_name_and_state_matching(
    db,
    user_factory,
    plan_factory,
    license_factory,
    purchase_factory,
    lead_factory,
):
    advisor = user_factory(
        role="advisor",
        password="LeadUnitTokenSearch123!",
        email="lead.unit.token.search@example.com",
    )
    plan = plan_factory(state_limit=2, stripe_price_id="price_state_token_search")
    license_factory(user_id=advisor.id, state="CA", status="verified")
    purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        credits_total=5,
        credits_remaining=5,
        status="completed",
    )
    matching_lead = lead_factory(
        state_code="CA",
        mobile_phone="555-333-9001",
        first_name="Casey",
        last_name="Advisor",
    )
    lead_factory(
        state_code="CA",
        mobile_phone="555-333-9002",
        first_name="Taylor",
        last_name="Advisor",
    )

    data = LeadService.get_available_leads_for_user(
        db=db,
        user=advisor,
        page=1,
        size=20,
        search="casey ca",
    )

    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0].id == matching_lead.id


@pytest.mark.unit
def test_get_available_leads_for_user_search_supports_phone_digit_tokens(
    db,
    user_factory,
    plan_factory,
    license_factory,
    purchase_factory,
    lead_factory,
):
    advisor = user_factory(
        role="advisor",
        password="LeadUnitPhoneSearch123!",
        email="lead.unit.phone.search@example.com",
    )
    plan = plan_factory(state_limit=1, stripe_price_id="price_phone_search")
    license_factory(user_id=advisor.id, state="CA", status="verified")
    purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        credits_total=5,
        credits_remaining=5,
        status="completed",
    )
    matching_lead = lead_factory(
        state_code="CA",
        mobile_phone="555-SEARCH-9012",
        first_name="Jordan",
        last_name="Phone",
    )
    lead_factory(
        state_code="CA",
        mobile_phone="555-SEARCH-1234",
        first_name="Taylor",
        last_name="Phone",
    )

    data = LeadService.get_available_leads_for_user(
        db=db,
        user=advisor,
        page=1,
        size=20,
        search="9012",
    )

    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0].id == matching_lead.id


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
    assert result["failed"] == 1
    assert any("Duplicate mobile_phone in file" in err["error"] for err in result["errors"])


@pytest.mark.unit
def test_bulk_import_leads_rejects_same_phone_with_and_without_plus_one(db):
    rows = [
        {"state_code": "CA", "mobile_phone": "3054959490", "first_name": "A"},
        {"state_code": "CA", "mobile_phone": "+13054959490", "first_name": "B"},
    ]

    result = LeadService.bulk_import_leads(db=db, csv_data=rows)
    assert result["success"] == 0
    assert result["failed"] == 1
    assert any("Duplicate mobile_phone in file" in err["error"] for err in result["errors"])


@pytest.mark.unit
def test_bulk_import_leads_counts_failed_rows_not_error_count(db):
    rows = [
        {"state_code": "ZZ", "mobile_phone": "", "first_name": "Bad"},
    ]

    result = LeadService.bulk_import_leads(db=db, csv_data=rows)
    assert result["success"] == 0
    assert result["failed"] == 1
    assert len(result["errors"]) == 2
    assert {err["error"] for err in result["errors"]} == {
        "Invalid state_code",
        "Missing mobile_phone",
    }
    assert {err["row"] for err in result["errors"]} == {2}


@pytest.mark.unit
def test_create_lead_normalizes_10_digit_mobile_phone_to_plus_one(db):
    lead = LeadService.create_lead(
        db=db,
        data=LeadCreate(
            state_code="CA",
            mobile_phone="3054959490",
            first_name="Phone",
            last_name="Normalized",
            source="manual_entry",
        ),
    )

    assert lead.mobile_phone == "+13054959490"


@pytest.mark.unit
def test_lead_download_is_append_only_for_same_user_and_lead(
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
    db.commit()

    rows = (
        db.query(LeadDownload)
        .filter(LeadDownload.user_id == advisor.id, LeadDownload.lead_id == lead.id)
        .order_by(LeadDownload.id.asc())
        .all()
    )
    assert len(rows) == 2
    assert rows[0].csv_batch_id == "batch_1"
    assert rows[1].csv_batch_id == "batch_2"


@pytest.mark.unit
def test_lead_ownership_has_global_unique_lead_owner_constraint(
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

    db.add(LeadOwnership(user_id=first_advisor.id, lead_id=lead.id))
    db.commit()

    db.add(LeadOwnership(user_id=second_advisor.id, lead_id=lead.id))
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
def test_download_delivered_leads_csv_deduplicates_same_lead(
    db,
    user_factory,
    lead_factory,
):
    advisor = user_factory(
        role="advisor",
        password="LeadUnitDeliveredDedup123!",
        email="lead.unit.delivered.dedup@example.com",
    )
    repeated = lead_factory(state_code="CA", mobile_phone="555-DELIVERED-DEDUP-0001")
    second = lead_factory(state_code="CA", mobile_phone="555-DELIVERED-DEDUP-0002")

    db.add(
        LeadDownload(
            user_id=advisor.id,
            lead_id=repeated.id,
            csv_batch_id="batch_delivered_dedup_a",
        )
    )
    db.add(
        LeadDownload(
            user_id=advisor.id,
            lead_id=repeated.id,
            csv_batch_id="batch_delivered_dedup_b",
        )
    )
    db.add(
        LeadDownload(
            user_id=advisor.id,
            lead_id=second.id,
            csv_batch_id="batch_delivered_dedup_b",
        )
    )
    db.commit()

    csv_text = "".join(LeadService.download_delivered_leads_csv(db=db, user=advisor))

    assert csv_text.count("555-DELIVERED-DEDUP-0001") == 1
    assert csv_text.count("555-DELIVERED-DEDUP-0002") == 1


@pytest.mark.unit
def test_upsert_lead_outcome_rejects_licensed_state_lead_without_delivery_or_ownership(
    db,
    user_factory,
    plan_factory,
    license_factory,
    purchase_factory,
    lead_factory,
):
    advisor = user_factory(
        role="advisor",
        password="LeadUnitOutcomeDeny123!",
        email="lead.unit.outcome.deny@example.com",
    )
    plan = plan_factory(state_limit=1, stripe_price_id="price_outcome_deny")
    license_factory(user_id=advisor.id, state="CA", status="verified")
    purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        credits_total=2,
        credits_remaining=2,
        status="completed",
    )
    lead = lead_factory(state_code="CA", mobile_phone="555-OUTCOME-DENY-0001")

    with pytest.raises(HTTPException) as exc_info:
        LeadService.upsert_lead_outcome(
            db=db,
            user=advisor,
            lead_id=lead.id,
            payload=LeadOutcomeUpdateRequest(status="contacted", notes="No access"),
        )
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Lead not found"


@pytest.mark.unit
def test_upsert_lead_outcome_allows_delivered_lead(
    db,
    user_factory,
    lead_factory,
):
    advisor = user_factory(
        role="advisor",
        password="LeadUnitOutcomeDelivered123!",
        email="lead.unit.outcome.delivered@example.com",
    )
    lead = lead_factory(state_code="CA", mobile_phone="555-OUTCOME-ALLOW-0001")
    db.add(
        LeadDownload(
            user_id=advisor.id,
            lead_id=lead.id,
            csv_batch_id="batch_unit_outcome_delivered",
        )
    )
    db.commit()

    outcome = LeadService.upsert_lead_outcome(
        db=db,
        user=advisor,
        lead_id=lead.id,
        payload=LeadOutcomeUpdateRequest(status="appointment_set", notes="Delivered access"),
    )

    assert outcome.user_id == advisor.id
    assert outcome.lead_id == lead.id
    assert outcome.status == "appointment_set"
    assert outcome.notes == "Delivered access"


@pytest.mark.unit
def test_upsert_lead_outcome_allows_owned_lead_before_download(
    db,
    user_factory,
    lead_factory,
):
    advisor = user_factory(
        role="advisor",
        password="LeadUnitOutcomeOwned123!",
        email="lead.unit.outcome.owned@example.com",
    )
    lead = lead_factory(state_code="CA", mobile_phone="555-OUTCOME-ALLOW-0002")
    db.add(LeadOwnership(user_id=advisor.id, lead_id=lead.id))
    db.commit()

    outcome = LeadService.upsert_lead_outcome(
        db=db,
        user=advisor,
        lead_id=lead.id,
        payload=LeadOutcomeUpdateRequest(status="contacted", notes="Owned access"),
    )

    assert outcome.user_id == advisor.id
    assert outcome.lead_id == lead.id
    assert outcome.status == "contacted"
    assert outcome.notes == "Owned access"


@pytest.mark.unit
def test_get_available_leads_for_user_uses_owned_scope_when_present(
    db,
    user_factory,
    plan_factory,
    license_factory,
    purchase_factory,
    lead_factory,
):
    advisor = user_factory(
        role="advisor",
        password="LeadUnitOwnedScope123!",
        email="lead.unit.owned.scope@example.com",
    )
    plan = plan_factory(
        daily_download_limit=5,
        state_limit=1,
        stripe_price_id="price_owned_scope",
    )
    license_factory(user_id=advisor.id, state="CA", status="verified")
    purchase = purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        credits_total=2,
        credits_remaining=2,
        status="completed",
    )
    owned_a = lead_factory(state_code="CA", mobile_phone="555-OWN-SCOPE-0001")
    owned_b = lead_factory(state_code="CA", mobile_phone="555-OWN-SCOPE-0002")
    unowned = lead_factory(state_code="CA", mobile_phone="555-OWN-SCOPE-0003")
    _ = unowned
    db.add(
        LeadOwnership(
            user_id=advisor.id,
            lead_id=owned_a.id,
            purchase_id=purchase.id,
        )
    )
    db.add(
        LeadOwnership(
            user_id=advisor.id,
            lead_id=owned_b.id,
            purchase_id=purchase.id,
        )
    )
    db.add(
        LeadDownload(
            user_id=advisor.id,
            lead_id=owned_a.id,
            purchase_id=purchase.id,
            csv_batch_id="batch_owned_scope",
        )
    )
    db.commit()

    all_data = LeadService.get_available_leads_for_user(
        db=db,
        user=advisor,
        page=1,
        size=20,
        delivery_status="all",
    )
    assert all_data["total"] == 2

    delivered_data = LeadService.get_available_leads_for_user(
        db=db,
        user=advisor,
        page=1,
        size=20,
        delivery_status="delivered",
    )
    assert delivered_data["total"] == 1
    assert delivered_data["items"][0].id == owned_a.id

    available_data = LeadService.get_available_leads_for_user(
        db=db,
        user=advisor,
        page=1,
        size=20,
        delivery_status="available",
    )
    assert available_data["total"] == 1
    assert available_data["items"][0].id == owned_b.id


@pytest.mark.unit
def test_download_leads_csv_exports_owned_leads_without_consuming_credits(
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
        password="LeadUnitOwnedExport123!",
        email="lead.unit.owned.export@example.com",
    )
    plan = plan_factory(
        daily_download_limit=5,
        state_limit=1,
        stripe_price_id="price_owned_export",
    )
    license_factory(user_id=advisor.id, state="CA", status="verified")
    purchase = purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        credits_total=2,
        credits_remaining=2,
        status="completed",
    )
    owned_a = lead_factory(state_code="CA", mobile_phone="555-OWN-EXPORT-0001")
    owned_b = lead_factory(state_code="CA", mobile_phone="555-OWN-EXPORT-0002")
    db.add(
        LeadOwnership(
            user_id=advisor.id,
            lead_id=owned_a.id,
            purchase_id=purchase.id,
        )
    )
    db.add(
        LeadOwnership(
            user_id=advisor.id,
            lead_id=owned_b.id,
            purchase_id=purchase.id,
        )
    )
    db.commit()

    captured_events = []
    monkeypatch.setattr(
        "app.services.lead_service.AuditService.log_purchase_event",
        lambda **kwargs: captured_events.append(kwargs),
    )

    first_csv = "".join(LeadService.download_leads_csv(db=db, user=advisor))
    assert "555-OWN-EXPORT-0001" in first_csv
    assert "555-OWN-EXPORT-0002" in first_csv
    assert (
        db.query(LeadDownload)
        .filter(LeadDownload.user_id == advisor.id)
        .count()
        == 2
    )
    db.refresh(purchase)
    assert purchase.credits_remaining == 2
    assert captured_events == []

    second_csv = "".join(LeadService.download_leads_csv(db=db, user=advisor))
    assert "555-OWN-EXPORT-0001" in second_csv
    assert "555-OWN-EXPORT-0002" in second_csv
    audit_rows = (
        db.query(LeadDownload)
        .filter(LeadDownload.user_id == advisor.id)
        .order_by(LeadDownload.id.asc())
        .all()
    )
    assert len(audit_rows) == 4
    assert len({row.csv_batch_id for row in audit_rows}) == 2


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


@pytest.mark.unit
def test_reconcile_pending_purchase_assignments_prioritizes_oldest_purchase(
    db,
    user_factory,
    plan_factory,
    license_factory,
    purchase_factory,
    lead_factory,
):
    advisor = user_factory(
        role="advisor",
        password="LeadUnitReconcileOrder123!",
        email="lead.unit.reconcile.order@example.com",
    )
    plan = plan_factory(
        daily_download_limit=5,
        state_limit=1,
        stripe_price_id="price_reconcile_order",
    )
    license_factory(user_id=advisor.id, state="CA", status="verified")
    older_purchase = purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        credits_total=2,
        credits_remaining=2,
        status="completed",
    )
    newer_purchase = purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        credits_total=2,
        credits_remaining=2,
        status="completed",
    )
    lead_factory(state_code="CA", mobile_phone="555-RECON-ORDER-0001")
    lead_factory(state_code="CA", mobile_phone="555-RECON-ORDER-0002")

    summary = LeadService.reconcile_pending_purchase_assignments(
        db=db,
        state_codes=["CA"],
        source_event="test_reconcile_order",
    )

    assert summary["newly_assigned_count"] == 2
    assert (
        db.query(LeadOwnership)
        .filter(LeadOwnership.purchase_id == older_purchase.id)
        .count()
        == 2
    )
    assert (
        db.query(LeadOwnership)
        .filter(LeadOwnership.purchase_id == newer_purchase.id)
        .count()
        == 0
    )


@pytest.mark.unit
def test_reconcile_pending_purchase_assignments_fair_share_respects_registration_rank(
    db,
    user_factory,
    plan_factory,
    license_factory,
    purchase_factory,
    lead_factory,
):
    higher_rank_advisor = user_factory(
        role="advisor",
        password="LeadUnitFairShareRankHigh123!",
        email="lead.unit.fairshare.rank.high@example.com",
    )
    lower_rank_advisor = user_factory(
        role="advisor",
        password="LeadUnitFairShareRankLow123!",
        email="lead.unit.fairshare.rank.low@example.com",
    )
    rank_anchor = datetime(2025, 1, 1, tzinfo=timezone.utc)
    higher_rank_advisor.created_at = rank_anchor
    lower_rank_advisor.created_at = rank_anchor + timedelta(minutes=1)
    db.add_all([higher_rank_advisor, lower_rank_advisor])
    db.commit()

    plan = plan_factory(
        daily_download_limit=5,
        state_limit=1,
        stripe_price_id="price_fair_share_rank",
    )
    license_factory(user_id=higher_rank_advisor.id, state="CA", status="verified")
    license_factory(user_id=lower_rank_advisor.id, state="CA", status="verified")
    higher_rank_purchase = purchase_factory(
        user_id=higher_rank_advisor.id,
        package_id=plan.id,
        credits_total=2,
        credits_remaining=2,
        status="completed",
    )
    lower_rank_purchase = purchase_factory(
        user_id=lower_rank_advisor.id,
        package_id=plan.id,
        credits_total=2,
        credits_remaining=2,
        status="completed",
    )

    lead_factory(state_code="CA", mobile_phone="555-RECON-FAIR-RANK-0001")
    lead_factory(state_code="CA", mobile_phone="555-RECON-FAIR-RANK-0002")
    lead_factory(state_code="CA", mobile_phone="555-RECON-FAIR-RANK-0003")

    summary = LeadService.reconcile_pending_purchase_assignments(
        db=db,
        state_codes=["CA"],
        source_event="test_reconcile_fair_share_rank",
    )

    higher_rank_assigned = (
        db.query(LeadOwnership)
        .filter(LeadOwnership.purchase_id == higher_rank_purchase.id)
        .count()
    )
    lower_rank_assigned = (
        db.query(LeadOwnership)
        .filter(LeadOwnership.purchase_id == lower_rank_purchase.id)
        .count()
    )
    assert summary["newly_assigned_count"] == 3
    assert summary["updated_purchases"] == 2
    assert higher_rank_assigned == 2
    assert lower_rank_assigned == 1
    assert summary["remaining_unfulfilled_count"] == 1


@pytest.mark.unit
def test_reconcile_pending_purchase_assignments_makes_purchases_whole_across_ingests(
    db,
    user_factory,
    plan_factory,
    license_factory,
    purchase_factory,
    lead_factory,
):
    advisors = [
        user_factory(
            role="advisor",
            password=f"LeadUnitFairWhole{i}123!",
            email=f"lead.unit.fair.whole.{i}@example.com",
        )
        for i in range(3)
    ]
    rank_anchor = datetime(2025, 1, 1, tzinfo=timezone.utc)
    for index, advisor in enumerate(advisors):
        advisor.created_at = rank_anchor + timedelta(minutes=index)
    db.add_all(advisors)
    db.commit()

    plan = plan_factory(
        daily_download_limit=25,
        state_limit=1,
        stripe_price_id="price_fair_share_make_whole",
    )
    purchases = []
    for advisor in advisors:
        license_factory(user_id=advisor.id, state="CA", status="verified")
        purchases.append(
            purchase_factory(
                user_id=advisor.id,
                package_id=plan.id,
                credits_total=10,
                credits_remaining=10,
                status="completed",
            )
        )

    for index in range(10):
        lead_factory(state_code="CA", mobile_phone=f"555-RECON-FAIR-WHOLE-A-{index:04d}")

    first_summary = LeadService.reconcile_pending_purchase_assignments(
        db=db,
        state_codes=["CA"],
        source_event="test_reconcile_fair_share_first_ingest",
    )

    first_counts = [
        db.query(LeadOwnership).filter(LeadOwnership.purchase_id == purchase.id).count()
        for purchase in purchases
    ]
    assert first_summary["newly_assigned_count"] == 10
    assert first_counts == [4, 3, 3]
    assert first_summary["remaining_unfulfilled_count"] == 20

    for index in range(20):
        lead_factory(state_code="CA", mobile_phone=f"555-RECON-FAIR-WHOLE-B-{index:04d}")

    second_summary = LeadService.reconcile_pending_purchase_assignments(
        db=db,
        state_codes=["CA"],
        source_event="test_reconcile_fair_share_second_ingest",
    )

    second_counts = [
        db.query(LeadOwnership).filter(LeadOwnership.purchase_id == purchase.id).count()
        for purchase in purchases
    ]
    assert second_summary["newly_assigned_count"] == 20
    assert second_counts == [10, 10, 10]
    assert second_summary["remaining_unfulfilled_count"] == 0


@pytest.mark.unit
def test_reconcile_pending_purchase_assignments_uses_user_id_tiebreak_for_same_registration_time(
    db,
    user_factory,
    plan_factory,
    license_factory,
    purchase_factory,
    lead_factory,
):
    advisor_a = user_factory(
        role="advisor",
        password="LeadUnitTieBreakA123!",
        email="lead.unit.tiebreak.a@example.com",
    )
    advisor_b = user_factory(
        role="advisor",
        password="LeadUnitTieBreakB123!",
        email="lead.unit.tiebreak.b@example.com",
    )
    shared_created_at = datetime(2025, 2, 1, tzinfo=timezone.utc)
    advisor_a.created_at = shared_created_at
    advisor_b.created_at = shared_created_at
    db.add_all([advisor_a, advisor_b])
    db.commit()

    plan = plan_factory(
        daily_download_limit=5,
        state_limit=1,
        stripe_price_id="price_fair_share_tiebreak",
    )
    license_factory(user_id=advisor_a.id, state="CA", status="verified")
    license_factory(user_id=advisor_b.id, state="CA", status="verified")
    purchase_a = purchase_factory(
        user_id=advisor_a.id,
        package_id=plan.id,
        credits_total=1,
        credits_remaining=1,
        status="completed",
    )
    purchase_b = purchase_factory(
        user_id=advisor_b.id,
        package_id=plan.id,
        credits_total=1,
        credits_remaining=1,
        status="completed",
    )
    lead_factory(state_code="CA", mobile_phone="555-RECON-TIEBREAK-0001")

    summary = LeadService.reconcile_pending_purchase_assignments(
        db=db,
        state_codes=["CA"],
        source_event="test_reconcile_tiebreak",
    )

    assigned_to_a = (
        db.query(LeadOwnership)
        .filter(LeadOwnership.purchase_id == purchase_a.id)
        .count()
    )
    assigned_to_b = (
        db.query(LeadOwnership)
        .filter(LeadOwnership.purchase_id == purchase_b.id)
        .count()
    )
    if advisor_a.id < advisor_b.id:
        assert assigned_to_a == 1
        assert assigned_to_b == 0
    else:
        assert assigned_to_a == 0
        assert assigned_to_b == 1
    assert summary["newly_assigned_count"] == 1
    assert summary["updated_purchases"] == 1
    assert summary["remaining_unfulfilled_count"] == 1


@pytest.mark.unit
def test_allocate_unsold_leads_for_purchase_ignores_legacy_refund_adjustments_for_entitlement(
    db,
    user_factory,
    plan_factory,
    license_factory,
    purchase_factory,
    lead_factory,
):
    advisor = user_factory(
        role="advisor",
        password="LeadUnitRefundTargetAlloc123!",
        email="lead.unit.refund.target.alloc@example.com",
    )
    plan = plan_factory(
        daily_download_limit=10,
        state_limit=1,
        stripe_price_id="price_refund_target_allocate",
    )
    license_factory(user_id=advisor.id, state="CA", status="verified")
    purchase = purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        credits_total=4,
        credits_remaining=3,
        status="completed",
    )
    db.add(
        LeadCreditLedger(
            user_id=advisor.id,
            purchase_id=purchase.id,
            movement_type="refund_adjustment",
            credits_delta=-1,
            note="partial refund",
            idempotency_key=f"test_refund_adjustment:{purchase.id}:1",
        )
    )
    db.commit()

    for index in range(4):
        lead_factory(state_code="CA", mobile_phone=f"555-REFUND-TARGET-ALLOC-{index:04d}")

    summary = LeadService.allocate_unsold_leads_for_purchase(
        db=db,
        purchase=purchase,
    )

    assert summary["requested_count"] == 4
    assert summary["assigned_count"] == 3
    assert summary["unfulfilled_count"] == 1
    assert summary["newly_assigned_count"] == 3
    assert (
        db.query(LeadOwnership)
        .filter(LeadOwnership.purchase_id == purchase.id)
        .count()
        == 3
    )


@pytest.mark.unit
def test_reconcile_pending_purchase_assignments_ignores_legacy_refund_adjustments(
    db,
    user_factory,
    plan_factory,
    license_factory,
    purchase_factory,
    lead_factory,
):
    advisor = user_factory(
        role="advisor",
        password="LeadUnitRefundTargetRecon123!",
        email="lead.unit.refund.target.reconcile@example.com",
    )
    plan = plan_factory(
        daily_download_limit=10,
        state_limit=1,
        stripe_price_id="price_refund_target_reconcile",
    )
    license_factory(user_id=advisor.id, state="CA", status="verified")
    purchase = purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        credits_total=4,
        credits_remaining=3,
        status="completed",
    )
    db.add(
        LeadCreditLedger(
            user_id=advisor.id,
            purchase_id=purchase.id,
            movement_type="refund_adjustment",
            credits_delta=-1,
            note="partial refund",
            idempotency_key=f"test_refund_adjustment:{purchase.id}:2",
        )
    )
    db.commit()

    for index in range(4):
        lead_factory(state_code="CA", mobile_phone=f"555-REFUND-TARGET-RECON-{index:04d}")

    summary = LeadService.reconcile_pending_purchase_assignments(
        db=db,
        state_codes=["CA"],
        source_event="test_refund_adjusted_reconcile",
    )

    assert summary["scanned_purchases"] == 1
    assert summary["updated_purchases"] == 1
    assert summary["newly_assigned_count"] == 3
    assert summary["remaining_unfulfilled_count"] == 1
    assert (
        db.query(LeadOwnership)
        .filter(LeadOwnership.purchase_id == purchase.id)
        .count()
        == 3
    )


@pytest.mark.unit
def test_create_lead_triggers_pending_purchase_reconciliation(
    db,
    user_factory,
    plan_factory,
    license_factory,
    purchase_factory,
):
    advisor = user_factory(
        role="advisor",
        password="LeadUnitCreateRecon123!",
        email="lead.unit.create.recon@example.com",
    )
    plan = plan_factory(
        daily_download_limit=5,
        state_limit=1,
        stripe_price_id="price_create_reconcile",
    )
    license_factory(user_id=advisor.id, state="CA", status="verified")
    purchase = purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        credits_total=1,
        credits_remaining=1,
        status="completed",
    )

    created = LeadService.create_lead(
        db=db,
        data=LeadCreate(
            state_code="CA",
            mobile_phone="555-CR-RECON-0001",
        ),
    )

    ownership = (
        db.query(LeadOwnership)
        .filter(
            LeadOwnership.purchase_id == purchase.id,
            LeadOwnership.user_id == advisor.id,
            LeadOwnership.lead_id == created.id,
        )
        .first()
    )
    assert ownership is not None


@pytest.mark.unit
def test_bulk_import_leads_triggers_pending_purchase_reconciliation(
    db,
    user_factory,
    plan_factory,
    license_factory,
    purchase_factory,
):
    advisor = user_factory(
        role="advisor",
        password="LeadUnitBulkRecon123!",
        email="lead.unit.bulk.recon@example.com",
    )
    plan = plan_factory(
        daily_download_limit=5,
        state_limit=1,
        stripe_price_id="price_bulk_reconcile",
    )
    license_factory(user_id=advisor.id, state="CA", status="verified")
    purchase = purchase_factory(
        user_id=advisor.id,
        package_id=plan.id,
        credits_total=3,
        credits_remaining=3,
        status="completed",
    )

    result = LeadService.bulk_import_leads(
        db=db,
        csv_data=[
            {"state_code": "CA", "mobile_phone": "555-BULK-RECON-0001"},
            {"state_code": "CA", "mobile_phone": "555-BULK-RECON-0002"},
            {"state_code": "CA", "mobile_phone": "555-BULK-RECON-0003"},
        ],
    )

    assert result["success"] == 3
    assert (
        db.query(LeadOwnership)
        .filter(
            LeadOwnership.purchase_id == purchase.id,
            LeadOwnership.user_id == advisor.id,
        )
        .count()
        == 3
    )
