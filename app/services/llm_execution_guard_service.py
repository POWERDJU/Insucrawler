from __future__ import annotations

import os
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import FactArticle, FactContentScreening, FactLLMQueue, FactLLMRun


class LLMExecutionGuardService:
    """Summarize whether runtime LLM cost guards are being respected."""

    def summary(self, db: Session) -> dict[str, Any]:
        article_count = db.query(FactArticle).count()
        priority_counts = dict(
            db.query(FactContentScreening.llm_priority, func.count(FactContentScreening.screening_id))
            .group_by(FactContentScreening.llm_priority)
            .all()
        )
        run_counts = dict(db.query(FactLLMRun.task_type, func.count(FactLLMRun.llm_run_id)).group_by(FactLLMRun.task_type).all())
        total_runs = db.query(FactLLMRun).count()
        cached_runs = db.query(FactLLMRun).filter(FactLLMRun.cached_yn == True).count()  # noqa: E712
        batch_runs = db.query(FactLLMRun).filter(FactLLMRun.batch_yn == True).count()  # noqa: E712
        low_skip_article_ids = [
            int(row[0])
            for row in db.query(FactContentScreening.article_id)
            .filter(FactContentScreening.llm_priority.in_(["low", "skip"]))
            .distinct()
            .all()
        ]
        low_skip_llm_violation_count = 0
        if low_skip_article_ids:
            low_skip_llm_violation_count += (
                db.query(FactLLMRun)
                .filter(FactLLMRun.article_id.in_(low_skip_article_ids), FactLLMRun.task_type.in_(["extract", "verify", "adjudicate"]))
                .count()
            )
            low_skip_llm_violation_count += (
                db.query(FactLLMQueue)
                .filter(
                    FactLLMQueue.target_type == "article",
                    FactLLMQueue.target_id.in_(low_skip_article_ids),
                    FactLLMQueue.task_type.in_(["extract", "verify", "adjudicate"]),
                )
                .count()
            )
        max_input_chars = int(os.getenv("LLM_MAX_INPUT_CHARS", "6000"))
        return {
            "article_count": article_count,
            "screened_high_count": int(priority_counts.get("high", 0) or 0),
            "screened_medium_count": int(priority_counts.get("medium", 0) or 0),
            "screened_low_count": int(priority_counts.get("low", 0) or 0),
            "screened_skip_count": int(priority_counts.get("skip", 0) or 0),
            "llm_queue_count": db.query(FactLLMQueue).count(),
            "batch_eligible_queue_count": db.query(FactLLMQueue)
            .filter(FactLLMQueue.batch_eligible_yn == True, FactLLMQueue.status == "pending")  # noqa: E712
            .count(),
            "cluster_reuse_count": db.query(FactArticle).filter(FactArticle.extraction_status == "cluster_extracted").count(),
            "total_run_count": total_runs,
            "extract_run_count": int(run_counts.get("extract", 0) or 0),
            "verify_run_count": int(run_counts.get("verify", 0) or 0),
            "adjudicate_run_count": int(run_counts.get("adjudicate", 0) or 0),
            "product_consolidation_run_count": int(run_counts.get("product_consolidation", 0) or 0),
            "cached_run_count": cached_runs,
            "batch_run_count": batch_runs,
            "cache_hit_rate": (cached_runs / total_runs) if total_runs else 0,
            "low_skip_llm_violation_count": low_skip_llm_violation_count,
            "article_level_same_product_llm_violation_count": (
                db.query(FactLLMRun)
                .filter(
                    FactLLMRun.task_type == "product_consolidation",
                    (FactLLMRun.article_id.isnot(None)) | (FactLLMRun.manual_ingestion_id.isnot(None)),
                )
                .count()
            ),
            "full_body_prompt_violation_count": (
                db.query(FactLLMRun)
                .filter(FactLLMRun.input_chars.isnot(None), FactLLMRun.input_chars > max_input_chars)
                .count()
            ),
            "verify_only_risky_enabled": os.getenv("LLM_VERIFY_ONLY_RISKY", "true").strip().lower() in {"1", "true", "yes", "y", "on"},
            "snippet_only_enabled": os.getenv("LLM_USE_SNIPPETS_ONLY", "true").strip().lower() in {"1", "true", "yes", "y", "on"},
            "cluster_extraction_enabled": os.getenv("ENABLE_PRODUCT_CLUSTER_EXTRACTION", "true").strip().lower() in {"1", "true", "yes", "y", "on"},
            "product_consolidation_llm_enabled": os.getenv("PRODUCT_CONSOLIDATION_LLM_ENABLED", "false").strip().lower() in {"1", "true", "yes", "y", "on"},
        }
