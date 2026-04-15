import logging
from datetime import datetime, timezone
from typing import Dict, Literal

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db, require_admin
from app.models.user import User
from app.schemas.lead import LeadCreate, LeadDashboardSummaryResponse, LeadListResponse, LeadOutcomeResponse, LeadOutcomeUpdateRequest, LeadResponse 
from app.services.lead_service import LeadService
from app.utils.csv_generator import LEAD_CSV_HEADERS, LEAD_CSV_REQUIRED_VALUE_FIELDS, parse_leads_csv

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/leads", tags=["leads"])


@router.get(
    "/",
    response_model=LeadListResponse,
    summary="Get leads for current user",
)
def list_available_leads(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    delivery_status: Literal["all", "available", "delivered"] = Query("all"),
    outcome_status: Literal["all", "new", "contacted", "appointment_set"] = Query("all"),
    search: str | None = Query(default=None),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> LeadListResponse:
    data = LeadService.get_available_leads_for_user(
        db=db,
        user=current_user,
        page=page,
        size=size,
        delivery_status=delivery_status,
        outcome_status=outcome_status,
        search=search,
    )
    items = [
        LeadResponse.model_validate(LeadService.to_advisor_lead_list_item_payload(lead))
        for lead in data["items"]
    ]
    return LeadListResponse(
        items=items,
        total=data["total"],
        page=data["page"],
        size=data["size"],
    )


@router.post(
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
    "/download/delivered",
    summary="Re-download previously delivered leads as CSV",
    response_class=StreamingResponse,
)
def download_delivered_leads_csv(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    csv_iterator = LeadService.download_delivered_leads_csv(db=db, user=current_user)
    filename = f"delivered_leads_{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"

    return StreamingResponse(
        csv_iterator,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Cache-Control": "no-cache",
        },
    )

@router.get(
    "/dashboard/summary",
    response_model=LeadDashboardSummaryResponse,
    summary="Advisor dashboard lead/outcome/settings summary",
)
def get_dashboard_summary(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> LeadDashboardSummaryResponse:
    data = LeadService.get_dashboard_summary(db=db, user=current_user)
    return LeadDashboardSummaryResponse(**data)


@router.put(
    "/{lead_id}/outcome",
    response_model=LeadOutcomeResponse,
    summary="Save advisor outcome for a lead",
)
def save_lead_outcome(
    lead_id: int,
    payload: LeadOutcomeUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> LeadOutcomeResponse:
    outcome = LeadService.upsert_lead_outcome(
        db=db,
        user=current_user,
        lead_id=lead_id,
        payload=payload,
    )
    return LeadOutcomeResponse.model_validate(outcome)


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
    result = LeadService.bulk_import_leads(
        db=db,
        csv_data=rows,
        actor_user_id=current_admin.id,
    )
    return result


@router.get(
    "/bulk/schema",
    summary="Get lead bulk import CSV schema (admin only)",
)
def get_bulk_import_schema(
    current_admin: User = Depends(require_admin),
) -> Dict[str, object]:
    _ = current_admin
    return {
        "headers": LEAD_CSV_HEADERS,
        "required_values": LEAD_CSV_REQUIRED_VALUE_FIELDS,
        "system_fields": {
            "source": "csv_import",
        },
    }
