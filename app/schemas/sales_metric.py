from __future__ import annotations

from pydantic import BaseModel


class SalesMetricResponse(BaseModel):
    sales_metric_id: int
    metric_name: str
    metric_value: float
    metric_unit: str | None = None
    metric_period: str | None = None
    evidence_text: str | None = None
    confidence: float | None = None
    needs_human_review: bool = False
