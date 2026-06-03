from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class PivotMetric(BaseModel):
    name: str
    agg: str
    field: str


class PivotRequest(BaseModel):
    base: Literal["product", "coverage", "sales"] = "product"
    classification_mode: Literal["primary_only", "include_secondary"] = "primary_only"
    rows: list[str] = Field(default_factory=list)
    columns: list[str] = Field(default_factory=list)
    filters: dict[str, list[Any]] = Field(default_factory=dict)
    metrics: list[PivotMetric] = Field(default_factory=list)
    include_review: bool = False
    min_confidence: float | None = None


class PivotResponse(BaseModel):
    base: str
    classification_mode: str
    rows: list[str]
    columns: list[str]
    metrics: list[str]
    records: list[dict[str, Any]]
