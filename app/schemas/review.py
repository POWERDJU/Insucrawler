from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ReviewResolveRequest(BaseModel):
    entity_type: str
    entity_id: int
    updates: dict[str, Any]
    reviewer: str | None = None


class ReviewQueueItem(BaseModel):
    entity_type: str
    entity_id: int
    label: str
    reason: str | None = None
    confidence: float | None = None
