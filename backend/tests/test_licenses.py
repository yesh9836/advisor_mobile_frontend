from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import pytest

from app.core.config import settings
from app.models.license import License
from app.models.license_resubmission import LicenseResubmission


def assert_public_license_payload(payload: dict, *, has_document: bool = True) -> None:
    assert payload["has_document"] is has_document
    assert "document_path" not in payload


@pytest.mark.integration
def test_license_submission_and_approval_flow(client, user_factory, auth_headers):
    advisor = user_factory(
        role="advisor",
        password="LicenseAdvisor123!",
        email="advisor.license@example.com",
        name="License Advisor",
    )
    admin = user_factory(
        role="admin",
        password="LicenseAdmin123!",
        email="admin.license@example.com",
        name="License Admin",
    )

    advisor_headers = auth_headers(advisor.email, "LicenseAdvisor123!")
    admin_headers = auth_headers(admin.email, "LicenseAdmin123!")

    submit_response = client.post(
        "/api/v1/licenses/",
        headers=advisor_headers,
        data={"state": "ca", "license_number": "CA-LIC-1001", "license_type": "Series 65"},
        files={"document": ("license.pdf", b"%PDF-1.4 test", "application/pdf")},
    )
    assert submit_response.status_code == 201, submit_response.text
    body = submit_response.json()
    assert_public_license_payload(body)
    assert body["verification_status"] == "pending"
    license_id = body["id"]

    pending_response = client.get("/api/v1/licenses/pending", headers=admin_headers)
    assert pending_response.status_code == 200, pending_response.text
    pending = pending_response.json()
    assert len(pending) == 1
    assert pending[0]["id"] == license_id
    assert pending[0]["user_email"] == advisor.email
    assert_public_license_payload(pending[0])

    approve_response = client.post(
        f"/api/v1/licenses/{license_id}/approve",
        headers=admin_headers,
    )
    assert approve_response.status_code == 200, approve_response.text
    approve_body = approve_response.json()
    assert_public_license_payload(approve_body)
    assert approve_body["verification_status"] == "verified"
    assert approve_body["verified_by"] == admin.id
    assert approve_body["verified_at"] is not None

    get_response = client.get(f"/api/v1/licenses/{license_id}", headers=advisor_headers)
    assert get_response.status_code == 200, get_response.text
    get_body = get_response.json()
    assert_public_license_payload(get_body)
    assert get_body["verification_status"] == "verified"

    processed_response = client.get("/api/v1/licenses/processed", headers=admin_headers)
    assert processed_response.status_code == 200, processed_response.text
    processed = processed_response.json()
    assert len(processed) == 1
    assert processed[0]["license_id"] == license_id
    assert processed[0]["decision_status"] == "verified"
    assert processed[0]["decision_at"] is not None
    assert processed[0]["submission_type"] == "first_time"
    assert processed[0]["review_cycle"] == 1


@pytest.mark.integration
def test_license_rejection_requires_admin_and_reason(client, user_factory, auth_headers):
    advisor = user_factory(
        role="advisor",
        password="LicenseReject123!",
        email="advisor.reject@example.com",
        name="Reject Advisor",
    )
    admin = user_factory(
        role="admin",
        password="LicenseRejectAdmin123!",
        email="admin.reject@example.com",
        name="Reject Admin",
    )

    advisor_headers = auth_headers(advisor.email, "LicenseReject123!")
    admin_headers = auth_headers(admin.email, "LicenseRejectAdmin123!")

    submit_response = client.post(
        "/api/v1/licenses/",
        headers=advisor_headers,
        data={"state": "TX", "license_number": "TX-LIC-1001", "license_type": "RIA"},
        files={"document": ("license.png", b"\x89PNG\r\n\x1a\nfakepng", "image/png")},
    )
    assert submit_response.status_code == 201, submit_response.text
    submit_body = submit_response.json()
    assert_public_license_payload(submit_body)
    license_id = submit_body["id"]

    forbidden_reject = client.post(
        f"/api/v1/licenses/{license_id}/reject",
        headers=advisor_headers,
        json={"rejection_reason": "Unauthorized user"},
    )
    assert forbidden_reject.status_code == 403

    reject_response = client.post(
        f"/api/v1/licenses/{license_id}/reject",
        headers=admin_headers,
        json={"rejection_reason": "Document is unreadable"},
    )
    assert reject_response.status_code == 200, reject_response.text
    reject_body = reject_response.json()
    assert_public_license_payload(reject_body)
    assert reject_body["verification_status"] == "rejected"
    assert reject_body["rejection_reason"] == "Document is unreadable"
    assert reject_body["verified_at"] is None
    assert reject_body["verified_by"] is None

    processed_response = client.get("/api/v1/licenses/processed", headers=admin_headers)
    assert processed_response.status_code == 200, processed_response.text
    processed = processed_response.json()
    assert len(processed) == 1
    assert processed[0]["license_id"] == license_id
    assert processed[0]["decision_status"] == "rejected"
    assert processed[0]["rejection_reason"] == "Document is unreadable"
    assert processed[0]["decision_at"] is not None
    assert processed[0]["submission_type"] == "first_time"
    assert processed[0]["review_cycle"] == 1


@pytest.mark.integration
def test_license_document_download_permissions_and_content(client, user_factory, auth_headers):
    advisor = user_factory(
        role="advisor",
        password="LicenseDocAdvisor123!",
        email="advisor.document@example.com",
        name="Document Advisor",
    )
    other_advisor = user_factory(
        role="advisor",
        password="LicenseDocOther123!",
        email="advisor.other.document@example.com",
        name="Other Advisor",
    )
    admin = user_factory(
        role="admin",
        password="LicenseDocAdmin123!",
        email="admin.document@example.com",
        name="Document Admin",
    )

    advisor_headers = auth_headers(advisor.email, "LicenseDocAdvisor123!")
    other_headers = auth_headers(other_advisor.email, "LicenseDocOther123!")
    admin_headers = auth_headers(admin.email, "LicenseDocAdmin123!")

    submit_response = client.post(
        "/api/v1/licenses/",
        headers=advisor_headers,
        data={"state": "CA", "license_number": "CA-LIC-DOC-1001", "license_type": "Series 65"},
        files={"document": ("license.pdf", b"%PDF-1.4 test-document", "application/pdf")},
    )
    assert submit_response.status_code == 201, submit_response.text
    license_id = submit_response.json()["id"]

    owner_download = client.get(
        f"/api/v1/licenses/{license_id}/document",
        headers=advisor_headers,
    )
    assert owner_download.status_code == 200, owner_download.text
    assert owner_download.headers["content-type"] == "application/pdf"
    assert "attachment" in owner_download.headers.get("content-disposition", "").lower()
    assert owner_download.content.startswith(b"%PDF-1.4")

    admin_download = client.get(
        f"/api/v1/licenses/{license_id}/document",
        headers=admin_headers,
    )
    assert admin_download.status_code == 200, admin_download.text
    assert admin_download.content.startswith(b"%PDF-1.4")

    admin_preview = client.get(
        f"/api/v1/licenses/{license_id}/document?access_mode=preview",
        headers=admin_headers,
    )
    assert admin_preview.status_code == 200, admin_preview.text
    assert admin_preview.headers["content-type"] == "application/pdf"
    assert "inline" in admin_preview.headers.get("content-disposition", "").lower()
    assert admin_preview.content.startswith(b"%PDF-1.4")

    unauthorized_download = client.get(
        f"/api/v1/licenses/{license_id}/document",
        headers=other_headers,
    )
    assert unauthorized_download.status_code == 403
    assert "Not authorized" in unauthorized_download.json()["detail"]


@pytest.mark.integration
def test_license_document_download_rejects_invalid_or_missing_path(
    client,
    db,
    user_factory,
    auth_headers,
    license_factory,
):
    advisor = user_factory(
        role="advisor",
        password="LicensePathAdvisor123!",
        email="advisor.path@example.com",
        name="Path Advisor",
    )
    advisor_headers = auth_headers(advisor.email, "LicensePathAdvisor123!")

    missing_file_license = license_factory(user_id=advisor.id, state="WA", status="pending")
    missing_file_response = client.get(
        f"/api/v1/licenses/{missing_file_license.id}/document",
        headers=advisor_headers,
    )
    assert missing_file_response.status_code == 404
    assert missing_file_response.json()["detail"] == "Document file not found"

    traversal_license = license_factory(user_id=advisor.id, state="OR", status="pending")
    traversal_license.document_path = "../outside.pdf"
    db.add(traversal_license)
    db.commit()

    invalid_path_response = client.get(
        f"/api/v1/licenses/{traversal_license.id}/document",
        headers=advisor_headers,
    )
    assert invalid_path_response.status_code == 400
    assert invalid_path_response.json()["detail"] == "Invalid document path"


@pytest.mark.integration
def test_license_upload_size_limit_respects_mb_setting(client, user_factory, auth_headers, monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 1)

    advisor = user_factory(
        role="advisor",
        password="LicenseSizeAdvisor123!",
        email="advisor.size@example.com",
        name="Size Advisor",
    )
    advisor_headers = auth_headers(advisor.email, "LicenseSizeAdvisor123!")

    under_limit_response = client.post(
        "/api/v1/licenses/",
        headers=advisor_headers,
        data={"state": "CA", "license_number": "CA-LIC-SIZE-1001", "license_type": "Series 65"},
        files={"document": ("small.pdf", b"%PDF-1.4\n" + (b"a" * 1024), "application/pdf")},
    )
    assert under_limit_response.status_code == 201, under_limit_response.text

    over_limit_response = client.post(
        "/api/v1/licenses/",
        headers=advisor_headers,
        data={"state": "TX", "license_number": "TX-LIC-SIZE-1002", "license_type": "Series 65"},
        files={"document": ("large.pdf", b"%PDF-1.4\n" + (b"a" * (1024 * 1024 + 1)), "application/pdf")},
    )
    assert over_limit_response.status_code == 400
    assert over_limit_response.json()["detail"] == "File too large. Limit: 1MB"


@pytest.mark.integration
def test_license_upload_retries_unique_filename_on_collision(
    client,
    db,
    user_factory,
    auth_headers,
    monkeypatch,
):
    from app.services import license_service as license_service_module

    fixed_now = datetime(2026, 2, 12, 14, 5, 12, tzinfo=timezone.utc)

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_now.replace(tzinfo=None)
            return fixed_now.astimezone(tz)

    monkeypatch.setattr(license_service_module, "datetime", FrozenDateTime)

    collision_uuid = UUID("11111111-1111-1111-1111-111111111111")
    unique_uuid = UUID("22222222-2222-2222-2222-222222222222")
    uuid_values = iter((collision_uuid, unique_uuid))
    monkeypatch.setattr(license_service_module, "uuid4", lambda: next(uuid_values))

    advisor = user_factory(
        role="advisor",
        password="LicenseCollision123!",
        email="advisor.collision@example.com",
        name="Collision Advisor",
    )
    advisor_headers = auth_headers(advisor.email, "LicenseCollision123!")

    timestamp = fixed_now.strftime("%Y%m%d_%H%M%S")
    collision_suffix = collision_uuid.hex[:license_service_module.UPLOAD_FILENAME_ENTROPY_LENGTH]
    upload_dir = Path(settings.UPLOAD_DIR) / "licenses" / str(advisor.id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    colliding_path = upload_dir / f"{timestamp}_{collision_suffix}_license.pdf"
    colliding_path.write_bytes(b"preexisting-content")

    submit_response = client.post(
        "/api/v1/licenses/",
        headers=advisor_headers,
        data={"state": "CA", "license_number": "CA-LIC-COLLIDE-1001", "license_type": "Series 65"},
        files={"document": ("license.pdf", b"%PDF-1.4 fresh-upload", "application/pdf")},
    )
    assert submit_response.status_code == 201, submit_response.text
    license_id = submit_response.json()["id"]

    saved_license = db.query(License).filter(License.id == license_id).one()
    saved_path = Path(saved_license.document_path)
    if not saved_path.is_absolute():
        saved_path = Path.cwd() / saved_path

    assert saved_path.name.startswith(f"{timestamp}_")
    assert saved_path.name.endswith("_license.pdf")
    assert saved_path != colliding_path.resolve()
    assert saved_path.read_bytes().startswith(b"%PDF-1.4")
    assert colliding_path.read_bytes() == b"preexisting-content"


@pytest.mark.integration
def test_rejected_license_can_be_resubmitted_by_owner(client, db, user_factory, auth_headers):
    advisor = user_factory(
        role="advisor",
        password="LicenseResubmitAdvisor123!",
        email="advisor.resubmit@example.com",
        name="Resubmit Advisor",
    )
    admin = user_factory(
        role="admin",
        password="LicenseResubmitAdmin123!",
        email="admin.resubmit@example.com",
        name="Resubmit Admin",
    )
    advisor_headers = auth_headers(advisor.email, "LicenseResubmitAdvisor123!")
    admin_headers = auth_headers(admin.email, "LicenseResubmitAdmin123!")

    submit_response = client.post(
        "/api/v1/licenses/",
        headers=advisor_headers,
        data={"state": "AL", "license_number": "DEMO-26-AL-001", "license_type": "Series 65"},
        files={"document": ("license.pdf", b"%PDF-1.4 original", "application/pdf")},
    )
    assert submit_response.status_code == 201, submit_response.text
    license_id = submit_response.json()["id"]

    reject_response = client.post(
        f"/api/v1/licenses/{license_id}/reject",
        headers=admin_headers,
        json={"rejection_reason": "Document is blurry"},
    )
    assert reject_response.status_code == 200, reject_response.text
    assert reject_response.json()["verification_status"] == "rejected"

    resubmit_response = client.post(
        f"/api/v1/licenses/{license_id}/resubmit",
        headers=advisor_headers,
        data={"license_type": "Updated Type"},
        files={"document": ("license_updated.pdf", b"%PDF-1.4 updated", "application/pdf")},
    )
    assert resubmit_response.status_code == 200, resubmit_response.text
    body = resubmit_response.json()
    assert_public_license_payload(body)
    assert body["verification_status"] == "pending"
    assert body["rejection_reason"] is None
    assert body["license_type"] == "Updated Type"

    attempts = (
        db.query(LicenseResubmission)
        .filter(LicenseResubmission.license_id == license_id)
        .count()
    )
    assert attempts == 1


@pytest.mark.integration
def test_license_resubmission_requires_owner_and_rejected_status(client, user_factory, auth_headers):
    advisor = user_factory(
        role="advisor",
        password="LicenseResubmitOwn123!",
        email="advisor.resubmit.owner@example.com",
        name="Owner Advisor",
    )
    other_advisor = user_factory(
        role="advisor",
        password="LicenseResubmitOther123!",
        email="advisor.resubmit.other@example.com",
        name="Other Advisor",
    )
    admin = user_factory(
        role="admin",
        password="LicenseResubmitRoleAdmin123!",
        email="admin.resubmit.role@example.com",
        name="Role Admin",
    )

    advisor_headers = auth_headers(advisor.email, "LicenseResubmitOwn123!")
    other_headers = auth_headers(other_advisor.email, "LicenseResubmitOther123!")
    admin_headers = auth_headers(admin.email, "LicenseResubmitRoleAdmin123!")

    submit_response = client.post(
        "/api/v1/licenses/",
        headers=advisor_headers,
        data={"state": "GA", "license_number": "GA-RESUBMIT-001", "license_type": "Series 65"},
        files={"document": ("license.pdf", b"%PDF-1.4 start", "application/pdf")},
    )
    assert submit_response.status_code == 201, submit_response.text
    license_id = submit_response.json()["id"]

    pending_resubmit = client.post(
        f"/api/v1/licenses/{license_id}/resubmit",
        headers=advisor_headers,
        files={"document": ("license_retry.pdf", b"%PDF-1.4 retry", "application/pdf")},
    )
    assert pending_resubmit.status_code == 400
    assert pending_resubmit.json()["detail"] == "Only rejected licenses can be resubmitted"

    reject_response = client.post(
        f"/api/v1/licenses/{license_id}/reject",
        headers=admin_headers,
        json={"rejection_reason": "Need clearer document"},
    )
    assert reject_response.status_code == 200, reject_response.text

    other_resubmit = client.post(
        f"/api/v1/licenses/{license_id}/resubmit",
        headers=other_headers,
        files={"document": ("license_other.pdf", b"%PDF-1.4 other", "application/pdf")},
    )
    assert other_resubmit.status_code == 403
    assert "Not authorized" in other_resubmit.json()["detail"]

    admin_resubmit = client.post(
        f"/api/v1/licenses/{license_id}/resubmit",
        headers=admin_headers,
        files={"document": ("license_admin.pdf", b"%PDF-1.4 admin", "application/pdf")},
    )
    assert admin_resubmit.status_code == 403
    assert admin_resubmit.json()["detail"] == "Only advisors can resubmit licenses"


@pytest.mark.integration
def test_license_resubmission_limit_enforced(client, user_factory, auth_headers, monkeypatch):
    monkeypatch.setattr(settings, "LICENSE_RESUBMISSION_MAX_ATTEMPTS", 3)
    monkeypatch.setattr(settings, "LICENSE_RESUBMISSION_WINDOW_DAYS", 90)

    advisor = user_factory(
        role="advisor",
        password="LicenseResubmitLimitAdvisor123!",
        email="advisor.resubmit.limit@example.com",
        name="Limit Advisor",
    )
    admin = user_factory(
        role="admin",
        password="LicenseResubmitLimitAdmin123!",
        email="admin.resubmit.limit@example.com",
        name="Limit Admin",
    )
    advisor_headers = auth_headers(advisor.email, "LicenseResubmitLimitAdvisor123!")
    admin_headers = auth_headers(admin.email, "LicenseResubmitLimitAdmin123!")

    submit_response = client.post(
        "/api/v1/licenses/",
        headers=advisor_headers,
        data={"state": "FL", "license_number": "FL-RESUBMIT-001", "license_type": "Series 7"},
        files={"document": ("license.pdf", b"%PDF-1.4 first", "application/pdf")},
    )
    assert submit_response.status_code == 201, submit_response.text
    license_id = submit_response.json()["id"]

    first_reject = client.post(
        f"/api/v1/licenses/{license_id}/reject",
        headers=admin_headers,
        json={"rejection_reason": "Try again"},
    )
    assert first_reject.status_code == 200, first_reject.text

    for index in range(3):
        resubmit_response = client.post(
            f"/api/v1/licenses/{license_id}/resubmit",
            headers=advisor_headers,
            files={"document": (f"retry_{index}.pdf", b"%PDF-1.4 retry", "application/pdf")},
        )
        assert resubmit_response.status_code == 200, resubmit_response.text
        resubmit_body = resubmit_response.json()
        assert_public_license_payload(resubmit_body)
        assert resubmit_body["verification_status"] == "pending"

        reject_response = client.post(
            f"/api/v1/licenses/{license_id}/reject",
            headers=admin_headers,
            json={"rejection_reason": f"Still invalid ({index})"},
        )
        assert reject_response.status_code == 200, reject_response.text
        reject_body = reject_response.json()
        assert_public_license_payload(reject_body)
        assert reject_body["verification_status"] == "rejected"

    blocked_response = client.post(
        f"/api/v1/licenses/{license_id}/resubmit",
        headers=advisor_headers,
        files={"document": ("retry_blocked.pdf", b"%PDF-1.4 blocked", "application/pdf")},
    )
    assert blocked_response.status_code == 429
    assert "Resubmission limit reached" in blocked_response.json()["detail"]


@pytest.mark.integration
def test_processed_licenses_requires_admin(client, user_factory, auth_headers):
    advisor = user_factory(
        role="advisor",
        password="LicenseProcessedAdvisor123!",
        email="advisor.processed@example.com",
        name="Processed Advisor",
    )

    advisor_headers = auth_headers(advisor.email, "LicenseProcessedAdvisor123!")

    response = client.get("/api/v1/licenses/processed", headers=advisor_headers)
    assert response.status_code == 403


@pytest.mark.integration
def test_resubmitted_license_moves_from_processed_back_to_pending(
    client,
    user_factory,
    auth_headers,
):
    advisor = user_factory(
        role="advisor",
        password="LicenseProcessedMoveAdvisor123!",
        email="advisor.processed.move@example.com",
        name="Processed Move Advisor",
    )
    admin = user_factory(
        role="admin",
        password="LicenseProcessedMoveAdmin123!",
        email="admin.processed.move@example.com",
        name="Processed Move Admin",
    )

    advisor_headers = auth_headers(advisor.email, "LicenseProcessedMoveAdvisor123!")
    admin_headers = auth_headers(admin.email, "LicenseProcessedMoveAdmin123!")

    submit_response = client.post(
        "/api/v1/licenses/",
        headers=advisor_headers,
        data={"state": "NC", "license_number": "NC-PROCESSED-001", "license_type": "Series 66"},
        files={"document": ("license.pdf", b"%PDF-1.4 initial", "application/pdf")},
    )
    assert submit_response.status_code == 201, submit_response.text
    license_id = submit_response.json()["id"]

    reject_response = client.post(
        f"/api/v1/licenses/{license_id}/reject",
        headers=admin_headers,
        json={"rejection_reason": "Please provide clearer scan"},
    )
    assert reject_response.status_code == 200, reject_response.text

    processed_after_reject = client.get("/api/v1/licenses/processed", headers=admin_headers)
    assert processed_after_reject.status_code == 200, processed_after_reject.text
    processed_ids = [item["license_id"] for item in processed_after_reject.json()]
    assert license_id in processed_ids

    resubmit_response = client.post(
        f"/api/v1/licenses/{license_id}/resubmit",
        headers=advisor_headers,
        files={"document": ("license_retry.pdf", b"%PDF-1.4 retry", "application/pdf")},
    )
    assert resubmit_response.status_code == 200, resubmit_response.text
    resubmit_body = resubmit_response.json()
    assert_public_license_payload(resubmit_body)
    assert resubmit_body["verification_status"] == "pending"
    assert resubmit_body["rejection_reason"] is None

    processed_after_resubmit = client.get("/api/v1/licenses/processed", headers=admin_headers)
    assert processed_after_resubmit.status_code == 200, processed_after_resubmit.text
    processed_ids_after = [item["license_id"] for item in processed_after_resubmit.json()]
    assert license_id not in processed_ids_after


@pytest.mark.integration
def test_processed_licenses_include_resubmission_cycle_and_filters(
    client,
    user_factory,
    auth_headers,
):
    advisor_a = user_factory(
        role="advisor",
        password="LicenseCycleAdvisorA123!",
        email="advisor.cycle.a@example.com",
        name="Cycle Advisor Alpha",
    )
    advisor_b = user_factory(
        role="advisor",
        password="LicenseCycleAdvisorB123!",
        email="advisor.cycle.b@example.com",
        name="Cycle Advisor Beta",
    )
    admin = user_factory(
        role="admin",
        password="LicenseCycleAdmin123!",
        email="admin.cycle@example.com",
        name="Cycle Admin",
    )

    advisor_a_headers = auth_headers(advisor_a.email, "LicenseCycleAdvisorA123!")
    advisor_b_headers = auth_headers(advisor_b.email, "LicenseCycleAdvisorB123!")
    admin_headers = auth_headers(admin.email, "LicenseCycleAdmin123!")

    first_submit = client.post(
        "/api/v1/licenses/",
        headers=advisor_a_headers,
        data={"state": "AZ", "license_number": "AZ-CYCLE-001", "license_type": "Series 7"},
        files={"document": ("license_a.pdf", b"%PDF-1.4 first", "application/pdf")},
    )
    assert first_submit.status_code == 201, first_submit.text
    first_license_id = first_submit.json()["id"]

    approve_first = client.post(
        f"/api/v1/licenses/{first_license_id}/approve",
        headers=admin_headers,
    )
    assert approve_first.status_code == 200, approve_first.text

    second_submit = client.post(
        "/api/v1/licenses/",
        headers=advisor_b_headers,
        data={"state": "UT", "license_number": "UT-CYCLE-001", "license_type": "Series 66"},
        files={"document": ("license_b.pdf", b"%PDF-1.4 original", "application/pdf")},
    )
    assert second_submit.status_code == 201, second_submit.text
    second_license_id = second_submit.json()["id"]

    first_reject = client.post(
        f"/api/v1/licenses/{second_license_id}/reject",
        headers=admin_headers,
        json={"rejection_reason": "Need a clearer copy"},
    )
    assert first_reject.status_code == 200, first_reject.text

    resubmit = client.post(
        f"/api/v1/licenses/{second_license_id}/resubmit",
        headers=advisor_b_headers,
        files={"document": ("license_b_retry.pdf", b"%PDF-1.4 retry", "application/pdf")},
    )
    assert resubmit.status_code == 200, resubmit.text

    second_reject = client.post(
        f"/api/v1/licenses/{second_license_id}/reject",
        headers=admin_headers,
        json={"rejection_reason": "Still not readable"},
    )
    assert second_reject.status_code == 200, second_reject.text

    all_processed = client.get("/api/v1/licenses/processed", headers=admin_headers)
    assert all_processed.status_code == 200, all_processed.text
    all_rows = all_processed.json()
    assert len(all_rows) == 2

    alpha_row = next(item for item in all_rows if item["license_id"] == first_license_id)
    beta_row = next(item for item in all_rows if item["license_id"] == second_license_id)

    assert alpha_row["submission_type"] == "first_time"
    assert alpha_row["review_cycle"] == 1

    assert beta_row["submission_type"] == "resubmission"
    assert beta_row["review_cycle"] == 2
    assert beta_row["decision_status"] == "rejected"

    filter_by_id = client.get(
        f"/api/v1/licenses/processed?advisor_id={advisor_b.id}",
        headers=admin_headers,
    )
    assert filter_by_id.status_code == 200, filter_by_id.text
    id_rows = filter_by_id.json()
    assert len(id_rows) == 1
    assert id_rows[0]["license_id"] == second_license_id

    filter_by_query = client.get(
        "/api/v1/licenses/processed?advisor_query=alpha",
        headers=admin_headers,
    )
    assert filter_by_query.status_code == 200, filter_by_query.text
    query_rows = filter_by_query.json()
    assert len(query_rows) == 1
    assert query_rows[0]["license_id"] == first_license_id
