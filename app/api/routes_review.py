from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.review import ReviewResolveRequest
from app.services.review_service import ReviewService

router = APIRouter()


@router.get("/queue")
def queue(limit: int = 100, db: Session = Depends(get_db)) -> list[dict]:
    return ReviewService().queue(db, limit)


@router.post("/resolve")
def resolve(request: ReviewResolveRequest, db: Session = Depends(get_db)) -> dict:
    return ReviewService().resolve(db, request.entity_type, request.entity_id, request.updates)
