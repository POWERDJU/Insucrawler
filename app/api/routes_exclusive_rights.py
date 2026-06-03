from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.exclusive_right import ExclusiveRightExportRequest
from app.services.exclusive_right_service import ExclusiveRightService

router = APIRouter()


@router.get("")
def list_exclusive_rights(
    insurance_type: str | None = None,
    company_id: int | None = None,
    company_name: str | None = None,
    company_names: list[str] | None = Query(default=None),
    acquired_year_month_from: str | None = None,
    acquired_year_month_to: str | None = None,
    months_back: int | None = None,
    include_review: bool = False,
    keyword: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> dict:
    items = ExclusiveRightService().list_rights(
        db,
        insurance_type=insurance_type,
        company_id=company_id,
        company_name=company_name,
        company_names=company_names,
        acquired_year_month_from=acquired_year_month_from,
        acquired_year_month_to=acquired_year_month_to,
        months_back=months_back,
        include_review=include_review,
        keyword=keyword,
        limit=limit,
    )
    return {"items": items, "count": len(items)}


@router.post("/export")
def export_exclusive_rights(request: ExclusiveRightExportRequest, db: Session = Depends(get_db)) -> StreamingResponse:
    workbook = ExclusiveRightService().export_workbook(db, request.model_dump())
    headers = {"Content-Disposition": 'attachment; filename="exclusive_rights.xlsx"'}
    return StreamingResponse(
        workbook,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


@router.get("/{exclusive_right_id}")
def exclusive_right_detail(exclusive_right_id: int, db: Session = Depends(get_db)) -> dict:
    detail = ExclusiveRightService().detail(db, exclusive_right_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="exclusive right not found")
    return detail
