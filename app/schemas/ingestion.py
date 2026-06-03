from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ManualTextExtractionRequest(BaseModel):
    title: str | None = None
    text: str
    source_note: str | None = None


class StructuredProductIngestionRequest(BaseModel):
    product: dict[str, Any]
    product_type_assignments: list[dict[str, Any]] = Field(default_factory=list)
    features: dict[str, Any] = Field(default_factory=dict)
    narrative_insights: dict[str, Any] = Field(default_factory=dict)
    major_coverages: list[dict[str, Any]] = Field(default_factory=list)
    sales_metrics: list[dict[str, Any]] = Field(default_factory=list)
    submitted_by: str | None = None


class IngestionResponse(BaseModel):
    product_id: int | None = None
    manual_ingestion_id: int | None = None
    status: str
    message: str | None = None
