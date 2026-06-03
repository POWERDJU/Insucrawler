from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


ExclusiveStatus = Literal["acquired", "applied_or_planned", "mentioned_only", "irrelevant"]


class ExclusiveRightRelevance(BaseModel):
    is_relevant: bool = False
    status: ExclusiveStatus = "irrelevant"
    reason: str | None = None


class ExclusiveSubjectExtract(BaseModel):
    raw_subject_name: str | None = None
    normalized_subject_name_candidate: str | None = None
    subject_core_key: str | None = None


class ExclusivePeriodExtract(BaseModel):
    months: int | None = None
    evidence_text: str | None = None


class ExclusiveAcquiredExtract(BaseModel):
    year_month: str | None = None


class ExclusiveRightItem(BaseModel):
    company_name_raw: str | None = None
    company_name_candidate: str | None = None
    insurance_type_candidate: Literal["생명보험", "손해보험", "unknown"] = "unknown"
    subject: ExclusiveSubjectExtract = Field(default_factory=ExclusiveSubjectExtract)
    exclusivity: ExclusivePeriodExtract = Field(default_factory=ExclusivePeriodExtract)
    acquired: ExclusiveAcquiredExtract = Field(default_factory=ExclusiveAcquiredExtract)
    feature_summary: str | None = None
    evidence_summary: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    needs_review: bool = False


class ExclusiveRightExtractionResult(BaseModel):
    exclusive_right_relevance: ExclusiveRightRelevance = Field(default_factory=ExclusiveRightRelevance)
    exclusive_rights: list[ExclusiveRightItem] = Field(default_factory=list)


def validate_exclusive_right_payload(payload: dict) -> ExclusiveRightExtractionResult:
    return ExclusiveRightExtractionResult.model_validate(payload)
