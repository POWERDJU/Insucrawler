from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator


InsuranceType = Literal["손해보험", "생명보험", "unknown"]
ReleaseBasis = Literal["explicit_in_article", "inferred_from_article_date", "first_seen_only", "earliest_related_article_month", "external_grounded_source", "manual", "unknown"]
DetailLevel = Literal["exact_coverage", "coverage_group", "marketing_statement", "unknown"]


class ArticleRelevance(BaseModel):
    is_relevant: bool
    relevance_type: Literal["new_product", "sales_performance", "product_feature", "market_trend", "irrelevant"]
    reason: str | None = None


class ProductIdentity(BaseModel):
    raw_product_name: str | None = None
    normalized_product_name_candidate: str | None = None
    company_name_raw: str | None = None
    company_name_candidate: str | None = None
    insurance_type: InsuranceType = "unknown"
    release_year_month: str | None = None
    release_year_month_basis: ReleaseBasis = "unknown"

    @field_validator("release_year_month")
    @classmethod
    def validate_year_month(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if len(value) != 7 or value[4] != "-":
            raise ValueError("release_year_month must be YYYY-MM")
        return value


class ProductTypeValue(BaseModel):
    code: str
    name_ko: str | None = None
    basis: str | None = None
    evidence_text: str | None = None
    confidence: float = Field(ge=0, le=1, default=0)


class ProductTypeClassification(BaseModel):
    primary_product_type: ProductTypeValue
    secondary_product_types: list[ProductTypeValue] = Field(default_factory=list)
    needs_human_review: bool = False


class StructuredFeatures(BaseModel):
    join_age_min: int | None = None
    join_age_max: int | None = None
    notification_type: str | None = "unknown"
    sales_channels: list[str] = Field(default_factory=list)
    simple_underwriting_yn: bool | None = None
    non_face_to_face_yn: bool | None = None
    renewal_type: str | None = "unknown"
    payment_period: str | None = None
    coverage_period: str | None = None


class NarrativeInsights(BaseModel):
    feature_summary: str | None = None
    product_development_summary: str | None = None
    marketing_summary: str | None = None
    target_customer_summary: str | None = None
    underwriting_summary: str | None = None
    channel_summary: str | None = None
    coverage_summary: str | None = None
    sales_summary: str | None = None
    differentiation_summary: str | None = None
    risk_note_summary: str | None = None
    missing_info_summary: str | None = None


class MajorCoverageExtraction(BaseModel):
    coverage_name_raw: str | None = None
    coverage_name_normalized: str | None = None
    risk_area: str = "unknown"
    benefit_type: str = "unknown"
    coverage_group: str | None = None
    max_amount_krw: int | None = None
    raw_amount_text: str | None = None
    amount_basis: str | None = None
    condition_text: str | None = None
    limit_text: str | None = None
    coverage_summary: str | None = None
    detail_level: DetailLevel = "unknown"
    is_main_coverage: bool = True
    display_order: int = 0
    evidence_text: str | None = None
    confidence: float = Field(ge=0, le=1, default=0)
    needs_human_review: bool = False

    @field_validator("detail_level", mode="before")
    @classmethod
    def normalize_detail_level(cls, value: str | None) -> str:
        if value is None:
            return "unknown"
        normalized = str(value).strip()
        aliases = {
            "high_level": "coverage_group",
            "summary": "coverage_group",
            "group": "coverage_group",
            "general": "coverage_group",
            "marketing": "marketing_statement",
            "exact": "exact_coverage",
        }
        return aliases.get(normalized, normalized)

    @model_validator(mode="after")
    def require_evidence_for_structured_coverage(self):
        if self.detail_level in {"exact_coverage", "coverage_group"} and not self.evidence_text:
            self.needs_human_review = True
        return self


class SalesMetricExtraction(BaseModel):
    metric_name: str
    metric_value: float
    metric_unit: str | None = None
    metric_period: str | None = None
    metric_basis: str | None = None
    evidence_text: str | None = None
    confidence: float = Field(ge=0, le=1, default=0)
    needs_human_review: bool = False

    @model_validator(mode="after")
    def require_sales_evidence(self):
        if not self.evidence_text:
            self.needs_human_review = True
        return self


class ProductEvidence(BaseModel):
    product_name_evidence: str | None = None
    company_evidence: str | None = None
    release_date_evidence: str | None = None
    feature_evidence: str | None = None
    coverage_evidence: str | None = None
    sales_evidence: str | None = None


class ProductConfidence(BaseModel):
    identity: float = Field(ge=0, le=1, default=0)
    product_type: float = Field(ge=0, le=1, default=0)
    features: float = Field(ge=0, le=1, default=0)
    coverage: float = Field(ge=0, le=1, default=0)
    sales: float = Field(ge=0, le=1, default=0)
    narrative: float = Field(ge=0, le=1, default=0)

    def total(self) -> float:
        values = [self.identity, self.product_type, self.features, self.coverage, self.sales, self.narrative]
        return sum(values) / len(values)


class ProductExtraction(BaseModel):
    identity: ProductIdentity
    product_type_classification: ProductTypeClassification
    structured_features: StructuredFeatures = Field(default_factory=StructuredFeatures)
    narrative_insights: NarrativeInsights = Field(default_factory=NarrativeInsights)
    missing_fields: list[str] = Field(default_factory=list)
    major_coverages: list[MajorCoverageExtraction] = Field(default_factory=list)
    sales_metrics: list[SalesMetricExtraction] = Field(default_factory=list)
    evidence: ProductEvidence = Field(default_factory=ProductEvidence)
    confidence: ProductConfidence = Field(default_factory=ProductConfidence)
    needs_human_review: bool = False

    @model_validator(mode="after")
    def mark_review_without_core_evidence(self):
        if self.identity.raw_product_name and not self.evidence.product_name_evidence:
            self.needs_human_review = True
        if self.identity.company_name_raw and not self.evidence.company_evidence:
            self.needs_human_review = True
        return self


class ExtractionResult(BaseModel):
    article_relevance: ArticleRelevance
    products: list[ProductExtraction] = Field(default_factory=list)


class FieldCheck(BaseModel):
    field_path: str
    extracted_value: object | None = None
    verdict: Literal["supported", "unsupported", "inferred", "incorrect", "ambiguous"]
    reason: str | None = None
    suggested_value: object | None = None
    suggested_basis: str | None = None
    evidence_text: str | None = None
    severity: Literal["low", "medium", "high", "critical"] = "low"


class VerificationResult(BaseModel):
    verification_status: Literal["pass", "fail", "partial", "conflict"]
    field_checks: list[FieldCheck] = Field(default_factory=list)
    unsupported_fields: list[str] = Field(default_factory=list)
    inferred_fields: list[str] = Field(default_factory=list)
    corrected_fields: list[str] = Field(default_factory=list)
    overall_confidence: float = Field(ge=0, le=1, default=0)
    needs_human_review: bool = True
    recommended_action: Literal["save", "save_with_review", "reject", "adjudicate"] = "save_with_review"


def validate_extraction_payload(payload: dict) -> ExtractionResult:
    return ExtractionResult.model_validate(payload)


def validate_verification_payload(payload: dict) -> VerificationResult:
    return VerificationResult.model_validate(payload)


def extraction_save_issues(result: ExtractionResult) -> list[str]:
    issues: list[str] = []
    for idx, product in enumerate(result.products):
        prefix = f"products[{idx}]"
        if product.identity.raw_product_name and not product.evidence.product_name_evidence:
            issues.append(f"{prefix}.identity.raw_product_name missing product_name_evidence")
        if product.identity.company_name_raw and not product.evidence.company_evidence:
            issues.append(f"{prefix}.identity.company_name_raw missing company_evidence")
        for c_idx, coverage in enumerate(product.major_coverages):
            if coverage.detail_level in {"exact_coverage", "coverage_group"} and not coverage.evidence_text:
                issues.append(f"{prefix}.major_coverages[{c_idx}] missing evidence_text")
        for s_idx, metric in enumerate(product.sales_metrics):
            if not metric.evidence_text:
                issues.append(f"{prefix}.sales_metrics[{s_idx}] missing evidence_text")
    return issues


def is_valid_extraction_payload(payload: dict) -> bool:
    try:
        validate_extraction_payload(payload)
        return True
    except ValidationError:
        return False
