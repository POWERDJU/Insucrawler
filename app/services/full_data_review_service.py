from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import (
    DimProduct,
    FactArticle,
    FactExclusiveUseRight,
    FactExclusiveUseRightArticle,
    FactFullReviewJob,
    FactProductArticle,
)
from app.services.exclusive_right_consolidation_service import ExclusiveRightConsolidationService
from app.services.product_consolidation_service import ProductConsolidationService
from app.services.qwen_adjudication_service import QwenAdjudicationService
from app.utils.dates import utcnow


EXCLUDED_PRODUCT_STATUSES = {
    "merged",
    "rejected",
    "rejected_multi_company_only",
    "rejected_ineligible_article_only",
    "rejected_marketing_only",
    "excluded_invalid_industry_product_type",
}
EXCLUDED_EXCLUSIVE_STATUSES = {"merged", "rejected", "rejected_multi_company_only"}


@dataclass(frozen=True)
class FullReviewRequestData:
    mode: str = "dry_run"
    review_scope: str = "all"
    date_from: str | None = None
    date_to: str | None = None
    crawl_job_id: int | None = None
    include_rule_review: bool = True
    include_qwen: bool = True
    qwen_priority: bool = True
    max_products: int = 100
    max_exclusive: int = 50
    qwen_exhaustive: bool = False


class FullDataReviewService:
    """Orchestrate rule review, compact Qwen final review, and artifacts."""

    def __init__(
        self,
        *,
        qwen_service: QwenAdjudicationService | None = None,
        output_dir: str | Path = "data/exports",
        docs_dir: str | Path = "docs",
    ) -> None:
        self.qwen_service = qwen_service or QwenAdjudicationService()
        self.output_dir = Path(output_dir)
        self.docs_dir = Path(docs_dir)

    def run(self, db: Session, request: FullReviewRequestData) -> dict[str, Any]:
        job = FactFullReviewJob(
            status="running",
            mode=request.mode,
            review_scope=request.review_scope,
            date_from=request.date_from,
            date_to=request.date_to,
            crawl_job_id=request.crawl_job_id,
            include_rule_review=request.include_rule_review,
            include_qwen=request.include_qwen,
            qwen_priority=request.qwen_priority,
            max_products=request.max_products,
            max_exclusive=request.max_exclusive,
            started_at=utcnow(),
        )
        db.add(job)
        db.flush()
        return self._execute_job(db, job, qwen_exhaustive=request.qwen_exhaustive)

    def apply_job(
        self,
        db: Session,
        full_review_job_id: int,
        *,
        max_products: int | None = None,
        max_exclusive: int | None = None,
    ) -> dict[str, Any]:
        job = db.get(FactFullReviewJob, full_review_job_id)
        if not job:
            raise ValueError(f"Full review job not found: {full_review_job_id}")
        if job.status == "cancelled":
            raise ValueError("Cancelled review job cannot be applied")
        job.mode = "apply"
        if max_products is not None:
            job.max_products = max_products
        if max_exclusive is not None:
            job.max_exclusive = max_exclusive
        job.status = "running"
        job.started_at = job.started_at or utcnow()
        db.flush()
        return self._execute_job(db, job)

    def cancel_job(self, db: Session, full_review_job_id: int) -> dict[str, Any]:
        job = db.get(FactFullReviewJob, full_review_job_id)
        if not job:
            raise ValueError(f"Full review job not found: {full_review_job_id}")
        if job.status in {"pending", "running"}:
            job.status = "cancelled"
            job.finished_at = utcnow()
            db.commit()
        return self.job_to_dict(job)

    def get_job(self, db: Session, full_review_job_id: int) -> dict[str, Any]:
        job = db.get(FactFullReviewJob, full_review_job_id)
        if not job:
            raise ValueError(f"Full review job not found: {full_review_job_id}")
        return self.job_to_dict(job)

    def _execute_job(self, db: Session, job: FactFullReviewJob, *, qwen_exhaustive: bool = False) -> dict[str, Any]:
        job_id = job.full_review_job_id
        try:
            counts = self._target_counts(
                db,
                date_from=job.date_from,
                date_to=job.date_to,
                crawl_job_id=job.crawl_job_id,
            )
            job.article_count = counts["articles"]
            job.product_candidate_count = counts["products"]
            job.exclusive_candidate_count = counts["exclusive_rights"]

            summary: dict[str, Any] = {
                "full_review_job_id": job.full_review_job_id,
                "mode": job.mode,
                "review_scope": job.review_scope,
                "date_from": job.date_from,
                "date_to": job.date_to,
                "crawl_job_id": job.crawl_job_id,
                "target_counts": counts,
                "qwen_exhaustive": qwen_exhaustive,
                "rule_review": {},
                "qwen": {},
            }
            if job.include_rule_review:
                rule_summary = self._run_rule_review(db, job)
                summary["rule_review"] = rule_summary
                job.rule_reviewed_count = int(rule_summary.get("reviewed_count") or 0)
            if job.include_qwen:
                qwen_summary = self.qwen_service.run_chunk(
                    db,
                    full_review_job_id=job.full_review_job_id,
                    crawl_job_id=job.crawl_job_id,
                    date_from=job.date_from,
                    date_to=job.date_to,
                    apply=job.mode == "apply",
                    limit_products=job.max_products,
                    limit_exclusive=job.max_exclusive,
                    exhaustive=qwen_exhaustive,
                )
                summary["qwen"] = qwen_summary
                self._apply_qwen_summary_to_job(job, qwen_summary)

            job.status = "completed"
            job.finished_at = utcnow()
            summary["status"] = job.status
            summary["finished_at"] = job.finished_at.isoformat() if job.finished_at else None
            paths = self._write_artifacts(job, summary)
            summary["artifacts"] = paths
            job.report_path = paths["report_path"]
            job.summary_json = json.dumps(summary, ensure_ascii=False)
            db.commit()
            return self.job_to_dict(job)
        except Exception as exc:
            db.rollback()
            job = db.get(FactFullReviewJob, job_id)
            if job:
                job.status = "failed"
                job.error_message = str(exc)
                job.finished_at = utcnow()
                db.commit()
                return self.job_to_dict(job)
            raise

    def _run_rule_review(self, db: Session, job: FactFullReviewJob) -> dict[str, Any]:
        apply_mode = job.mode == "apply"
        product_summary: dict[str, Any] = {}
        exclusive_summary: dict[str, Any] = {}
        if job.review_scope in {"all", "products"}:
            product_summary = ProductConsolidationService().run(
                db,
                mode="rule_only_apply" if apply_mode else "dry_run",
                target="all",
                limit=10000,
                trigger_type="full_review",
                use_llm_for_gray_blocks=False,
            )
        if job.review_scope in {"all", "exclusive_rights"}:
            exclusive_summary = ExclusiveRightConsolidationService().run(
                db,
                mode="rule_only_apply" if apply_mode else "dry_run",
                crawl_job_id=job.crawl_job_id,
                date_from=job.date_from,
                date_to=job.date_to,
            )
        return {
            "products": product_summary,
            "exclusive_rights": exclusive_summary,
            "reviewed_count": int(product_summary.get("block_count") or 0) + int(exclusive_summary.get("block_count") or 0),
        }

    def _target_counts(
        self,
        db: Session,
        *,
        date_from: str | None,
        date_to: str | None,
        crawl_job_id: int | None,
    ) -> dict[str, int]:
        article_query = db.query(FactArticle)
        article_query = self._filter_article_query(article_query, date_from=date_from, date_to=date_to, crawl_job_id=crawl_job_id)

        product_query = (
            db.query(func.count(func.distinct(DimProduct.product_id)))
            .join(FactProductArticle, FactProductArticle.product_id == DimProduct.product_id)
            .join(FactArticle, FactArticle.article_id == FactProductArticle.article_id)
            .filter(DimProduct.product_status.notin_(list(EXCLUDED_PRODUCT_STATUSES)))
        )
        product_query = self._filter_article_join_query(product_query, date_from=date_from, date_to=date_to, crawl_job_id=crawl_job_id)

        exclusive_query = (
            db.query(func.count(func.distinct(FactExclusiveUseRight.exclusive_right_id)))
            .join(
                FactExclusiveUseRightArticle,
                FactExclusiveUseRightArticle.exclusive_right_id == FactExclusiveUseRight.exclusive_right_id,
            )
            .join(FactArticle, FactArticle.article_id == FactExclusiveUseRightArticle.article_id)
            .filter(FactExclusiveUseRight.event_status.notin_(list(EXCLUDED_EXCLUSIVE_STATUSES)))
        )
        exclusive_query = self._filter_article_join_query(exclusive_query, date_from=date_from, date_to=date_to, crawl_job_id=crawl_job_id)
        return {
            "articles": int(article_query.count()),
            "products": int(product_query.scalar() or 0),
            "exclusive_rights": int(exclusive_query.scalar() or 0),
        }

    @staticmethod
    def _filter_article_query(query: Any, *, date_from: str | None, date_to: str | None, crawl_job_id: int | None) -> Any:
        if crawl_job_id is not None:
            query = query.filter(FactArticle.crawl_job_id == crawl_job_id)
        if date_from:
            query = query.filter(FactArticle.pub_date >= datetime.fromisoformat(date_from))
        if date_to:
            query = query.filter(FactArticle.pub_date < datetime.fromisoformat(date_to) + timedelta(days=1))
        return query

    @staticmethod
    def _filter_article_join_query(query: Any, *, date_from: str | None, date_to: str | None, crawl_job_id: int | None) -> Any:
        if crawl_job_id is not None:
            query = query.filter(FactArticle.crawl_job_id == crawl_job_id)
        if date_from:
            query = query.filter(FactArticle.pub_date >= datetime.fromisoformat(date_from))
        if date_to:
            query = query.filter(FactArticle.pub_date < datetime.fromisoformat(date_to) + timedelta(days=1))
        return query

    @staticmethod
    def _apply_qwen_summary_to_job(job: FactFullReviewJob, summary: dict[str, Any]) -> None:
        products = summary.get("products") or {}
        exclusive = summary.get("exclusive_rights") or {}
        job.qwen_processed_count = int(products.get("processed") or 0) + int(exclusive.get("processed") or 0)
        job.qwen_provider_called_count = int(products.get("provider_called") or 0) + int(exclusive.get("provider_called") or 0)
        job.qwen_accepted_count = int(products.get("accepted") or 0) + int(exclusive.get("accepted") or 0)
        job.qwen_reviewed_count = int(products.get("reviewed") or 0) + int(exclusive.get("reviewed") or 0)
        job.qwen_rejected_count = int(products.get("rejected") or 0) + int(exclusive.get("rejected") or 0)
        job.qwen_remaining_count = int(products.get("remaining_estimate") or 0) + int(exclusive.get("remaining_estimate") or 0)
        job.applied_count = job.qwen_accepted_count if job.mode == "apply" else 0

    def _write_artifacts(self, job: FactFullReviewJob, summary: dict[str, Any]) -> dict[str, str]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.docs_dir.mkdir(parents=True, exist_ok=True)
        suffix = f"{job.full_review_job_id}"
        plan_path = self.output_dir / f"full_qwen_review_plan_{suffix}.csv"
        conflicts_path = self.output_dir / f"full_qwen_review_conflicts_{suffix}.csv"
        applied_path = self.output_dir / f"full_qwen_review_applied_{suffix}.csv"
        report_path = self.docs_dir / "full-qwen-review-result.md"
        rows = [
            {"metric": key, "value": value}
            for key, value in (summary.get("target_counts") or {}).items()
        ]
        rows.extend(
            [
                {"metric": "qwen_processed_count", "value": job.qwen_processed_count},
                {"metric": "qwen_provider_called_count", "value": job.qwen_provider_called_count},
                {"metric": "qwen_remaining_count", "value": job.qwen_remaining_count},
            ]
        )
        self._write_csv(plan_path, rows)
        self._write_csv(conflicts_path, self._error_rows(summary))
        self._write_csv(applied_path, [{"metric": "applied_count", "value": job.applied_count}])
        report_path.write_text(self._report_markdown(job, summary, plan_path, conflicts_path, applied_path), encoding="utf-8")
        return {
            "plan_csv_path": str(plan_path),
            "conflicts_csv_path": str(conflicts_path),
            "applied_csv_path": str(applied_path),
            "report_path": str(report_path),
        }

    @staticmethod
    def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
        with path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=["metric", "value"])
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

    @staticmethod
    def _error_rows(summary: dict[str, Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        qwen = summary.get("qwen") or {}
        for scope in ("products", "exclusive_rights"):
            for error in (qwen.get(scope) or {}).get("errors", []):
                rows.append({"metric": scope, "value": json.dumps(error, ensure_ascii=False)})
        return rows

    @staticmethod
    def _report_markdown(job: FactFullReviewJob, summary: dict[str, Any], plan_path: Path, conflicts_path: Path, applied_path: Path) -> str:
        return "\n".join(
            [
                "# Full Qwen Review Result",
                "",
                f"- review_job_id: {job.full_review_job_id}",
                f"- status: {job.status}",
                f"- mode: {job.mode}",
                f"- date_from: {job.date_from or 'all'}",
                f"- date_to: {job.date_to or 'all'}",
                f"- crawl_job_id: {job.crawl_job_id or 'all'}",
                f"- article_count: {job.article_count}",
                f"- product_candidate_count: {job.product_candidate_count}",
                f"- exclusive_candidate_count: {job.exclusive_candidate_count}",
                f"- qwen_processed_count: {job.qwen_processed_count}",
                f"- qwen_provider_called_count: {job.qwen_provider_called_count}",
                f"- qwen_remaining_count: {job.qwen_remaining_count}",
                "",
                "## Artifacts",
                "",
                f"- plan: `{plan_path}`",
                f"- conflicts: `{conflicts_path}`",
                f"- applied: `{applied_path}`",
                "",
                "## Raw Summary",
                "",
                "```json",
                json.dumps(summary, ensure_ascii=False, indent=2),
                "```",
                "",
            ]
        )

    @staticmethod
    def job_to_dict(job: FactFullReviewJob) -> dict[str, Any]:
        payload = {column.name: getattr(job, column.name) for column in job.__table__.columns}
        if payload.get("summary_json"):
            try:
                payload["summary"] = json.loads(payload["summary_json"])
            except json.JSONDecodeError:
                payload["summary"] = None
        return payload
