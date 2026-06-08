from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class DashboardQueryRequest(BaseModel):
    release_year: str = "전체"
    release_years: list[str] = Field(default_factory=list)
    release_month: str = "전체"
    insurance_type: str = "전체"
    company_names: list[str] = Field(default_factory=list)
    product_type_codes: list[str] = Field(default_factory=list)
    classification_mode: Literal["primary_only", "include_secondary"] = "primary_only"
    pivot_preset: str = "custom"
    custom_rows: list[str] = Field(default_factory=list)
    custom_columns: list[str] = Field(default_factory=list)
    custom_metrics: list[str] = Field(default_factory=list)
    include_review: bool = False
    min_confidence: float = 0.0
    include_reinsurers: bool = False
    include_foreign_branches: bool = False
    include_changed_companies: bool = True
    include_short_term_insurers: bool = True
    include_excluded_policy_products: bool = False
    keyword: str | None = None
    keyword_fields: list[str] = Field(default_factory=list)


class DashboardOptionsResponse(BaseModel):
    years: list[str]
    months: list[str]
    insurance_types: list[str]
    companies: list[dict[str, Any]]
    product_types: list[dict[str, Any]]
    pivot_presets: list[dict[str, str]]
