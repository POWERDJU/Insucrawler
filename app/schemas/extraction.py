from __future__ import annotations

from pydantic import BaseModel


class ExtractionRunResponse(BaseModel):
    status: str
    article_id: int | None = None
    manual_ingestion_id: int | None = None
    product_ids: list[int] = []
    message: str | None = None
