from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.ingestion import ManualTextExtractionRequest
from app.services.extract_service import ExtractService

router = APIRouter()


@router.post("/article/{article_id}")
def extract_article(article_id: int, db: Session = Depends(get_db)) -> dict:
    return ExtractService().extract_article(db, article_id)


@router.post("/pending")
def extract_pending(limit: int = 20, db: Session = Depends(get_db)) -> dict:
    return ExtractService().extract_pending_articles(db, limit)


@router.post("/from-text")
def extract_from_text(request: ManualTextExtractionRequest, db: Session = Depends(get_db)) -> dict:
    return ExtractService().extract_from_text(db, request.title, request.text, request.source_note)
