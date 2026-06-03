from __future__ import annotations

from pydantic import BaseModel, Field


class AdminAuthRequest(BaseModel):
    password: str


class CrawlJobRunRequest(BaseModel):
    include_llm_extraction: bool = False
    extraction_mode: str = Field(default="none", pattern="^(none|screening_only|enqueue_only|realtime|batch)$")
    include_exclusive_right_pipeline: bool = False
    exclusive_right_pipeline_mode: str = Field(default="batch", pattern="^(none|screening_only|enqueue_only|batch|realtime)$")
    exclusive_right_auto_submit_batch: bool = False
    exclusive_right_auto_import_when_completed: bool = False
    exclusive_right_auto_consolidate: bool = True
    exclusive_right_limit: int | None = Field(default=None, ge=1, le=10000)
    include_reinsurers: bool = False
    include_foreign_branches: bool = False


class CrawlIncrementalRequest(CrawlJobRunRequest):
    days_back: int = Field(default=14, ge=1, le=30)


class CrawlManualRangeRequest(CrawlJobRunRequest):
    date_from: str
    date_to: str


class NaverNewsSearchPreviewRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    display: int = Field(default=10, ge=1, le=100)
    start: int = Field(default=1, ge=1, le=1000)
    sort: str = Field(default="date", pattern="^(date|sim)$")


class LLMBatchCreateRequest(BaseModel):
    task_type: str = Field(default="extract", pattern="^(extract|verify|adjudicate|cheap_classify|exclusive_right_extract|exclusive_right_verify|exclusive_right_consolidation)$")
    provider: str = Field(default="gemini")
    model_name: str = Field(default="gemini-2.5-flash")
    limit: int = Field(default=1000, ge=1, le=10000)
    submit: bool = False
    crawl_job_id: int | None = None


class ProductConsolidationRunRequest(BaseModel):
    mode: str = Field(default="dry_run", pattern="^(dry_run|rule_only_apply|apply_with_llm_gray_blocks)$")
    target: str = Field(default="all_provisional", pattern="^(new_since_last_job|all_provisional|all|selected)$")
    limit: int = Field(default=500, ge=1, le=10000)
    use_llm_for_gray_blocks: bool = False


class LLMConsolidationReviewRequest(BaseModel):
    mode: str = Field(default="dry_run", pattern="^(dry_run|apply)$")
    target: str = Field(default="all", pattern="^(all|company|candidates|selected|all_provisional|new_since_last_job)$")
    company_name: str | None = None
    limit: int = Field(default=1000, ge=1, le=10000)
    max_companies: int | None = Field(default=None, ge=1, le=500)
    max_blocks: int = Field(default=20, ge=1, le=100)


class ProductConsolidationManualMergeRequest(BaseModel):
    canonical_product_id: int
    duplicate_product_ids: list[int] = Field(default_factory=list)
    reason: str | None = None


class ProductConsolidationRejectMergeRequest(BaseModel):
    block_id: int
    reason: str | None = None


class ExclusiveRightExtractPendingRequest(BaseModel):
    crawl_job_id: int | None = None
    limit: int = Field(default=100, ge=1, le=1000)
    mode: str = Field(default="enqueue_only", pattern="^(none|screening_only|enqueue_only|realtime|batch)$")
    date_from: str | None = None
    date_to: str | None = None


class ExclusiveRightConsolidateRequest(BaseModel):
    crawl_job_id: int | None = None
    mode: str = Field(default="dry_run", pattern="^(dry_run|rule_only_apply)$")
    date_from: str | None = None
    date_to: str | None = None
