from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint

from app.db.database import Base
from app.utils.dates import utcnow


class TimestampMixin:
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


class DimCompany(Base, TimestampMixin):
    __tablename__ = "dim_company"

    company_id = Column(Integer, primary_key=True)
    company_name_normalized = Column(String(255), nullable=False, index=True)
    company_name_raw = Column(String(255))
    alias = Column(Text)
    insurance_type = Column(String(50))
    insurance_type_default = Column(String(50))
    company_role = Column(String(100))
    status_2024_2026 = Column(String(100), default="active")
    include_in_product_news_default = Column(String(1), default="Y", nullable=False)
    active_yn = Column(String(1), default="Y", nullable=False)
    valid_from = Column(String(10))
    valid_to = Column(String(10))
    predecessor_company = Column(String(255))
    successor_company = Column(String(255))
    establishment_year = Column(Integer)
    establishment_month = Column(Integer)
    establishment_day = Column(Integer)
    establishment_sort_date = Column(String(10))
    establishment_basis = Column(String(50))
    oldest_predecessor_year = Column(Integer)
    current_brand_year = Column(Integer)
    display_order_established = Column(Integer)
    sort_tie_breaker = Column(Integer)
    establishment_source_note = Column(Text)
    notes = Column(Text)


class FactCompanyEvent(Base):
    __tablename__ = "fact_company_event"

    company_event_id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("dim_company.company_id"), nullable=False, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    event_date = Column(String(10))
    related_company_name = Column(String(255))
    event_summary = Column(Text, nullable=False)
    source_note = Column(Text)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class DimProduct(Base, TimestampMixin):
    __tablename__ = "dim_product"

    product_id = Column(Integer, primary_key=True)
    normalized_product_name = Column(String(500), nullable=False, index=True)
    raw_product_name = Column(String(500), nullable=False)
    company_name_raw = Column(String(255))
    product_search_key = Column(String(1000), nullable=False, index=True)
    product_core_key = Column(String(1000), index=True)
    product_identity_key = Column(String(1200), index=True)
    company_id = Column(Integer, ForeignKey("dim_company.company_id"))
    insurance_type = Column(String(50), default="unknown")
    release_year_month = Column(String(7))
    release_year_month_basis = Column(String(100), default="unknown")
    release_year_month_source_article_id = Column(Integer, ForeignKey("fact_article.article_id"), nullable=True)
    release_year_month_source_type = Column(String(100))
    release_year_month_inferred_at = Column(DateTime)
    first_seen_month = Column(String(7))
    primary_product_type_code = Column(String(50), ForeignKey("dim_product_type.product_type_code"))
    product_category_summary = Column(Text)
    confidence_total = Column(Float, default=0.0)
    needs_review = Column(Boolean, default=True, nullable=False)
    product_status = Column(String(50), default="active", nullable=False, index=True)
    merged_into_product_id = Column(Integer, ForeignKey("dim_product.product_id"), nullable=True, index=True)
    canonical_product_id = Column(Integer, ForeignKey("dim_product.product_id"), nullable=True, index=True)
    alias_count = Column(Integer, default=0, nullable=False)
    consolidation_status = Column(String(50), default="pending", nullable=True, index=True)
    last_consolidated_at = Column(DateTime)
    partner_company_name = Column(String(255))
    partner_context_summary = Column(Text)

    __table_args__ = (UniqueConstraint("product_search_key", "company_id", name="uq_product_search_company"),)


class DimProductAlias(Base, TimestampMixin):
    __tablename__ = "dim_product_alias"

    product_alias_id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("dim_product.product_id"), nullable=False, index=True)
    raw_product_name = Column(String(500), nullable=False)
    normalized_product_name_candidate = Column(String(500))
    product_core_key = Column(String(1000), index=True)
    company_id = Column(Integer, ForeignKey("dim_company.company_id"), nullable=True, index=True)
    article_id = Column(Integer, ForeignKey("fact_article.article_id"), nullable=True, index=True)
    source_type = Column(String(100))
    first_seen_at = Column(DateTime, default=utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=utcnow, nullable=False)
    observation_count = Column(Integer, default=1, nullable=False)


class DimProductType(Base):
    __tablename__ = "dim_product_type"

    product_type_code = Column(String(50), primary_key=True)
    product_type_name_ko = Column(String(100), nullable=False)
    description = Column(Text)
    parent_type_code = Column(String(50))
    sort_order = Column(Integer, default=999)
    pivot_enabled = Column(String(1), default="Y", nullable=False)
    active_yn = Column(String(1), default="Y", nullable=False)


class DimPartnerCompany(Base, TimestampMixin):
    __tablename__ = "dim_partner_company"

    partner_id = Column(Integer, primary_key=True)
    partner_name_normalized = Column(String(255), nullable=False, index=True)
    alias = Column(Text)
    partner_type = Column(String(100), default="unknown")

    __table_args__ = (UniqueConstraint("partner_name_normalized", name="uq_partner_company_name"),)


class FactProductPartner(Base, TimestampMixin):
    __tablename__ = "fact_product_partner"

    product_partner_id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("dim_product.product_id"), nullable=False, index=True)
    partner_id = Column(Integer, ForeignKey("dim_partner_company.partner_id"), nullable=False, index=True)
    article_id = Column(Integer, ForeignKey("fact_article.article_id"), nullable=True, index=True)
    partner_role = Column(String(100), default="distribution_partner", nullable=False)
    evidence_text = Column(Text)
    confidence = Column(Float, default=0.0)

    __table_args__ = (UniqueConstraint("product_id", "partner_id", "article_id", "partner_role", name="uq_product_partner_context"),)


class FactProductMergeDecision(Base):
    __tablename__ = "fact_product_merge_decision"

    merge_decision_id = Column(Integer, primary_key=True)
    canonical_product_id = Column(Integer, ForeignKey("dim_product.product_id"), nullable=False, index=True)
    duplicate_product_id = Column(Integer, ForeignKey("dim_product.product_id"), nullable=False, index=True)
    decision_type = Column(String(100), nullable=False, index=True)
    decision_source = Column(String(100), nullable=False, index=True)
    confidence = Column(Float, default=0.0)
    reason = Column(Text)
    evidence_article_ids_json = Column(Text)
    alias_names_json = Column(Text)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    applied_at = Column(DateTime)
    applied_by = Column(String(255))
    needs_review = Column(Boolean, default=False, nullable=False)


class FactProductObservation(Base, TimestampMixin):
    __tablename__ = "fact_product_observation"

    observation_id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("dim_product.product_id"), nullable=True, index=True)
    article_id = Column(Integer, ForeignKey("fact_article.article_id"), nullable=True, index=True)
    raw_product_name = Column(String(500), nullable=False)
    normalized_product_name_candidate = Column(String(500))
    product_core_key = Column(String(1000), index=True)
    company_id = Column(Integer, ForeignKey("dim_company.company_id"), nullable=True, index=True)
    company_name_raw = Column(String(255))
    partner_company_name = Column(String(255), index=True)
    product_type_code = Column(String(50), ForeignKey("dim_product_type.product_type_code"), nullable=True, index=True)
    release_year_month = Column(String(7), index=True)
    article_title = Column(Text)
    article_description = Column(Text)
    source_url = Column(Text)
    observation_context_text = Column(Text)
    candidate_type = Column(String(100), default="unknown", nullable=False, index=True)
    confidence = Column(Float, default=0.0)


class FactProductConsolidationJob(Base):
    __tablename__ = "fact_product_consolidation_job"

    consolidation_job_id = Column(Integer, primary_key=True)
    status = Column(String(50), default="pending", nullable=False, index=True)
    trigger_type = Column(String(50), default="manual", nullable=False, index=True)
    mode = Column(String(50), default="dry_run", nullable=False, index=True)
    target_new_product_count = Column(Integer, default=0, nullable=False)
    observation_count = Column(Integer, default=0, nullable=False)
    provisional_product_count = Column(Integer, default=0, nullable=False)
    block_count = Column(Integer, default=0, nullable=False)
    auto_merge_count = Column(Integer, default=0, nullable=False)
    llm_review_count = Column(Integer, default=0, nullable=False)
    manual_review_count = Column(Integer, default=0, nullable=False)
    llm_call_count = Column(Integer, default=0, nullable=False)
    estimated_cost_usd = Column(Float, default=0.0, nullable=False)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    error_message = Column(Text)


class FactProductConsolidationBlock(Base, TimestampMixin):
    __tablename__ = "fact_product_consolidation_block"

    block_id = Column(Integer, primary_key=True)
    consolidation_job_id = Column(Integer, ForeignKey("fact_product_consolidation_job.consolidation_job_id"), nullable=False, index=True)
    block_key = Column(String(1000), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("dim_company.company_id"), nullable=True, index=True)
    partner_company_name = Column(String(255), nullable=True, index=True)
    release_month_window = Column(String(50))
    product_type_codes_json = Column(Text)
    candidate_product_ids_json = Column(Text)
    observation_ids_json = Column(Text)
    block_reason = Column(Text)
    status = Column(String(50), default="pending", nullable=False, index=True)


class FactArticle(Base, TimestampMixin):
    __tablename__ = "fact_article"

    article_id = Column(Integer, primary_key=True)
    source_api = Column(String(100), nullable=False, index=True)
    title = Column(Text, nullable=False)
    description = Column(Text)
    publisher = Column(String(255))
    url = Column(Text, nullable=False)
    original_url = Column(Text)
    pub_date = Column(DateTime)
    collected_at = Column(DateTime, default=utcnow, nullable=False)
    query = Column(String(500))
    query_group = Column(String(255), index=True)
    crawl_job_id = Column(Integer, ForeignKey("fact_crawl_job.crawl_job_id"), nullable=True, index=True)
    crawl_task_id = Column(Integer, ForeignKey("fact_crawl_task.crawl_task_id"), nullable=True, index=True)
    content_hash = Column(String(64), nullable=False, unique=True, index=True)
    extraction_status = Column(String(50), default="pending", index=True)
    multi_company_article_yn = Column(Boolean, default=False, nullable=False, index=True)
    multi_company_company_names_json = Column(Text)
    multi_company_detected_at = Column(DateTime)
    extraction_exclusion_reason = Column(Text)


class FactExclusiveUseRight(Base, TimestampMixin):
    __tablename__ = "fact_exclusive_use_right"

    exclusive_right_id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("dim_company.company_id"), nullable=True, index=True)
    company_name_normalized = Column(String(255), index=True)
    insurance_type = Column(String(50), index=True)
    subject_name = Column(String(500), nullable=False)
    subject_core_key = Column(String(1000), index=True)
    exclusivity_months = Column(Integer)
    acquired_year_month = Column(String(7), index=True)
    feature_summary = Column(Text)
    evidence_summary = Column(Text)
    primary_article_id = Column(Integer, ForeignKey("fact_article.article_id"), nullable=True, index=True)
    primary_article_title = Column(Text)
    primary_article_url = Column(Text)
    article_count = Column(Integer, default=0, nullable=False)
    confidence_total = Column(Float, default=0.0)
    needs_review = Column(Boolean, default=True, nullable=False, index=True)
    event_status = Column(String(50), default="review", nullable=False, index=True)
    merged_into_exclusive_right_id = Column(Integer, ForeignKey("fact_exclusive_use_right.exclusive_right_id"), nullable=True, index=True)
    canonical_exclusive_right_id = Column(Integer, ForeignKey("fact_exclusive_use_right.exclusive_right_id"), nullable=True, index=True)
    alias_names_json = Column(Text)
    evidence_text = Column(Text)

    __table_args__ = (
        Index("ix_exclusive_right_insurance_month", "insurance_type", "acquired_year_month"),
        Index("ix_exclusive_right_company_month", "company_id", "acquired_year_month"),
    )


class FactExclusiveUseRightObservation(Base, TimestampMixin):
    __tablename__ = "fact_exclusive_use_right_observation"

    observation_id = Column(Integer, primary_key=True)
    exclusive_right_id = Column(Integer, ForeignKey("fact_exclusive_use_right.exclusive_right_id"), nullable=True, index=True)
    article_id = Column(Integer, ForeignKey("fact_article.article_id"), nullable=True, index=True)
    source_url = Column(Text)
    company_id = Column(Integer, ForeignKey("dim_company.company_id"), nullable=True, index=True)
    company_name_normalized = Column(String(255), index=True)
    insurance_type = Column(String(50), index=True)
    raw_subject_name = Column(String(500), nullable=False)
    normalized_subject_name_candidate = Column(String(500))
    subject_core_key = Column(String(1000), index=True)
    exclusivity_months = Column(Integer)
    acquired_year_month = Column(String(7))
    feature_summary = Column(Text)
    article_title = Column(Text)
    evidence_text = Column(Text)
    status_candidate = Column(String(100), default="unknown", nullable=False, index=True)
    confidence = Column(Float, default=0.0)
    needs_review = Column(Boolean, default=True, nullable=False)


class FactExclusiveUseRightArticle(Base, TimestampMixin):
    __tablename__ = "fact_exclusive_use_right_article"

    exclusive_right_article_id = Column(Integer, primary_key=True)
    exclusive_right_id = Column(Integer, ForeignKey("fact_exclusive_use_right.exclusive_right_id"), nullable=False, index=True)
    article_id = Column(Integer, ForeignKey("fact_article.article_id"), nullable=False, index=True)
    confidence = Column(Float, default=0.0)
    evidence_summary = Column(Text)

    __table_args__ = (UniqueConstraint("exclusive_right_id", "article_id", name="uq_exclusive_right_article"),)


class FactExclusiveUseRightAlias(Base, TimestampMixin):
    __tablename__ = "fact_exclusive_use_right_alias"

    exclusive_right_alias_id = Column(Integer, primary_key=True)
    exclusive_right_id = Column(Integer, ForeignKey("fact_exclusive_use_right.exclusive_right_id"), nullable=False, index=True)
    raw_subject_name = Column(String(500), nullable=False)
    normalized_subject_name_candidate = Column(String(500))
    subject_core_key = Column(String(1000), index=True)
    article_id = Column(Integer, ForeignKey("fact_article.article_id"), nullable=True, index=True)
    first_seen_at = Column(DateTime, default=utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=utcnow, nullable=False)
    observation_count = Column(Integer, default=1, nullable=False)


class FactExclusiveUseRightMergeDecision(Base):
    __tablename__ = "fact_exclusive_use_right_merge_decision"

    merge_decision_id = Column(Integer, primary_key=True)
    canonical_exclusive_right_id = Column(Integer, ForeignKey("fact_exclusive_use_right.exclusive_right_id"), nullable=False, index=True)
    duplicate_exclusive_right_id = Column(Integer, ForeignKey("fact_exclusive_use_right.exclusive_right_id"), nullable=False, index=True)
    decision_type = Column(String(100), nullable=False, index=True)
    decision_source = Column(String(100), nullable=False, index=True)
    confidence = Column(Float, default=0.0)
    reason = Column(Text)
    evidence_article_ids_json = Column(Text)
    alias_names_json = Column(Text)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    applied_at = Column(DateTime)
    applied_by = Column(String(255))
    needs_review = Column(Boolean, default=False, nullable=False)


class FactContentScreening(Base):
    __tablename__ = "fact_content_screening"

    screening_id = Column(Integer, primary_key=True)
    article_id = Column(Integer, ForeignKey("fact_article.article_id"), nullable=False, index=True)
    source_type = Column(String(100))
    rule_relevance_score = Column(Float, default=0.0, nullable=False)
    matched_company_names_json = Column(Text)
    matched_product_type_codes_json = Column(Text)
    matched_launch_keywords_json = Column(Text)
    matched_negative_keywords_json = Column(Text)
    is_candidate = Column(Boolean, default=False, nullable=False)
    candidate_reason = Column(Text)
    llm_required_yn = Column(Boolean, default=False, nullable=False)
    llm_priority = Column(String(20), default="skip", nullable=False, index=True)
    exclusive_right_score = Column(Float, default=0.0, nullable=False)
    exclusive_right_candidate_yn = Column(Boolean, default=False, nullable=False, index=True)
    matched_exclusive_keywords_json = Column(Text)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class FactArticleSnippet(Base):
    __tablename__ = "fact_article_snippet"

    snippet_id = Column(Integer, primary_key=True)
    article_id = Column(Integer, ForeignKey("fact_article.article_id"), nullable=False, index=True)
    snippet_type = Column(String(100), nullable=False, index=True)
    snippet_text = Column(Text, nullable=False)
    sentence_index = Column(Integer)
    matched_keywords_json = Column(Text)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class FactProductCandidateCluster(Base, TimestampMixin):
    __tablename__ = "fact_product_candidate_cluster"

    candidate_cluster_id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("dim_company.company_id"), nullable=True, index=True)
    product_core_key = Column(String(1000), nullable=True, index=True)
    candidate_product_name = Column(String(500))
    candidate_company_name = Column(String(255))
    article_count = Column(Integer, default=0, nullable=False)
    source_article_ids_json = Column(Text)
    earliest_article_date = Column(DateTime)
    latest_article_date = Column(DateTime)
    screening_score = Column(Float, default=0.0)
    llm_status = Column(String(50), default="pending", nullable=False, index=True)


class FactLLMQueue(Base, TimestampMixin):
    __tablename__ = "fact_llm_queue"

    llm_queue_id = Column(Integer, primary_key=True)
    target_type = Column(String(100), nullable=False, index=True)
    target_id = Column(Integer, nullable=False, index=True)
    task_type = Column(String(50), nullable=False, index=True)
    priority = Column(String(20), default="medium", nullable=False, index=True)
    provider = Column(String(100))
    model_name = Column(String(255))
    batch_eligible_yn = Column(Boolean, default=False, nullable=False)
    crawl_job_id = Column(Integer, ForeignKey("fact_crawl_job.crawl_job_id"), nullable=True, index=True)
    llm_batch_job_id = Column(Integer, ForeignKey("fact_llm_batch_job.llm_batch_job_id"), nullable=True, index=True)
    status = Column(String(50), default="pending", nullable=False, index=True)
    attempts = Column(Integer, default=0, nullable=False)
    last_error = Column(Text)


class FactLLMBatchJob(Base, TimestampMixin):
    __tablename__ = "fact_llm_batch_job"

    llm_batch_job_id = Column(Integer, primary_key=True)
    provider = Column(String(100), nullable=False, index=True)
    model_name = Column(String(255), nullable=False)
    task_type = Column(String(50), nullable=False, index=True)
    crawl_job_id = Column(Integer, ForeignKey("fact_crawl_job.crawl_job_id"), nullable=True, index=True)
    provider_batch_id = Column(String(255), index=True)
    provider_status = Column(String(100))
    status = Column(String(50), default="pending", nullable=False, index=True)
    input_file_path = Column(Text)
    output_file_path = Column(Text)
    request_count = Column(Integer, default=0, nullable=False)
    completed_count = Column(Integer, default=0, nullable=False)
    failed_count = Column(Integer, default=0, nullable=False)
    submitted_at = Column(DateTime)
    completed_at = Column(DateTime)
    error_message = Column(Text)


class FactLLMResponseCache(Base):
    __tablename__ = "fact_llm_response_cache"

    cache_id = Column(Integer, primary_key=True)
    input_hash = Column(String(64), nullable=False, index=True)
    prompt_version = Column(String(100), nullable=False)
    schema_version = Column(String(100), nullable=False)
    provider = Column(String(100), nullable=False)
    model_name = Column(String(255), nullable=False)
    task_type = Column(String(50), nullable=False, index=True)
    output_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    hit_count = Column(Integer, default=0, nullable=False)
    last_used_at = Column(DateTime, default=utcnow, nullable=False)

    __table_args__ = (UniqueConstraint("input_hash", "prompt_version", "schema_version", "provider", "model_name", "task_type", name="uq_llm_response_cache_key"),)


class FactCrawlJob(Base, TimestampMixin):
    __tablename__ = "fact_crawl_job"

    crawl_job_id = Column(Integer, primary_key=True)
    job_name = Column(String(255), nullable=False, index=True)
    job_type = Column(String(50), nullable=False, index=True)
    status = Column(String(50), default="pending", nullable=False, index=True)
    date_from = Column(String(10), nullable=False)
    date_to = Column(String(10), nullable=False)
    requested_by = Column(String(255))
    requested_from = Column(String(255))
    include_llm_extraction = Column(Boolean, default=False, nullable=False)
    extraction_mode = Column(String(50), default="none", nullable=False, index=True)
    include_article_body_fetch = Column(Boolean, default=False, nullable=False)
    include_reinsurers = Column(Boolean, default=False, nullable=False)
    include_foreign_branches = Column(Boolean, default=False, nullable=False)
    include_exclusive_right_pipeline = Column(Boolean, default=False, nullable=False)
    exclusive_right_pipeline_mode = Column(String(50), default="batch", nullable=False)
    exclusive_right_auto_submit_batch = Column(Boolean, default=False, nullable=False)
    exclusive_right_auto_import_when_completed = Column(Boolean, default=False, nullable=False)
    exclusive_right_auto_consolidate = Column(Boolean, default=True, nullable=False)
    exclusive_right_limit = Column(Integer)
    exclusive_right_candidate_count = Column(Integer, default=0, nullable=False)
    exclusive_right_queue_created_count = Column(Integer, default=0, nullable=False)
    exclusive_right_batch_job_id = Column(Integer, ForeignKey("fact_llm_batch_job.llm_batch_job_id"), nullable=True, index=True)
    exclusive_right_batch_status = Column(String(100))
    exclusive_right_imported_count = Column(Integer, default=0, nullable=False)
    exclusive_right_canonical_count = Column(Integer, default=0, nullable=False)
    exclusive_right_consolidation_job_id = Column(Integer, nullable=True)
    exclusive_right_pipeline_status = Column(String(100), default="not_requested")
    exclusive_right_pipeline_error = Column(Text)
    pipeline_mode = Column(String(100), default="crawl_only", nullable=False, index=True)
    include_qwen_adjudication = Column(Boolean, default=False, nullable=False)
    qwen_priority = Column(Boolean, default=True, nullable=False)
    run_postprocess = Column(Boolean, default=True, nullable=False)
    run_consolidation = Column(Boolean, default=True, nullable=False)
    scheduled_run_at = Column(DateTime, nullable=True, index=True)
    scheduled_timezone = Column(String(100))
    postprocess_status = Column(String(100), default="not_requested", nullable=False, index=True)
    consolidation_status = Column(String(100), default="not_requested", nullable=False, index=True)
    qwen_review_status = Column(String(100), default="not_requested", nullable=False, index=True)
    full_review_job_id = Column(Integer, nullable=True, index=True)
    report_path = Column(Text)
    total_tasks = Column(Integer, default=0, nullable=False)
    completed_tasks = Column(Integer, default=0, nullable=False)
    failed_tasks = Column(Integer, default=0, nullable=False)
    total_api_calls = Column(Integer, default=0, nullable=False)
    total_items_fetched = Column(Integer, default=0, nullable=False)
    total_articles_saved = Column(Integer, default=0, nullable=False)
    total_articles_duplicated = Column(Integer, default=0, nullable=False)
    total_articles_out_of_range = Column(Integer, default=0, nullable=False)
    total_articles_irrelevant = Column(Integer, default=0, nullable=False)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    error_message = Column(Text)


class FactFullReviewJob(Base, TimestampMixin):
    __tablename__ = "fact_full_review_job"

    full_review_job_id = Column(Integer, primary_key=True)
    status = Column(String(50), default="pending", nullable=False, index=True)
    mode = Column(String(50), default="dry_run", nullable=False, index=True)
    review_scope = Column(String(100), default="all", nullable=False, index=True)
    date_from = Column(String(10), nullable=True, index=True)
    date_to = Column(String(10), nullable=True, index=True)
    crawl_job_id = Column(Integer, ForeignKey("fact_crawl_job.crawl_job_id"), nullable=True, index=True)
    include_rule_review = Column(Boolean, default=True, nullable=False)
    include_qwen = Column(Boolean, default=True, nullable=False)
    qwen_priority = Column(Boolean, default=True, nullable=False)
    qwen_provider = Column(String(100), default="qwen")
    qwen_model_name = Column(String(255))
    max_products = Column(Integer, default=100, nullable=False)
    max_exclusive = Column(Integer, default=50, nullable=False)
    article_count = Column(Integer, default=0, nullable=False)
    product_candidate_count = Column(Integer, default=0, nullable=False)
    exclusive_candidate_count = Column(Integer, default=0, nullable=False)
    rule_reviewed_count = Column(Integer, default=0, nullable=False)
    qwen_processed_count = Column(Integer, default=0, nullable=False)
    qwen_provider_called_count = Column(Integer, default=0, nullable=False)
    qwen_accepted_count = Column(Integer, default=0, nullable=False)
    qwen_reviewed_count = Column(Integer, default=0, nullable=False)
    qwen_rejected_count = Column(Integer, default=0, nullable=False)
    qwen_remaining_count = Column(Integer, default=0, nullable=False)
    hard_gate_rejected_count = Column(Integer, default=0, nullable=False)
    applied_count = Column(Integer, default=0, nullable=False)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    summary_json = Column(Text)
    report_path = Column(Text)
    error_message = Column(Text)


class FactQwenReviewAudit(Base, TimestampMixin):
    __tablename__ = "fact_qwen_review_audit"

    qwen_review_audit_id = Column(Integer, primary_key=True)
    full_review_job_id = Column(Integer, ForeignKey("fact_full_review_job.full_review_job_id"), nullable=True, index=True)
    target_type = Column(String(100), nullable=False, index=True)
    target_id = Column(Integer, nullable=True, index=True)
    crawl_job_id = Column(Integer, ForeignKey("fact_crawl_job.crawl_job_id"), nullable=True, index=True)
    article_id = Column(Integer, ForeignKey("fact_article.article_id"), nullable=True, index=True)
    task_type = Column(String(100), nullable=False, index=True)
    provider = Column(String(100), default="qwen", nullable=False, index=True)
    model_name = Column(String(255))
    decision = Column(String(100), index=True)
    confidence = Column(Float, default=0.0)
    reason = Column(Text)
    evidence_text = Column(Text)
    before_json = Column(Text)
    after_json = Column(Text)
    warnings_json = Column(Text)
    hard_gate_status = Column(String(100), default="pass", nullable=False, index=True)
    apply_status = Column(String(100), default="not_applied", nullable=False, index=True)
    override_reason = Column(Text)


class FactCrawlTask(Base, TimestampMixin):
    __tablename__ = "fact_crawl_task"

    crawl_task_id = Column(Integer, primary_key=True)
    crawl_job_id = Column(Integer, ForeignKey("fact_crawl_job.crawl_job_id"), nullable=False, index=True)
    task_name = Column(String(500), nullable=False)
    status = Column(String(50), default="pending", nullable=False, index=True)
    date_from = Column(String(10), nullable=False)
    date_to = Column(String(10), nullable=False)
    year = Column(Integer)
    month = Column(Integer)
    company_id = Column(Integer, ForeignKey("dim_company.company_id"), nullable=True, index=True)
    company_name = Column(String(255))
    query_group = Column(String(255))
    query_text = Column(String(500), nullable=False)
    sort = Column(String(20), default="date", nullable=False)
    display = Column(Integer, default=100, nullable=False)
    start_position = Column(Integer, default=1, nullable=False)
    api_calls = Column(Integer, default=0, nullable=False)
    items_fetched = Column(Integer, default=0, nullable=False)
    articles_saved = Column(Integer, default=0, nullable=False)
    articles_duplicated = Column(Integer, default=0, nullable=False)
    articles_out_of_range = Column(Integer, default=0, nullable=False)
    articles_irrelevant = Column(Integer, default=0, nullable=False)
    last_error = Column(Text)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)


class FactCrawlEventLog(Base):
    __tablename__ = "fact_crawl_event_log"

    crawl_event_id = Column(Integer, primary_key=True)
    crawl_job_id = Column(Integer, ForeignKey("fact_crawl_job.crawl_job_id"), nullable=False, index=True)
    crawl_task_id = Column(Integer, ForeignKey("fact_crawl_task.crawl_task_id"), nullable=True, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    event_message = Column(Text, nullable=False)
    event_payload_json = Column(Text)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class FactProductArticle(Base, TimestampMixin):
    __tablename__ = "fact_product_article"

    product_article_id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("dim_product.product_id"), nullable=False, index=True)
    article_id = Column(Integer, ForeignKey("fact_article.article_id"), nullable=False, index=True)
    is_primary_product = Column(Boolean, default=True, nullable=False)
    extraction_status = Column(String(50), default="saved")
    confidence_total = Column(Float, default=0.0)
    needs_review = Column(Boolean, default=False, nullable=False)
    evidence_summary = Column(Text)

    __table_args__ = (UniqueConstraint("product_id", "article_id", name="uq_product_article"),)


class FactProductStructuredFeature(Base, TimestampMixin):
    __tablename__ = "fact_product_structured_feature"

    feature_id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("dim_product.product_id"), nullable=False, index=True)
    article_id = Column(Integer, ForeignKey("fact_article.article_id"), nullable=True, index=True)
    join_age_min = Column(Integer)
    join_age_max = Column(Integer)
    notification_type = Column(String(100))
    sales_channel = Column(String(255))
    simple_underwriting_yn = Column(Boolean)
    non_face_to_face_yn = Column(Boolean)
    renewal_type = Column(String(100))
    payment_period = Column(String(255))
    coverage_period = Column(String(255))
    evidence_text = Column(Text)
    confidence = Column(Float, default=0.0)


class FactProductNarrativeInsight(Base, TimestampMixin):
    __tablename__ = "fact_product_narrative_insight"

    insight_id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("dim_product.product_id"), nullable=False, index=True)
    article_id = Column(Integer, ForeignKey("fact_article.article_id"), nullable=True, index=True)
    feature_summary = Column(Text)
    product_development_summary = Column(Text)
    marketing_summary = Column(Text)
    target_customer_summary = Column(Text)
    underwriting_summary = Column(Text)
    channel_summary = Column(Text)
    coverage_summary = Column(Text)
    sales_summary = Column(Text)
    differentiation_summary = Column(Text)
    risk_note_summary = Column(Text)
    missing_info_summary = Column(Text)
    missing_fields_json = Column(Text)
    evidence_text = Column(Text)
    confidence = Column(Float, default=0.0)
    needs_review = Column(Boolean, default=False, nullable=False)


class FactProductMajorCoverage(Base, TimestampMixin):
    __tablename__ = "fact_product_major_coverage"

    coverage_id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("dim_product.product_id"), nullable=False, index=True)
    article_id = Column(Integer, ForeignKey("fact_article.article_id"), nullable=True, index=True)
    coverage_name_raw = Column(String(500))
    coverage_name_normalized = Column(String(500), index=True)
    risk_area = Column(String(100), index=True)
    benefit_type = Column(String(100), index=True)
    coverage_group = Column(String(255))
    max_amount_krw = Column(Integer)
    raw_amount_text = Column(String(255))
    amount_basis = Column(Text)
    condition_text = Column(Text)
    limit_text = Column(Text)
    coverage_summary = Column(Text)
    detail_level = Column(String(100), default="unknown")
    is_main_coverage = Column(Boolean, default=True, nullable=False)
    display_order = Column(Integer, default=0)
    evidence_text = Column(Text)
    confidence = Column(Float, default=0.0)
    needs_human_review = Column(Boolean, default=False, nullable=False)


class FactCoverageEvidence(Base):
    __tablename__ = "fact_coverage_evidence"

    coverage_evidence_id = Column(Integer, primary_key=True)
    coverage_id = Column(Integer, ForeignKey("fact_product_major_coverage.coverage_id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("dim_product.product_id"), nullable=False, index=True)
    article_id = Column(Integer, ForeignKey("fact_article.article_id"), nullable=True, index=True)
    raw_coverage_text = Column(Text)
    evidence_text = Column(Text)
    source_title = Column(Text)
    source_url = Column(Text)
    pub_date = Column(DateTime)
    extraction_confidence = Column(Float, default=0.0)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class FactSalesMetricStructured(Base, TimestampMixin):
    __tablename__ = "fact_sales_metric_structured"

    sales_metric_id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("dim_product.product_id"), nullable=False, index=True)
    article_id = Column(Integer, ForeignKey("fact_article.article_id"), nullable=True, index=True)
    metric_name = Column(String(100), nullable=False, index=True)
    metric_value = Column(Numeric(18, 2), nullable=False)
    metric_unit = Column(String(100))
    metric_period = Column(String(255))
    metric_basis = Column(Text)
    evidence_text = Column(Text)
    confidence = Column(Float, default=0.0)
    needs_human_review = Column(Boolean, default=False, nullable=False)


class FactManualIngestion(Base):
    __tablename__ = "fact_manual_ingestion"

    manual_ingestion_id = Column(Integer, primary_key=True)
    input_type = Column(String(50), nullable=False, index=True)
    input_title = Column(Text)
    input_text = Column(Text)
    input_json = Column(Text)
    submitted_by = Column(String(255))
    created_at = Column(DateTime, default=utcnow, nullable=False)
    processing_status = Column(String(50), default="pending", index=True)


class FactExtractionRawJson(Base):
    __tablename__ = "fact_extraction_raw_json"

    extraction_id = Column(Integer, primary_key=True)
    article_id = Column(Integer, ForeignKey("fact_article.article_id"), nullable=True, index=True)
    manual_ingestion_id = Column(Integer, ForeignKey("fact_manual_ingestion.manual_ingestion_id"), nullable=True, index=True)
    input_source_type = Column(String(50), nullable=False)
    input_source_id = Column(Integer)
    model_name = Column(String(255))
    provider = Column(String(100))
    prompt_version = Column(String(100))
    schema_version = Column(String(100))
    raw_json = Column(Text, nullable=False)
    validation_status = Column(String(50), default="unknown")
    created_at = Column(DateTime, default=utcnow, nullable=False)


class FactLLMRun(Base):
    __tablename__ = "fact_llm_run"

    llm_run_id = Column(Integer, primary_key=True)
    article_id = Column(Integer, ForeignKey("fact_article.article_id"), nullable=True, index=True)
    manual_ingestion_id = Column(Integer, ForeignKey("fact_manual_ingestion.manual_ingestion_id"), nullable=True, index=True)
    llm_queue_id = Column(Integer, ForeignKey("fact_llm_queue.llm_queue_id"), nullable=True, index=True)
    llm_batch_job_id = Column(Integer, ForeignKey("fact_llm_batch_job.llm_batch_job_id"), nullable=True, index=True)
    task_type = Column(String(50), nullable=False, index=True)
    provider = Column(String(100), nullable=False, index=True)
    model_name = Column(String(255), nullable=False)
    prompt_version = Column(String(100))
    schema_version = Column(String(100))
    input_hash = Column(String(64), index=True)
    output_json = Column(Text)
    validation_status = Column(String(50), default="unknown")
    token_input = Column(Integer)
    token_output = Column(Integer)
    latency_ms = Column(Integer)
    cost_estimate = Column(Float)
    cached_yn = Column(Boolean, default=False, nullable=False)
    batch_yn = Column(Boolean, default=False, nullable=False)
    estimated_cost_usd = Column(Float)
    input_chars = Column(Integer)
    output_chars = Column(Integer)
    estimate_quality = Column(String(50))
    grounded_yn = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class FactLLMCostLog(Base):
    __tablename__ = "fact_llm_cost_log"

    llm_cost_id = Column(Integer, primary_key=True)
    llm_run_id = Column(Integer, ForeignKey("fact_llm_run.llm_run_id"), nullable=False, index=True)
    provider = Column(String(100), nullable=False, index=True)
    model_name = Column(String(255), nullable=False)
    task_type = Column(String(50), nullable=False, index=True)
    input_tokens = Column(Integer, default=0, nullable=False)
    output_tokens = Column(Integer, default=0, nullable=False)
    cached_tokens = Column(Integer, default=0, nullable=False)
    estimated_cost_usd = Column(Float, default=0.0, nullable=False)
    batch_yn = Column(Boolean, default=False, nullable=False)
    grounded_yn = Column(Boolean, default=False, nullable=False)
    estimate_quality = Column(String(50), default="rough", nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class FactExtractionComparison(Base):
    __tablename__ = "fact_extraction_comparison"

    comparison_id = Column(Integer, primary_key=True)
    article_id = Column(Integer, ForeignKey("fact_article.article_id"), nullable=True, index=True)
    manual_ingestion_id = Column(Integer, ForeignKey("fact_manual_ingestion.manual_ingestion_id"), nullable=True, index=True)
    product_id = Column(Integer, ForeignKey("dim_product.product_id"), nullable=True, index=True)
    extractor_run_id = Column(Integer, ForeignKey("fact_llm_run.llm_run_id"), nullable=False)
    verifier_run_id = Column(Integer, ForeignKey("fact_llm_run.llm_run_id"), nullable=True)
    adjudicator_run_id = Column(Integer, ForeignKey("fact_llm_run.llm_run_id"), nullable=True)
    agreement_score = Column(Float, default=0.0)
    conflict_count = Column(Integer, default=0)
    critical_conflict_count = Column(Integer, default=0)
    final_status = Column(String(50), default="unknown")
    needs_human_review = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)


class FactExtractionFieldAudit(Base):
    __tablename__ = "fact_extraction_field_audit"

    field_audit_id = Column(Integer, primary_key=True)
    comparison_id = Column(Integer, ForeignKey("fact_extraction_comparison.comparison_id"), nullable=False, index=True)
    field_path = Column(String(1000), nullable=False)
    extractor_value = Column(Text)
    verifier_verdict = Column(String(100))
    suggested_value = Column(Text)
    evidence_text = Column(Text)
    severity = Column(String(50), default="low")
    final_value = Column(Text)
    final_basis = Column(Text)
    created_at = Column(DateTime, default=utcnow, nullable=False)
