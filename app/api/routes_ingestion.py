from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.ingestion import StructuredProductIngestionRequest
from app.services.ingestion_service import IngestionService

router = APIRouter()


@router.post("/structured-product")
def structured_product(request: StructuredProductIngestionRequest, db: Session = Depends(get_db)) -> dict:
    product = IngestionService().upsert_structured_product(db, request.model_dump())
    return {"status": "saved", "product_id": product.product_id}
