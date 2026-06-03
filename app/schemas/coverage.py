from __future__ import annotations

from pydantic import BaseModel


class CoverageResponse(BaseModel):
    coverage_id: int
    coverage_name_raw: str | None = None
    coverage_name_normalized: str | None = None
    risk_area: str | None = None
    benefit_type: str | None = None
    max_amount_krw: int | None = None
    detail_level: str | None = None
    evidence_text: str | None = None
    confidence: float | None = None
    needs_human_review: bool = False
