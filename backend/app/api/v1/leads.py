import logging
from datetime import datetime, timezone
from typing import Dict

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db, require_admin
from app.models.user import User
from app.schemas.lead import LeadCreate, LeadListResponse, LeadResponse
from app.services.lead_service import LeadService
from app.utils.csv_generator import parse_leads_csv

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/leads", tags=["leads"])


@router.get(
    "/",
    response_model=LeadListResponse,
    summary="Get available leads for current user",
)
def list_available_leads(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> LeadListResponse:
    data = LeadService.get_available_leads_for_user(
        db=db,
        user=current_user,
        page=page,
        size=size,
    )
    items = [LeadResponse.model_validate(lead) for lead in data["items"]]
    return LeadListResponse(
        items=items,
        total=data["total"],
        page=data["page"],
        size=data["size"],
    )


@router.get(
    "/download",
    summary="Download leads as CSV",
    response_class=StreamingResponse
)
def download_leads_csv(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    csv_iterator = LeadService.download_leads_csv(db=db, user=current_user)
    filename = f"leads_{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"

    return StreamingResponse(
        csv_iterator,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Cache-Control": "no-cache",
        },
    )


@router.post(
    "/",
    response_model=LeadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new lead (admin only)",
)
def create_lead(
    data: LeadCreate,
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> LeadResponse:
    lead = LeadService.create_lead(db=db, data=data)
    return LeadResponse.model_validate(lead)


@router.post(
    "/bulk",
    summary="Bulk import leads from CSV (admin only)",
)
def bulk_import_leads(
    csv_file: UploadFile = File(..., description="CSV file with lead data"),
    current_admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Dict[str, object]:
    rows = parse_leads_csv(csv_file)
    return LeadService.bulk_import_leads(db=db, csv_data=rows)
