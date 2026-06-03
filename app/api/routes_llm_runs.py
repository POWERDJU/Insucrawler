from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.llm_run_service import LLMRunService

router = APIRouter()


@router.get("")
def list_runs(limit: int = 100, db: Session = Depends(get_db)) -> list[dict]:
    rows = LLMRunService().list_runs(db, limit)
    return [{column.name: getattr(row, column.name) for column in row.__table__.columns} for row in rows]


@router.get("/metrics")
def metrics(db: Session = Depends(get_db)) -> dict:
    return LLMRunService().metrics(db)
