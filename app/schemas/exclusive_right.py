from __future__ import annotations

from pydantic import BaseModel, Field


class ExclusiveRightExportRequest(BaseModel):
    insurance_type: str | None = None
    company_id: int | None = None
    company_name: str | None = None
    company_names: list[str] = Field(default_factory=list)
    acquired_year_month_from: str | None = None
    acquired_year_month_to: str | None = None
    months_back: int | None = None
    include_review: bool = False
    keyword: str | None = None
