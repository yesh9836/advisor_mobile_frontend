import logging
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db, require_admin
from app.models.user import User
from app.schemas.license import (
    AdminLicenseDecisionRow,
    LicenseApprove,
    LicenseCreate,
    LicenseReject,
    LicenseResponse,
    LicenseWithUser,
)
from app.services.license_service import LicenseService
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/licenses", tags=["licenses"])


@router.post(
    "/",
    response_model=LicenseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a license for verification",
)
async def submit_license(
    state: str = Form(..., description="Two-letter state code"),
    license_number: str = Form(..., description="License number"),
    license_type: str = Form(None, description="Type of license (optional)"),
    document: UploadFile = File(..., description="License document (PDF or image)"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> LicenseResponse:
    """
    Submit a new license for admin verification.
    
    The license document will be reviewed by an administrator.
    
    Requirements:
    - State must be a valid 2-letter code
    - License number is required
    - Document must be PDF, JPG, JPEG, or PNG
    - Maximum file size: 10 MB
    """
    # Create schema for validation
    license_data = LicenseCreate(
        state=state,
        license_number=license_number,
        license_type=license_type,
    )

    # Submit license
    license = await LicenseService.submit_license(
        db=db,
        user_id=current_user.id,
        data=license_data,
        file=document,
    )

    return LicenseResponse.model_validate(license)


@router.get(
    "/",
    response_model=List[LicenseResponse],
    summary="Get current user's licenses",
)
def get_my_licenses(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> List[LicenseResponse]:
    """
    Get all licenses for the current user.
    
    Returns licenses ordered by submission date (newest first).
    """
    licenses = LicenseService.get_user_licenses(db=db, user_id=current_user.id)
    return [LicenseResponse.model_validate(license) for license in licenses]


@router.get(
    "/pending",
    response_model=List[LicenseWithUser],
    summary="Get all pending licenses (admin only)",
    dependencies=[Depends(require_admin)],
)
def get_pending_licenses(
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> List[LicenseWithUser]:
    """
    Get all pending licenses awaiting admin review.
    
    Admin only. Returns licenses ordered by submission date (oldest first).
    """
    licenses = LicenseService.get_pending_licenses(db=db)
    
    # Convert to response schema with user details
    response = []
    for license in licenses:
        license_dict = LicenseResponse.model_validate(license).model_dump()
        license_dict["user_name"] = license.user.name
        license_dict["user_email"] = license.user.email
        response.append(LicenseWithUser(**license_dict))
    
    return response


@router.get(
    "/processed",
    response_model=List[AdminLicenseDecisionRow],
    summary="Get currently processed licenses (admin only)",
    dependencies=[Depends(require_admin)],
)
def get_processed_licenses(
    advisor_id: Optional[int] = None,
    advisor_query: Optional[str] = None,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> List[AdminLicenseDecisionRow]:
    """
    Get licenses currently in approved/rejected states for admin visibility.

    Admin only. Returns licenses ordered by latest decision timestamp (newest first).
    """
    rows = LicenseService.get_processed_licenses(
        db=db,
        advisor_id=advisor_id,
        advisor_query=advisor_query,
    )

    response = []
    for row in rows:
        license = row["license"]
        response.append(
            AdminLicenseDecisionRow(
                license_id=license.id,
                user_id=license.user_id,
                user_name=row["user_name"],
                user_email=row["user_email"],
                state=license.state,
                license_number=license.license_number,
                license_type=license.license_type,
                decision_status=license.verification_status,
                decision_at=license.reviewed_at,
                submission_type=row["submission_type"],
                review_cycle=row["review_cycle"],
                rejection_reason=license.rejection_reason,
                created_at=license.created_at,
            )
        )

    return response


@router.post(
    "/{license_id}/approve",
    response_model=LicenseResponse,
    summary="Approve a pending license (admin only)",
    dependencies=[Depends(require_admin)],
)
def approve_license(
    license_id: int,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> LicenseResponse:
    """
    Approve a pending license.
    
    Admin only. Sets the license status to 'verified' and records
    the approving admin and timestamp.
    """
    license = LicenseService.approve_license(
        db=db,
        license_id=license_id,
        admin_id=current_admin.id,
    )

    AuditService.log_event(
        actor_user_id=current_admin.id,
        action="license_approved",
        entity_type="License",
        entity_id=license.id,
        meta_data={"state": license.state, "status": license.verification_status},
    )

    return LicenseResponse.model_validate(license)


@router.post(
    "/{license_id}/reject",
    response_model=LicenseResponse,
    summary="Reject a pending license (admin only)",
    dependencies=[Depends(require_admin)],
)
def reject_license(
    license_id: int,
    data: LicenseReject,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> LicenseResponse:
    """
    Reject a pending license.
    
    Admin only. Sets the license status to 'rejected' and records
    the rejection reason.
    """
    license = LicenseService.reject_license(
        db=db,
        license_id=license_id,
        admin_id=current_admin.id,
        reason=data.rejection_reason,
    )

    AuditService.log_event(
        actor_user_id=current_admin.id,
        action="license_rejected",
        entity_type="License",
        entity_id=license.id,
        meta_data={
            "state": license.state,
            "status": license.verification_status,
            "reason": data.rejection_reason,
        },
    )

    return LicenseResponse.model_validate(license)


@router.post(
    "/{license_id}/resubmit",
    response_model=LicenseResponse,
    summary="Resubmit a rejected license (advisor only)",
)
async def resubmit_license(
    license_id: int,
    document: UploadFile = File(..., description="Updated license document (PDF or image)"),
    license_type: Optional[str] = Form(None, description="Updated license type (optional)"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> LicenseResponse:
    """
    Resubmit a rejected license for another admin review cycle.

    Advisors can only resubmit their own rejected licenses.
    """
    if current_user.role != "advisor":
        raise HTTPException(status_code=403, detail="Only advisors can resubmit licenses")

    license = await LicenseService.resubmit_rejected_license(
        db=db,
        user_id=current_user.id,
        license_id=license_id,
        file=document,
        license_type=license_type,
    )

    AuditService.log_event(
        actor_user_id=current_user.id,
        action="license_resubmitted",
        entity_type="License",
        entity_id=license.id,
        meta_data={"state": license.state},
    )

    return LicenseResponse.model_validate(license)


@router.get(
    "/{license_id}",
    response_model=LicenseResponse,
    summary="Get license by ID",
)
def get_license(
    license_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> LicenseResponse:
    """
    Get a specific license by ID.
    
    Users can only view their own licenses unless they are admin.
    """
    license = LicenseService.get_license_by_id(db=db, license_id=license_id)
    
    if not license:
        raise HTTPException(status_code=404, detail="License not found")
    
    # Check permissions: user can only view their own licenses, admins can view all
    if license.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to view this license")
    
    return LicenseResponse.model_validate(license)


@router.get(
    "/{license_id}/document",
    summary="Download license document",
)
def download_license_document(
    license_id: int,
    access_mode: Literal["download", "preview"] = Query(
        "download",
        description="How the file is being accessed for audit semantics and disposition headers.",
    ),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    """
    Download the uploaded document for a license.

    Access rules:
    - Admin users can download any license document
    - Advisors can download only their own license documents
    """
    license = LicenseService.get_license_by_id(db=db, license_id=license_id)
    if not license:
        raise HTTPException(status_code=404, detail="License not found")

    if license.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to download this document")

    file_path, media_type = LicenseService.resolve_document_for_download(license.document_path)
    filename = f"license_{license.id}{file_path.suffix.lower()}"
    action = (
        "license_document_viewed"
        if access_mode == "preview"
        else "license_document_downloaded"
    )

    AuditService.log_event(
        actor_user_id=current_user.id,
        action=action,
        entity_type="License",
        entity_id=license.id,
        meta_data={"viewer_role": current_user.role, "access_mode": access_mode},
    )

    headers = {
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
    }

    if access_mode == "preview":
        headers["Content-Disposition"] = f'inline; filename="{filename}"'
        return FileResponse(
            path=file_path,
            media_type=media_type,
            headers=headers,
        )

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=filename,
        headers=headers,
    )
