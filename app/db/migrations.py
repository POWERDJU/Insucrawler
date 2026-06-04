from __future__ import annotations

from sqlalchemy import text

from app.db.database import Base, engine
from app.db import models  # noqa: F401


VIEW_SQL = {
    "vw_product_primary_type_pivot": """
        CREATE VIEW vw_product_primary_type_pivot AS
        SELECT
            p.product_id,
            p.normalized_product_name,
            p.raw_product_name,
            p.company_name_raw,
            p.product_search_key,
            p.product_core_key,
            p.product_identity_key,
            c.company_name_normalized AS company_name,
            c.company_role,
            c.status_2024_2026,
            c.include_in_product_news_default,
            p.insurance_type,
            p.release_year_month,
            p.release_year_month_basis,
            p.release_year_month_source_article_id,
            p.release_year_month_source_type,
            p.release_year_month_inferred_at,
            p.product_status,
            p.merged_into_product_id,
            p.canonical_product_id,
            p.alias_count,
            p.consolidation_status,
            p.last_consolidated_at,
            p.partner_company_name,
            p.partner_context_summary,
            p.primary_product_type_code AS product_type_code,
            pt.product_type_name_ko AS product_type_name,
            p.confidence_total,
            p.needs_review,
            COALESCE(pa.article_count, 0) AS article_count,
            ni.coverage_summary,
            sf.notification_type,
            sf.sales_channel
        FROM dim_product p
        LEFT JOIN dim_company c ON c.company_id = p.company_id
        LEFT JOIN dim_product_type pt ON pt.product_type_code = p.primary_product_type_code
        LEFT JOIN (
            SELECT pa.product_id, COUNT(DISTINCT pa.article_id) AS article_count
            FROM fact_product_article pa
            JOIN fact_article ar ON ar.article_id = pa.article_id
            WHERE COALESCE(ar.multi_company_article_yn, 0) = 0
              AND COALESCE(pa.extraction_status, 'saved') != 'excluded_multi_company'
            GROUP BY pa.product_id
        ) pa ON pa.product_id = p.product_id
        LEFT JOIN (
            SELECT ni.product_id, MAX(ni.insight_id) AS latest_insight_id
            FROM fact_product_narrative_insight ni
            LEFT JOIN fact_article ar ON ar.article_id = ni.article_id
            WHERE COALESCE(ar.multi_company_article_yn, 0) = 0
            GROUP BY ni.product_id
        ) latest_ni ON latest_ni.product_id = p.product_id
        LEFT JOIN fact_product_narrative_insight ni ON ni.insight_id = latest_ni.latest_insight_id
        LEFT JOIN (
            SELECT sf.product_id, MAX(sf.feature_id) AS latest_feature_id
            FROM fact_product_structured_feature sf
            LEFT JOIN fact_article ar ON ar.article_id = sf.article_id
            WHERE COALESCE(ar.multi_company_article_yn, 0) = 0
            GROUP BY sf.product_id
        ) latest_sf ON latest_sf.product_id = p.product_id
        LEFT JOIN fact_product_structured_feature sf ON sf.feature_id = latest_sf.latest_feature_id
        WHERE COALESCE(p.product_status, 'active') NOT IN ('merged', 'rejected', 'rejected_multi_company_only')
    """,
    "vw_product_all_type_pivot": """
        CREATE VIEW vw_product_all_type_pivot AS
        SELECT
            p.product_id,
            p.normalized_product_name,
            p.raw_product_name,
            p.company_name_raw,
            p.product_search_key,
            p.product_core_key,
            p.product_identity_key,
            c.company_name_normalized AS company_name,
            c.company_role,
            c.status_2024_2026,
            c.include_in_product_news_default,
            p.insurance_type,
            p.release_year_month,
            p.release_year_month_basis,
            p.release_year_month_source_article_id,
            p.release_year_month_source_type,
            p.release_year_month_inferred_at,
            p.product_status,
            p.merged_into_product_id,
            p.canonical_product_id,
            p.alias_count,
            p.consolidation_status,
            p.last_consolidated_at,
            p.partner_company_name,
            p.partner_context_summary,
            a.product_type_code,
            pt.product_type_name_ko AS product_type_name,
            a.assignment_role,
            p.confidence_total,
            p.needs_review,
            COALESCE(pa.article_count, 0) AS article_count,
            ni.coverage_summary,
            sf.notification_type,
            sf.sales_channel
        FROM dim_product p
        LEFT JOIN dim_company c ON c.company_id = p.company_id
        LEFT JOIN fact_product_type_assignment a ON a.product_id = p.product_id
        LEFT JOIN dim_product_type pt ON pt.product_type_code = a.product_type_code
        LEFT JOIN (
            SELECT pa.product_id, COUNT(DISTINCT pa.article_id) AS article_count
            FROM fact_product_article pa
            JOIN fact_article ar ON ar.article_id = pa.article_id
            WHERE COALESCE(ar.multi_company_article_yn, 0) = 0
              AND COALESCE(pa.extraction_status, 'saved') != 'excluded_multi_company'
            GROUP BY pa.product_id
        ) pa ON pa.product_id = p.product_id
        LEFT JOIN (
            SELECT ni.product_id, MAX(ni.insight_id) AS latest_insight_id
            FROM fact_product_narrative_insight ni
            LEFT JOIN fact_article ar ON ar.article_id = ni.article_id
            WHERE COALESCE(ar.multi_company_article_yn, 0) = 0
            GROUP BY ni.product_id
        ) latest_ni ON latest_ni.product_id = p.product_id
        LEFT JOIN fact_product_narrative_insight ni ON ni.insight_id = latest_ni.latest_insight_id
        LEFT JOIN (
            SELECT sf.product_id, MAX(sf.feature_id) AS latest_feature_id
            FROM fact_product_structured_feature sf
            LEFT JOIN fact_article ar ON ar.article_id = sf.article_id
            WHERE COALESCE(ar.multi_company_article_yn, 0) = 0
            GROUP BY sf.product_id
        ) latest_sf ON latest_sf.product_id = p.product_id
        LEFT JOIN fact_product_structured_feature sf ON sf.feature_id = latest_sf.latest_feature_id
        WHERE COALESCE(p.product_status, 'active') NOT IN ('merged', 'rejected', 'rejected_multi_company_only')
    """,
    "vw_product_type_coverage_pivot": """
        CREATE VIEW vw_product_type_coverage_pivot AS
        SELECT
            cov.coverage_id,
            p.product_id,
            c.company_name_normalized AS company_name,
            c.company_role,
            c.status_2024_2026,
            c.include_in_product_news_default,
            p.insurance_type,
            p.release_year_month,
            p.release_year_month_basis,
            p.product_status,
            p.merged_into_product_id,
            p.canonical_product_id,
            p.alias_count,
            p.consolidation_status,
            p.last_consolidated_at,
            a.product_type_code,
            pt.product_type_name_ko AS product_type_name,
            a.assignment_role,
            p.normalized_product_name AS product_name,
            p.company_name_raw,
            cov.risk_area,
            cov.benefit_type,
            cov.coverage_name_normalized AS coverage_name,
            cov.max_amount_krw,
            cov.detail_level,
            cov.confidence,
            cov.needs_human_review AS needs_review
        FROM fact_product_major_coverage cov
        JOIN dim_product p ON p.product_id = cov.product_id
        LEFT JOIN fact_article ar ON ar.article_id = cov.article_id
        LEFT JOIN dim_company c ON c.company_id = p.company_id
        LEFT JOIN fact_product_type_assignment a ON a.product_id = p.product_id
        LEFT JOIN dim_product_type pt ON pt.product_type_code = a.product_type_code
        WHERE cov.detail_level IN ('exact_coverage', 'coverage_group')
          AND COALESCE(ar.multi_company_article_yn, 0) = 0
          AND COALESCE(p.product_status, 'active') NOT IN ('merged', 'rejected', 'rejected_multi_company_only')
    """,
    "vw_product_sales_pivot": """
        CREATE VIEW vw_product_sales_pivot AS
        SELECT
            sm.sales_metric_id,
            p.product_id,
            c.company_name_normalized AS company_name,
            c.company_role,
            c.status_2024_2026,
            c.include_in_product_news_default,
            p.insurance_type,
            p.release_year_month,
            p.release_year_month_basis,
            p.product_status,
            p.merged_into_product_id,
            p.canonical_product_id,
            p.alias_count,
            p.consolidation_status,
            p.last_consolidated_at,
            a.product_type_code,
            pt.product_type_name_ko AS product_type_name,
            a.assignment_role,
            p.normalized_product_name AS product_name,
            p.company_name_raw,
            sm.metric_name,
            sm.metric_value,
            sm.metric_unit,
            sm.metric_period,
            sm.confidence,
            sm.needs_human_review AS needs_review
        FROM fact_sales_metric_structured sm
        JOIN dim_product p ON p.product_id = sm.product_id
        LEFT JOIN fact_article ar ON ar.article_id = sm.article_id
        LEFT JOIN dim_company c ON c.company_id = p.company_id
        LEFT JOIN fact_product_type_assignment a ON a.product_id = p.product_id
        LEFT JOIN dim_product_type pt ON pt.product_type_code = a.product_type_code
        WHERE COALESCE(ar.multi_company_article_yn, 0) = 0
          AND COALESCE(p.product_status, 'active') NOT IN ('merged', 'rejected', 'rejected_multi_company_only')
    """,
    "vw_product_search": """
        CREATE VIEW vw_product_search AS
        SELECT
            p.product_id,
            p.product_search_key,
            p.product_core_key,
            p.product_identity_key,
            p.normalized_product_name,
            p.raw_product_name,
            p.company_name_raw,
            c.company_name_normalized AS company_name,
            c.company_role,
            c.status_2024_2026,
            c.include_in_product_news_default,
            p.insurance_type,
            p.release_year_month,
            p.release_year_month_basis,
            p.release_year_month_source_article_id,
            p.release_year_month_source_type,
            p.release_year_month_inferred_at,
            p.primary_product_type_code,
            p.product_status,
            p.merged_into_product_id,
            p.canonical_product_id,
            p.alias_count,
            p.consolidation_status,
            p.last_consolidated_at,
            p.partner_company_name,
            p.partner_context_summary,
            pt.product_type_name_ko AS primary_product_type,
            (
                SELECT GROUP_CONCAT(pt2.product_type_name_ko, ',')
                FROM fact_product_type_assignment a2
                JOIN dim_product_type pt2 ON pt2.product_type_code = a2.product_type_code
                WHERE a2.product_id = p.product_id AND a2.assignment_role = 'secondary'
            ) AS secondary_product_types,
            ni.coverage_summary,
            p.confidence_total,
            p.needs_review
        FROM dim_product p
        LEFT JOIN dim_company c ON c.company_id = p.company_id
        LEFT JOIN dim_product_type pt ON pt.product_type_code = p.primary_product_type_code
        LEFT JOIN (
            SELECT ni.product_id, MAX(ni.insight_id) AS latest_insight_id
            FROM fact_product_narrative_insight ni
            LEFT JOIN fact_article ar ON ar.article_id = ni.article_id
            WHERE COALESCE(ar.multi_company_article_yn, 0) = 0
            GROUP BY ni.product_id
        ) latest_ni ON latest_ni.product_id = p.product_id
        LEFT JOIN fact_product_narrative_insight ni ON ni.insight_id = latest_ni.latest_insight_id
        WHERE COALESCE(p.product_status, 'active') NOT IN ('merged', 'rejected', 'rejected_multi_company_only')
    """,
}


COMPANY_COLUMN_MIGRATIONS = {
    "insurance_type": "VARCHAR(50)",
    "company_role": "VARCHAR(100)",
    "status_2024_2026": "VARCHAR(100) DEFAULT 'active'",
    "include_in_product_news_default": "VARCHAR(1) DEFAULT 'Y'",
    "valid_from": "VARCHAR(10)",
    "valid_to": "VARCHAR(10)",
    "predecessor_company": "VARCHAR(255)",
    "successor_company": "VARCHAR(255)",
    "establishment_year": "INTEGER",
    "establishment_month": "INTEGER",
    "establishment_day": "INTEGER",
    "establishment_sort_date": "VARCHAR(10)",
    "establishment_basis": "VARCHAR(50)",
    "oldest_predecessor_year": "INTEGER",
    "current_brand_year": "INTEGER",
    "display_order_established": "INTEGER",
    "sort_tie_breaker": "INTEGER",
    "establishment_source_note": "TEXT",
    "notes": "TEXT",
}


PRODUCT_COLUMN_MIGRATIONS = {
    "company_name_raw": "VARCHAR(255)",
    "product_core_key": "VARCHAR(1000)",
    "product_identity_key": "VARCHAR(1200)",
    "release_year_month_source_article_id": "INTEGER",
    "release_year_month_source_type": "VARCHAR(100)",
    "release_year_month_inferred_at": "DATETIME",
    "product_status": "VARCHAR(50) DEFAULT 'active'",
    "merged_into_product_id": "INTEGER",
    "canonical_product_id": "INTEGER",
    "alias_count": "INTEGER DEFAULT 0",
    "consolidation_status": "VARCHAR(50) DEFAULT 'pending'",
    "last_consolidated_at": "DATETIME",
    "partner_company_name": "VARCHAR(255)",
    "partner_context_summary": "TEXT",
}


ARTICLE_COLUMN_MIGRATIONS = {
    "crawl_job_id": "INTEGER",
    "crawl_task_id": "INTEGER",
    "multi_company_article_yn": "BOOLEAN DEFAULT 0",
    "multi_company_company_names_json": "TEXT",
    "multi_company_detected_at": "DATETIME",
    "extraction_exclusion_reason": "TEXT",
}


LLM_RUN_COLUMN_MIGRATIONS = {
    "llm_queue_id": "INTEGER",
    "llm_batch_job_id": "INTEGER",
    "cached_yn": "BOOLEAN DEFAULT 0",
    "batch_yn": "BOOLEAN DEFAULT 0",
    "estimated_cost_usd": "FLOAT",
    "input_chars": "INTEGER",
    "output_chars": "INTEGER",
    "estimate_quality": "VARCHAR(50)",
    "grounded_yn": "BOOLEAN DEFAULT 0",
}


LLM_COST_COLUMN_MIGRATIONS = {
    "estimate_quality": "VARCHAR(50) DEFAULT 'rough'",
}


LLM_QUEUE_COLUMN_MIGRATIONS = {
    "llm_batch_job_id": "INTEGER",
    "crawl_job_id": "INTEGER",
}


LLM_BATCH_JOB_COLUMN_MIGRATIONS = {
    "crawl_job_id": "INTEGER",
    "provider_batch_id": "VARCHAR(255)",
    "provider_status": "VARCHAR(100)",
    "input_file_path": "TEXT",
    "output_file_path": "TEXT",
    "request_count": "INTEGER DEFAULT 0",
    "completed_count": "INTEGER DEFAULT 0",
    "failed_count": "INTEGER DEFAULT 0",
    "submitted_at": "DATETIME",
    "completed_at": "DATETIME",
    "error_message": "TEXT",
}


CRAWL_JOB_COLUMN_MIGRATIONS = {
    "extraction_mode": "VARCHAR(50) DEFAULT 'none'",
    "include_exclusive_right_pipeline": "BOOLEAN DEFAULT 0",
    "exclusive_right_pipeline_mode": "VARCHAR(50) DEFAULT 'batch'",
    "exclusive_right_auto_submit_batch": "BOOLEAN DEFAULT 0",
    "exclusive_right_auto_import_when_completed": "BOOLEAN DEFAULT 0",
    "exclusive_right_auto_consolidate": "BOOLEAN DEFAULT 1",
    "exclusive_right_limit": "INTEGER",
    "exclusive_right_candidate_count": "INTEGER DEFAULT 0",
    "exclusive_right_queue_created_count": "INTEGER DEFAULT 0",
    "exclusive_right_batch_job_id": "INTEGER",
    "exclusive_right_batch_status": "VARCHAR(100)",
    "exclusive_right_imported_count": "INTEGER DEFAULT 0",
    "exclusive_right_canonical_count": "INTEGER DEFAULT 0",
    "exclusive_right_consolidation_job_id": "INTEGER",
    "exclusive_right_pipeline_status": "VARCHAR(100) DEFAULT 'not_requested'",
    "exclusive_right_pipeline_error": "TEXT",
}


CONTENT_SCREENING_COLUMN_MIGRATIONS = {
    "exclusive_right_score": "FLOAT DEFAULT 0",
    "exclusive_right_candidate_yn": "BOOLEAN DEFAULT 0",
    "matched_exclusive_keywords_json": "TEXT",
}


EXCLUSIVE_RIGHT_COLUMN_MIGRATIONS = {
    "company_id": "INTEGER",
    "company_name_normalized": "VARCHAR(255)",
    "insurance_type": "VARCHAR(50)",
    "subject_core_key": "VARCHAR(1000)",
    "evidence_summary": "TEXT",
    "primary_article_id": "INTEGER",
    "primary_article_title": "TEXT",
    "primary_article_url": "TEXT",
    "article_count": "INTEGER DEFAULT 0",
    "event_status": "VARCHAR(50) DEFAULT 'review'",
    "merged_into_exclusive_right_id": "INTEGER",
    "canonical_exclusive_right_id": "INTEGER",
    "alias_names_json": "TEXT",
    "evidence_text": "TEXT",
}


EXCLUSIVE_RIGHT_OBSERVATION_COLUMN_MIGRATIONS = {
    "source_url": "TEXT",
    "company_id": "INTEGER",
    "company_name_normalized": "VARCHAR(255)",
    "insurance_type": "VARCHAR(50)",
    "raw_subject_name": "VARCHAR(500)",
    "normalized_subject_name_candidate": "VARCHAR(500)",
    "subject_core_key": "VARCHAR(1000)",
    "status_candidate": "VARCHAR(100) DEFAULT 'unknown'",
    "article_title": "TEXT",
    "evidence_text": "TEXT",
}


EXCLUSIVE_RIGHT_OBSOLETE_COLUMNS = {
    "fact_exclusive_use_right": [
        "company_name_raw",
        "company_display_name",
        "exclusive_right_type",
        "exclusive_right_type_code",
        "subject_type",
        "exclusivity_period_text",
        "acquired_year_month_basis",
        "acquired_date_text",
        "related_product_name",
    ],
    "fact_exclusive_use_right_observation": [
        "company_name_raw",
        "company_display_name",
        "exclusive_right_type",
        "exclusive_right_type_code",
        "subject_name",
        "subject_type",
        "exclusivity_period_text",
        "acquired_year_month_basis",
        "acquired_date_text",
        "related_product_name",
        "article_url",
        "company_matching_confidence",
        "company_evidence_text",
    ],
}

EXCLUSIVE_RIGHT_REBUILD_COLUMNS = {
    "fact_exclusive_use_right": [
        ("exclusive_right_id", "INTEGER PRIMARY KEY"),
        ("company_id", "INTEGER"),
        ("company_name_normalized", "VARCHAR(255)"),
        ("insurance_type", "VARCHAR(50)"),
        ("subject_name", "VARCHAR(500) NOT NULL"),
        ("subject_core_key", "VARCHAR(1000)"),
        ("exclusivity_months", "INTEGER"),
        ("acquired_year_month", "VARCHAR(7)"),
        ("feature_summary", "TEXT"),
        ("evidence_summary", "TEXT"),
        ("primary_article_id", "INTEGER"),
        ("primary_article_title", "TEXT"),
        ("primary_article_url", "TEXT"),
        ("article_count", "INTEGER DEFAULT 0"),
        ("confidence_total", "FLOAT DEFAULT 0"),
        ("needs_review", "BOOLEAN DEFAULT 0"),
        ("event_status", "VARCHAR(50) DEFAULT 'active'"),
        ("merged_into_exclusive_right_id", "INTEGER"),
        ("canonical_exclusive_right_id", "INTEGER"),
        ("alias_names_json", "TEXT"),
        ("evidence_text", "TEXT"),
        ("created_at", "DATETIME"),
        ("updated_at", "DATETIME"),
    ],
    "fact_exclusive_use_right_observation": [
        ("observation_id", "INTEGER PRIMARY KEY"),
        ("exclusive_right_id", "INTEGER"),
        ("article_id", "INTEGER NOT NULL"),
        ("source_url", "TEXT"),
        ("company_id", "INTEGER"),
        ("company_name_normalized", "VARCHAR(255)"),
        ("insurance_type", "VARCHAR(50)"),
        ("raw_subject_name", "VARCHAR(500) NOT NULL"),
        ("normalized_subject_name_candidate", "VARCHAR(500)"),
        ("subject_core_key", "VARCHAR(1000)"),
        ("exclusivity_months", "INTEGER"),
        ("acquired_year_month", "VARCHAR(7)"),
        ("feature_summary", "TEXT"),
        ("article_title", "TEXT"),
        ("evidence_text", "TEXT NOT NULL"),
        ("status_candidate", "VARCHAR(100) DEFAULT 'unknown'"),
        ("confidence", "FLOAT DEFAULT 0"),
        ("needs_review", "BOOLEAN DEFAULT 0"),
        ("created_at", "DATETIME"),
        ("updated_at", "DATETIME"),
    ],
}


def upgrade_company_columns(bind=engine) -> None:
    if not bind.url.get_backend_name().startswith("sqlite"):
        return
    with bind.begin() as conn:
        existing = {row[1] for row in conn.execute(text("PRAGMA table_info(dim_company)")).all()}
        for column_name, column_type in COMPANY_COLUMN_MIGRATIONS.items():
            if column_name not in existing:
                conn.execute(text(f"ALTER TABLE dim_company ADD COLUMN {column_name} {column_type}"))
        conn.execute(
            text(
                """
                UPDATE dim_company
                SET insurance_type = COALESCE(insurance_type, insurance_type_default),
                    status_2024_2026 = COALESCE(status_2024_2026, 'active'),
                    include_in_product_news_default = COALESCE(include_in_product_news_default, 'Y')
                """
            )
        )


def upgrade_product_columns(bind=engine) -> None:
    if not bind.url.get_backend_name().startswith("sqlite"):
        return
    with bind.begin() as conn:
        existing = {row[1] for row in conn.execute(text("PRAGMA table_info(dim_product)")).all()}
        for column_name, column_type in PRODUCT_COLUMN_MIGRATIONS.items():
            if column_name not in existing:
                conn.execute(text(f"ALTER TABLE dim_product ADD COLUMN {column_name} {column_type}"))
        conn.execute(
            text(
                """
                UPDATE dim_product
                SET product_status = COALESCE(product_status, 'active'),
                    canonical_product_id = COALESCE(canonical_product_id, product_id),
                    alias_count = COALESCE(alias_count, 0),
                    consolidation_status = COALESCE(consolidation_status, 'pending')
                """
            )
        )


def upgrade_article_columns(bind=engine) -> None:
    if not bind.url.get_backend_name().startswith("sqlite"):
        return
    with bind.begin() as conn:
        existing = {row[1] for row in conn.execute(text("PRAGMA table_info(fact_article)")).all()}
        for column_name, column_type in ARTICLE_COLUMN_MIGRATIONS.items():
            if column_name not in existing:
                conn.execute(text(f"ALTER TABLE fact_article ADD COLUMN {column_name} {column_type}"))


def upgrade_llm_run_columns(bind=engine) -> None:
    if not bind.url.get_backend_name().startswith("sqlite"):
        return
    with bind.begin() as conn:
        existing = {row[1] for row in conn.execute(text("PRAGMA table_info(fact_llm_run)")).all()}
        for column_name, column_type in LLM_RUN_COLUMN_MIGRATIONS.items():
            if column_name not in existing:
                conn.execute(text(f"ALTER TABLE fact_llm_run ADD COLUMN {column_name} {column_type}"))
        conn.execute(
            text(
                """
                UPDATE fact_llm_run
                SET cached_yn = COALESCE(cached_yn, 0),
                    batch_yn = COALESCE(batch_yn, 0),
                    estimated_cost_usd = COALESCE(estimated_cost_usd, cost_estimate),
                    grounded_yn = COALESCE(grounded_yn, 0)
                """
            )
        )


def upgrade_llm_cost_columns(bind=engine) -> None:
    if not bind.url.get_backend_name().startswith("sqlite"):
        return
    with bind.begin() as conn:
        existing = {row[1] for row in conn.execute(text("PRAGMA table_info(fact_llm_cost_log)")).all()}
        for column_name, column_type in LLM_COST_COLUMN_MIGRATIONS.items():
            if column_name not in existing:
                conn.execute(text(f"ALTER TABLE fact_llm_cost_log ADD COLUMN {column_name} {column_type}"))
        conn.execute(
            text(
                """
                UPDATE fact_llm_cost_log
                SET estimate_quality = COALESCE(estimate_quality, 'rough')
                """
            )
        )


def upgrade_llm_queue_columns(bind=engine) -> None:
    if not bind.url.get_backend_name().startswith("sqlite"):
        return
    with bind.begin() as conn:
        existing = {row[1] for row in conn.execute(text("PRAGMA table_info(fact_llm_queue)")).all()}
        for column_name, column_type in LLM_QUEUE_COLUMN_MIGRATIONS.items():
            if column_name not in existing:
                conn.execute(text(f"ALTER TABLE fact_llm_queue ADD COLUMN {column_name} {column_type}"))


def upgrade_llm_batch_job_columns(bind=engine) -> None:
    if not bind.url.get_backend_name().startswith("sqlite"):
        return
    with bind.begin() as conn:
        existing = {row[1] for row in conn.execute(text("PRAGMA table_info(fact_llm_batch_job)")).all()}
        for column_name, column_type in LLM_BATCH_JOB_COLUMN_MIGRATIONS.items():
            if column_name not in existing:
                conn.execute(text(f"ALTER TABLE fact_llm_batch_job ADD COLUMN {column_name} {column_type}"))
        conn.execute(
            text(
                """
                UPDATE fact_llm_batch_job
                SET request_count = COALESCE(request_count, 0),
                    completed_count = COALESCE(completed_count, 0),
                    failed_count = COALESCE(failed_count, 0)
                """
            )
        )


def upgrade_crawl_job_columns(bind=engine) -> None:
    if not bind.url.get_backend_name().startswith("sqlite"):
        return
    with bind.begin() as conn:
        existing = {row[1] for row in conn.execute(text("PRAGMA table_info(fact_crawl_job)")).all()}
        for column_name, column_type in CRAWL_JOB_COLUMN_MIGRATIONS.items():
            if column_name not in existing:
                conn.execute(text(f"ALTER TABLE fact_crawl_job ADD COLUMN {column_name} {column_type}"))
        conn.execute(
            text(
                """
                UPDATE fact_crawl_job
                SET extraction_mode = COALESCE(
                        extraction_mode,
                        CASE WHEN include_llm_extraction = 1 THEN 'enqueue_only' ELSE 'none' END
                    ),
                    include_exclusive_right_pipeline = COALESCE(include_exclusive_right_pipeline, 0),
                    exclusive_right_pipeline_mode = COALESCE(exclusive_right_pipeline_mode, 'batch'),
                    exclusive_right_auto_submit_batch = COALESCE(exclusive_right_auto_submit_batch, 0),
                    exclusive_right_auto_import_when_completed = COALESCE(exclusive_right_auto_import_when_completed, 0),
                    exclusive_right_auto_consolidate = COALESCE(exclusive_right_auto_consolidate, 1),
                    exclusive_right_candidate_count = COALESCE(exclusive_right_candidate_count, 0),
                    exclusive_right_queue_created_count = COALESCE(exclusive_right_queue_created_count, 0),
                    exclusive_right_imported_count = COALESCE(exclusive_right_imported_count, 0),
                    exclusive_right_canonical_count = COALESCE(exclusive_right_canonical_count, 0),
                    exclusive_right_pipeline_status = COALESCE(exclusive_right_pipeline_status, 'not_requested')
                """
            )
        )


def upgrade_content_screening_columns(bind=engine) -> None:
    if not bind.url.get_backend_name().startswith("sqlite"):
        return
    with bind.begin() as conn:
        existing = {row[1] for row in conn.execute(text("PRAGMA table_info(fact_content_screening)")).all()}
        for column_name, column_type in CONTENT_SCREENING_COLUMN_MIGRATIONS.items():
            if column_name not in existing:
                conn.execute(text(f"ALTER TABLE fact_content_screening ADD COLUMN {column_name} {column_type}"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_content_screening_exclusive_candidate ON fact_content_screening (exclusive_right_candidate_yn)"))


def upgrade_exclusive_right_columns(bind=engine) -> None:
    if not bind.url.get_backend_name().startswith("sqlite"):
        return
    with bind.begin() as conn:
        existing = {row[1] for row in conn.execute(text("PRAGMA table_info(fact_exclusive_use_right)")).all()}
        for column_name, column_type in EXCLUSIVE_RIGHT_COLUMN_MIGRATIONS.items():
            if column_name not in existing:
                conn.execute(text(f"ALTER TABLE fact_exclusive_use_right ADD COLUMN {column_name} {column_type}"))
        obs_existing = {row[1] for row in conn.execute(text("PRAGMA table_info(fact_exclusive_use_right_observation)")).all()}
        for column_name, column_type in EXCLUSIVE_RIGHT_OBSERVATION_COLUMN_MIGRATIONS.items():
            if column_name not in obs_existing:
                conn.execute(text(f"ALTER TABLE fact_exclusive_use_right_observation ADD COLUMN {column_name} {column_type}"))
        conn.execute(text("DROP TABLE IF EXISTS dim_exclusive_right_type"))
        refreshed_obs = {row[1] for row in conn.execute(text("PRAGMA table_info(fact_exclusive_use_right_observation)")).all()}
        if "subject_name" in refreshed_obs and "raw_subject_name" in refreshed_obs:
            conn.execute(
                text(
                    """
                    UPDATE fact_exclusive_use_right_observation
                    SET raw_subject_name = COALESCE(raw_subject_name, subject_name),
                        normalized_subject_name_candidate = COALESCE(normalized_subject_name_candidate, subject_name)
                    """
                )
            )
        if "article_url" in refreshed_obs and "source_url" in refreshed_obs:
            conn.execute(
                text(
                    """
                    UPDATE fact_exclusive_use_right_observation
                    SET source_url = COALESCE(source_url, article_url)
                    """
                )
            )
        conn.execute(
            text(
                """
                UPDATE fact_exclusive_use_right
                SET canonical_exclusive_right_id = COALESCE(canonical_exclusive_right_id, exclusive_right_id)
                """
            )
        )
        _drop_obsolete_exclusive_right_columns(conn)
        index_ddls = [
            "CREATE INDEX IF NOT EXISTS ix_exclusive_right_insurance_type ON fact_exclusive_use_right (insurance_type)",
            "CREATE INDEX IF NOT EXISTS ix_exclusive_right_company_id ON fact_exclusive_use_right (company_id)",
            "CREATE INDEX IF NOT EXISTS ix_exclusive_right_company_name ON fact_exclusive_use_right (company_name_normalized)",
            "CREATE INDEX IF NOT EXISTS ix_exclusive_right_acquired_month ON fact_exclusive_use_right (acquired_year_month)",
            "CREATE INDEX IF NOT EXISTS ix_exclusive_right_insurance_month ON fact_exclusive_use_right (insurance_type, acquired_year_month)",
            "CREATE INDEX IF NOT EXISTS ix_exclusive_right_company_month ON fact_exclusive_use_right (company_id, acquired_year_month)",
            "CREATE INDEX IF NOT EXISTS ix_exclusive_right_merged_into ON fact_exclusive_use_right (merged_into_exclusive_right_id)",
            "CREATE INDEX IF NOT EXISTS ix_exclusive_right_canonical ON fact_exclusive_use_right (canonical_exclusive_right_id)",
            "CREATE INDEX IF NOT EXISTS ix_exclusive_obs_company_id ON fact_exclusive_use_right_observation (company_id)",
            "CREATE INDEX IF NOT EXISTS ix_exclusive_obs_insurance_type ON fact_exclusive_use_right_observation (insurance_type)",
            "CREATE INDEX IF NOT EXISTS ix_exclusive_obs_article_id ON fact_exclusive_use_right_observation (article_id)",
            "CREATE INDEX IF NOT EXISTS ix_exclusive_obs_subject_core_key ON fact_exclusive_use_right_observation (subject_core_key)",
        ]
        for ddl in index_ddls:
            conn.execute(text(ddl))


def _drop_obsolete_exclusive_right_columns(conn) -> None:
    for index_name in [
        "ix_exclusive_right_type_month",
        "ix_fact_exclusive_use_right_exclusive_right_type_code",
    ]:
        conn.execute(text(f"DROP INDEX IF EXISTS {index_name}"))
    for table_name, columns in EXCLUSIVE_RIGHT_OBSOLETE_COLUMNS.items():
        existing = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table_name})")).all()}
        for column_name in columns:
            if column_name not in existing:
                continue
            try:
                conn.execute(text(f"ALTER TABLE {table_name} DROP COLUMN {column_name}"))
            except Exception:
                _rebuild_exclusive_right_table(conn, table_name)
                break


def _rebuild_exclusive_right_table(conn, table_name: str) -> None:
    columns = EXCLUSIVE_RIGHT_REBUILD_COLUMNS.get(table_name)
    if not columns:
        return
    existing = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table_name})")).all()}
    if not existing:
        return
    keep_names = [name for name, _ in columns if name in existing]
    temp_name = f"{table_name}_simplified"
    conn.execute(text("PRAGMA foreign_keys=OFF"))
    conn.execute(text(f"DROP TABLE IF EXISTS {temp_name}"))
    column_sql = ", ".join(f"{name} {column_type}" for name, column_type in columns)
    conn.execute(text(f"CREATE TABLE {temp_name} ({column_sql})"))
    if keep_names:
        names_sql = ", ".join(keep_names)
        conn.execute(text(f"INSERT INTO {temp_name} ({names_sql}) SELECT {names_sql} FROM {table_name}"))
    conn.execute(text(f"DROP TABLE {table_name}"))
    conn.execute(text(f"ALTER TABLE {temp_name} RENAME TO {table_name}"))
    conn.execute(text("PRAGMA foreign_keys=ON"))


def create_views(bind=engine) -> None:
    with bind.begin() as conn:
        for view_name in VIEW_SQL:
            conn.execute(text(f"DROP VIEW IF EXISTS {view_name}"))
        for ddl in VIEW_SQL.values():
            conn.execute(text(ddl))


def init_db(bind=engine) -> None:
    Base.metadata.create_all(bind=bind)
    upgrade_company_columns(bind)
    upgrade_product_columns(bind)
    upgrade_article_columns(bind)
    upgrade_llm_run_columns(bind)
    upgrade_llm_cost_columns(bind)
    upgrade_llm_queue_columns(bind)
    upgrade_llm_batch_job_columns(bind)
    upgrade_crawl_job_columns(bind)
    upgrade_content_screening_columns(bind)
    upgrade_exclusive_right_columns(bind)
    create_views(bind)
