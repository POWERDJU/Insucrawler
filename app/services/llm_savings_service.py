from __future__ import annotations

import os
from collections import Counter
from datetime import datetime, time
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import (
    FactArticle,
    FactArticleSnippet,
    FactContentScreening,
    FactLLMCostLog,
    FactLLMQueue,
    FactLLMRun,
    FactProductCandidateCluster,
)
from app.services.llm_cost_service import LLMCostService


BASELINE_POLICIES = {
    "all_articles_fulltext_extract_only",
    "all_articles_fulltext_extract_and_verify",
    "candidate_articles_fulltext_extract_only",
    "candidate_articles_fulltext_extract_and_verify",
}


class LLMSavingsService:
    def __init__(self, cost_service: LLMCostService | None = None) -> None:
        self.cost_service = cost_service or LLMCostService()

    def get_savings_summary(
        self,
        db: Session,
        date_from: str | None = None,
        date_to: str | None = None,
        baseline_policy: str = "all_articles_fulltext_extract_and_verify",
        include_breakdown: bool = True,
    ) -> dict[str, Any]:
        if baseline_policy not in BASELINE_POLICIES:
            baseline_policy = "all_articles_fulltext_extract_and_verify"

        articles = self._date_filter(db.query(FactArticle), FactArticle.collected_at, date_from, date_to).all()
        screenings = self._date_filter(db.query(FactContentScreening), FactContentScreening.created_at, date_from, date_to).all()
        cost_logs = self._date_filter(db.query(FactLLMCostLog), FactLLMCostLog.created_at, date_from, date_to).all()
        runs = self._date_filter(db.query(FactLLMRun), FactLLMRun.created_at, date_from, date_to).all()
        clusters = self._date_filter(db.query(FactProductCandidateCluster), FactProductCandidateCluster.created_at, date_from, date_to).all()
        queues = self._date_filter(db.query(FactLLMQueue), FactLLMQueue.created_at, date_from, date_to).all()

        candidate_article_ids = {s.article_id for s in screenings if s.llm_priority in {"high", "medium"} or s.is_candidate}
        baseline_target_articles = articles if baseline_policy.startswith("all_articles") else [a for a in articles if a.article_id in candidate_article_ids]
        baseline = self.estimate_baseline_cost(db, baseline_target_articles, cost_logs, baseline_policy)

        optimized_actual_cost = round(sum(float(row.estimated_cost_usd or 0) for row in cost_logs), 8)
        savings = max(0.0, round(baseline["estimated_cost_usd"] - optimized_actual_cost, 8))
        savings_rate = (savings / baseline["estimated_cost_usd"]) if baseline["estimated_cost_usd"] else 0.0

        counts = self._counts(articles, screenings, queues, runs, clusters, cost_logs)
        tokens = {
            "baseline_input_tokens": baseline["input_tokens"],
            "optimized_input_tokens": sum(int(row.input_tokens or 0) for row in cost_logs),
            "baseline_output_tokens": baseline["output_tokens"],
            "optimized_output_tokens": sum(int(row.output_tokens or 0) for row in cost_logs),
        }
        breakdown = {}
        if include_breakdown:
            breakdown = self._breakdown(
                db=db,
                articles=articles,
                baseline_target_articles=baseline_target_articles,
                screenings=screenings,
                cost_logs=cost_logs,
                runs=runs,
                clusters=clusters,
                baseline=baseline,
                baseline_policy=baseline_policy,
                date_from=date_from,
                date_to=date_to,
            )

        return {
            "date_from": date_from,
            "date_to": date_to,
            "baseline_policy": baseline_policy,
            "estimate_quality": self._combined_quality(cost_logs, baseline.get("estimate_quality")),
            "baseline_estimated_cost_usd": baseline["estimated_cost_usd"],
            "optimized_actual_cost_usd": optimized_actual_cost,
            "estimated_savings_usd": savings,
            "estimated_savings_rate": round(savings_rate, 6),
            "counts": counts,
            "tokens": tokens,
            "breakdown": breakdown,
            "by_model": self._by_model(cost_logs),
            "by_task_type": self._by_task_type(cost_logs),
        }

    def estimate_baseline_cost(
        self,
        db: Session,
        articles: list[FactArticle],
        actual_cost_logs: list[FactLLMCostLog],
        baseline_policy: str,
    ) -> dict[str, Any]:
        fulltext_input_tokens = sum(self._article_fulltext_tokens(article) for article in articles)
        extract_output_tokens = self._average_output_tokens(actual_cost_logs, "extract", int(os.getenv("DEFAULT_EXTRACT_OUTPUT_TOKENS", "1200")))
        verify_output_tokens = self._average_output_tokens(actual_cost_logs, "verify", int(os.getenv("DEFAULT_VERIFY_OUTPUT_TOKENS", "800")))
        extract_count = len(articles)
        verify_count = len(articles) if baseline_policy.endswith("and_verify") else 0
        extract_provider, extract_model = self._model_for_task(actual_cost_logs, "extract")
        verify_provider, verify_model = self._model_for_task(actual_cost_logs, "verify", fallback=(extract_provider, extract_model))

        extract_cost, extract_quality = self.cost_service.estimate_with_quality(
            provider=extract_provider,
            model_name=extract_model,
            input_tokens=fulltext_input_tokens,
            output_tokens=extract_count * extract_output_tokens,
        )
        verify_cost, verify_quality = self.cost_service.estimate_with_quality(
            provider=verify_provider,
            model_name=verify_model,
            input_tokens=fulltext_input_tokens if verify_count else 0,
            output_tokens=verify_count * verify_output_tokens,
        )
        quality = "missing_price" if "missing_price" in {extract_quality, verify_quality} else "rough"
        return {
            "estimated_cost_usd": round(extract_cost + verify_cost, 8),
            "input_tokens": fulltext_input_tokens * (1 + (1 if verify_count else 0)),
            "output_tokens": extract_count * extract_output_tokens + verify_count * verify_output_tokens,
            "extract_count": extract_count,
            "verify_count": verify_count,
            "extract_provider": extract_provider,
            "extract_model": extract_model,
            "verify_provider": verify_provider,
            "verify_model": verify_model,
            "avg_extract_output_tokens": extract_output_tokens,
            "avg_verify_output_tokens": verify_output_tokens,
            "estimate_quality": quality,
        }

    def estimate_screening_savings(self, baseline_target_count: int, llm_target_count: int, average_unit_cost: float) -> float:
        return round(max(0, baseline_target_count - llm_target_count) * average_unit_cost, 8)

    def estimate_snippet_savings(self, baseline_tokens: int, optimized_tokens: int, provider: str, model_name: str) -> float:
        saved_tokens = max(0, baseline_tokens - optimized_tokens)
        cost, _ = self.cost_service.estimate_with_quality(provider=provider, model_name=model_name, input_tokens=saved_tokens, output_tokens=0)
        return cost

    def estimate_cluster_savings(self, candidate_article_count: int, cluster_count: int, average_extract_cost: float) -> float:
        return round(max(0, candidate_article_count - cluster_count) * average_extract_cost, 8)

    def estimate_selective_verification_savings(self, baseline_verify_count: int, actual_verify_count: int, average_verify_cost: float) -> float:
        return round(max(0, baseline_verify_count - actual_verify_count) * average_verify_cost, 8)

    def estimate_cache_savings(self, cost_logs: list[FactLLMCostLog]) -> float:
        total = 0.0
        for row in cost_logs:
            if not row.cached_tokens:
                continue
            cost, _ = self.cost_service.estimate_with_quality(
                provider=row.provider,
                model_name=row.model_name,
                input_tokens=int(row.cached_tokens or 0),
                output_tokens=int(row.output_tokens or 0),
                batch_yn=False,
            )
            total += cost
        return round(total, 8)

    def estimate_batch_savings(self, cost_logs: list[FactLLMCostLog]) -> float:
        total = 0.0
        for row in cost_logs:
            if not row.batch_yn:
                continue
            full_cost, _ = self.cost_service.estimate_with_quality(
                provider=row.provider,
                model_name=row.model_name,
                input_tokens=row.input_tokens,
                output_tokens=row.output_tokens,
                cached_tokens=row.cached_tokens,
                batch_yn=False,
            )
            total += max(0.0, full_cost - float(row.estimated_cost_usd or 0))
        return round(total, 8)

    def _breakdown(
        self,
        *,
        db: Session,
        articles: list[FactArticle],
        baseline_target_articles: list[FactArticle],
        screenings: list[FactContentScreening],
        cost_logs: list[FactLLMCostLog],
        runs: list[FactLLMRun],
        clusters: list[FactProductCandidateCluster],
        baseline: dict[str, Any],
        baseline_policy: str,
        date_from: str | None,
        date_to: str | None,
    ) -> dict[str, float]:
        extract_logs = [row for row in cost_logs if row.task_type == "extract"]
        verify_logs = [row for row in cost_logs if row.task_type == "verify"]
        avg_extract_cost = (sum(float(row.estimated_cost_usd or 0) for row in extract_logs) / len(extract_logs)) if extract_logs else 0.0
        avg_verify_cost = (sum(float(row.estimated_cost_usd or 0) for row in verify_logs) / len(verify_logs)) if verify_logs else 0.0
        avg_extract_cost = avg_extract_cost or self._unit_extract_cost(baseline)
        avg_verify_cost = avg_verify_cost or self._unit_verify_cost(baseline)

        llm_candidate_count = len({s.article_id for s in screenings if s.llm_priority in {"high", "medium"} or s.llm_required_yn})
        candidate_article_count = len({s.article_id for s in screenings if s.llm_priority in {"high", "medium"} or s.is_candidate})
        actual_verify_count = len([run for run in runs if run.task_type == "verify"])
        baseline_verify_count = baseline["verify_count"]
        snippet_tokens = self._snippet_tokens(db, [a.article_id for a in baseline_target_articles], date_from, date_to)
        optimized_input_tokens = sum(int(row.input_tokens or 0) for row in cost_logs if row.task_type == "extract") or snippet_tokens
        fulltext_tokens_for_targets = sum(self._article_fulltext_tokens(article) for article in baseline_target_articles)

        return {
            "screening_saved_usd": self.estimate_screening_savings(
                len(articles) if baseline_policy.startswith("all_articles") else len(baseline_target_articles),
                llm_candidate_count,
                avg_extract_cost + (avg_verify_cost if baseline_verify_count else 0.0),
            ),
            "snippet_saved_usd": self.estimate_snippet_savings(fulltext_tokens_for_targets, optimized_input_tokens, baseline["extract_provider"], baseline["extract_model"]),
            "cluster_saved_usd": self.estimate_cluster_savings(candidate_article_count, len(clusters), avg_extract_cost),
            "selective_verification_saved_usd": self.estimate_selective_verification_savings(baseline_verify_count, actual_verify_count, avg_verify_cost),
            "cache_saved_usd": self.estimate_cache_savings(cost_logs),
            "batch_saved_usd": self.estimate_batch_savings(cost_logs),
        }

    def _counts(
        self,
        articles: list[FactArticle],
        screenings: list[FactContentScreening],
        queues: list[FactLLMQueue],
        runs: list[FactLLMRun],
        clusters: list[FactProductCandidateCluster],
        cost_logs: list[FactLLMCostLog],
    ) -> dict[str, int]:
        priority_counts = Counter(s.llm_priority or "skip" for s in screenings)
        return {
            "article_count": len(articles),
            "screened_high_count": priority_counts.get("high", 0),
            "screened_medium_count": priority_counts.get("medium", 0),
            "screened_low_count": priority_counts.get("low", 0),
            "screened_skip_count": priority_counts.get("skip", 0),
            "llm_queue_count": len(queues),
            "llm_run_count": len(runs),
            "extract_run_count": sum(1 for row in runs if row.task_type == "extract"),
            "verify_run_count": sum(1 for row in runs if row.task_type == "verify"),
            "adjudicate_run_count": sum(1 for row in runs if row.task_type == "adjudicate"),
            "cluster_count": len(clusters),
            "cache_hit_count": sum(1 for row in runs if row.cached_yn),
            "batch_run_count": sum(1 for row in cost_logs if row.batch_yn),
        }

    def _article_fulltext_tokens(self, article: FactArticle) -> int:
        text = " ".join(part for part in [getattr(article, "full_text", None), getattr(article, "cleaned_content", None)] if part)
        if not text.strip():
            text = " ".join(part for part in [article.title, article.description] if part)
        return self.cost_service.rough_token_count_for_korean(text)

    def _snippet_tokens(self, db: Session, article_ids: list[int], date_from: str | None, date_to: str | None) -> int:
        if not article_ids:
            return 0
        query = db.query(FactArticleSnippet).filter(FactArticleSnippet.article_id.in_(article_ids))
        query = self._date_filter(query, FactArticleSnippet.created_at, date_from, date_to)
        return sum(self.cost_service.rough_token_count_for_korean(row.snippet_text or "") for row in query.all())

    @staticmethod
    def _average_output_tokens(rows: list[FactLLMCostLog], task_type: str, fallback: int) -> int:
        values = [int(row.output_tokens or 0) for row in rows if row.task_type == task_type and row.output_tokens]
        return round(sum(values) / len(values)) if values else fallback

    @staticmethod
    def _model_for_task(rows: list[FactLLMCostLog], task_type: str, fallback: tuple[str, str] = ("gemini", "default")) -> tuple[str, str]:
        for row in rows:
            if row.task_type == task_type and row.provider and row.model_name:
                return row.provider, row.model_name
        return fallback

    @staticmethod
    def _unit_extract_cost(baseline: dict[str, Any]) -> float:
        count = baseline.get("extract_count") or 0
        if not count:
            return 0.0
        return round(baseline["estimated_cost_usd"] / count, 8)

    @staticmethod
    def _unit_verify_cost(baseline: dict[str, Any]) -> float:
        count = baseline.get("verify_count") or 0
        if not count:
            return 0.0
        return round(baseline["estimated_cost_usd"] / (baseline.get("extract_count", 0) + count), 8)

    @staticmethod
    def _by_model(rows: list[FactLLMCostLog]) -> list[dict[str, Any]]:
        grouped: dict[tuple[str, str], dict[str, Any]] = {}
        for row in rows:
            key = (row.provider, row.model_name)
            grouped.setdefault(key, {"estimated_cost_usd": 0.0, "count": 0})
            grouped[key]["estimated_cost_usd"] += float(row.estimated_cost_usd or 0)
            grouped[key]["count"] += 1
        return [
            {"provider": provider, "model_name": model, "estimated_cost_usd": round(value["estimated_cost_usd"], 8), "count": value["count"]}
            for (provider, model), value in sorted(grouped.items())
        ]

    @staticmethod
    def _by_task_type(rows: list[FactLLMCostLog]) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = {}
        for row in rows:
            grouped.setdefault(row.task_type, {"estimated_cost_usd": 0.0, "count": 0})
            grouped[row.task_type]["estimated_cost_usd"] += float(row.estimated_cost_usd or 0)
            grouped[row.task_type]["count"] += 1
        return [
            {"task_type": task, "estimated_cost_usd": round(value["estimated_cost_usd"], 8), "count": value["count"]}
            for task, value in sorted(grouped.items())
        ]

    @staticmethod
    def _combined_quality(rows: list[FactLLMCostLog], baseline_quality: str | None) -> str:
        qualities = [baseline_quality] if baseline_quality else []
        qualities.extend(getattr(row, "estimate_quality", None) for row in rows)
        if "missing_price" in qualities:
            return "missing_price"
        if qualities and all(q == "actual_tokens" for q in qualities if q):
            return "actual_tokens"
        if any(q in {"actual_tokens", "mixed"} for q in qualities if q):
            return "mixed"
        return "rough"

    @staticmethod
    def _date_filter(query: Any, column: Any, date_from: str | None, date_to: str | None) -> Any:
        if date_from:
            query = query.filter(column >= LLMSavingsService._parse_start(date_from))
        if date_to:
            query = query.filter(column <= LLMSavingsService._parse_end(date_to))
        return query

    @staticmethod
    def _parse_start(value: str) -> datetime | str:
        try:
            return datetime.combine(datetime.fromisoformat(value[:10]).date(), time.min)
        except ValueError:
            return value

    @staticmethod
    def _parse_end(value: str) -> datetime | str:
        try:
            return datetime.combine(datetime.fromisoformat(value[:10]).date(), time.max)
        except ValueError:
            return value
