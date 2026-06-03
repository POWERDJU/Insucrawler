from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.pivot import PivotRequest
from app.services.pivot_service import PivotService

router = APIRouter()


@router.post("/run")
def run_pivot(request: PivotRequest, db: Session = Depends(get_db)) -> dict:
    return PivotService().run_pivot(
        db,
        base=request.base,
        classification_mode=request.classification_mode,
        rows=request.rows,
        columns=request.columns,
        filters=request.filters,
        metrics=[metric.model_dump() for metric in request.metrics],
        include_review=request.include_review,
        min_confidence=request.min_confidence,
    )


@router.get("/presets")
def presets() -> list[dict]:
    return PivotService().presets()


@router.post("/export")
def export_pivot(request: PivotRequest, file_format: str = "csv", db: Session = Depends(get_db)) -> dict:
    result = run_pivot(request, db)
    suffix = "xlsx" if file_format == "xlsx" else "csv"
    path = f"data/exports/pivot_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.{suffix}"
    exported = PivotService().export(result, path, suffix)
    return {"status": "exported", "path": str(exported)}
