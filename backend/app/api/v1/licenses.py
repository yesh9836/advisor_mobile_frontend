import logging
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db, require_admin
from app.models.user import User
from app.schemas.license import (
    AdminLicenseDecisionRow,
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
    try:
        license_data = LicenseCreate(
            state=state,
            license_number=license_number,
            license_type=license_type,
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=exc.errors(include_url=False, include_context=False),
        ) from exc

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
    licenses = LicenseService.get_user_licenses(db=db, user_id=current_user.id)
    return [LicenseResponse.model_validate(license) for license in licenses]


@router.get(
    "/pending",
    response_model=List[LicenseWithUser],
    summary="Get all pending licenses (admin only)",
)
def get_pending_licenses(
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> List[LicenseWithUser]:
    licenses = LicenseService.get_pending_licenses(db=db)
    
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
)
def get_processed_licenses(
    advisor_id: Optional[int] = None,
    advisor_query: Optional[str] = None,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> List[AdminLicenseDecisionRow]:
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
)
def approve_license(
    license_id: int,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> LicenseResponse:
    license = LicenseService.approve_license(
        db=db,
        license_id=license_id,
        admin_id=current_admin.id,
    )

    return LicenseResponse.model_validate(license)


@router.post(
    "/{license_id}/reject",
    response_model=LicenseResponse,
    summary="Reject a pending license (admin only)",
)
def reject_license(
    license_id: int,
    data: LicenseReject,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> LicenseResponse:
    license = LicenseService.reject_license(
        db=db,
        license_id=license_id,
        admin_id=current_admin.id,
        reason=data.rejection_reason,
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
    if current_user.role != "advisor":
        raise HTTPException(status_code=403, detail="Only advisors can resubmit licenses")

    license = await LicenseService.resubmit_rejected_license(
        db=db,
        user_id=current_user.id,
        license_id=license_id,
        file=document,
        license_type=license_type,
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
    license = LicenseService.get_license_by_id(db=db, license_id=license_id)
    
    if not license:
        raise HTTPException(status_code=404, detail="License not found")
    
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
