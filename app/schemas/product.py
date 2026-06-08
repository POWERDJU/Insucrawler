from __future__ import annotations

from pydantic import BaseModel


class ProductSearchResult(BaseModel):
    product_id: int
    raw_product_name: str
    normalized_product_name: str
    company_name: str | None = None
    insurance_type: str | None = None
    release_year_month: str | None = None
    primary_product_type: str | None = None
    coverage_summary: str | None = None
    major_coverage_count: int = 0
    article_count: int = 0
    confidence_total: float = 0.0
    needs_review: bool = False


class ManualTypeAssignmentRequest(BaseModel):
    product_type_code: str
    evidence_text: str | None = None
    confidence: float = 1.0


class ManualCoverageRequest(BaseModel):
    coverage_name_raw: str
    coverage_name_normalized: str | None = None
    risk_area: str = "unknown"
    benefit_type: str = "unknown"
    coverage_group: str | None = None
    max_amount_krw: int | None = None
    raw_amount_text: str | None = None
    amount_basis: str | None = "manual"
    condition_text: str | None = None
    limit_text: str | None = None
    coverage_summary: str | None = None
    detail_level: str = "exact_coverage"
    is_main_coverage: bool = True
    evidence_text: str | None = None
    confidence: float = 1.0
