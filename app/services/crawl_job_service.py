from __future__ import annotations

import calendar
import json
import os
import time
from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import case, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.collectors.base_news_client import NewsItem
from app.collectors.naver_news_client import NaverNewsClient
from app.db.database import SessionLocal
from app.db.models import DimCompany, DimProduct, FactArticle, FactCrawlEventLog, FactCrawlJob, FactCrawlTask
from app.services.company_service import CompanyService
from app.services.crawl_query_generator import (
    COMMON_CRAWL_QUERIES,
    COMPANY_CRAWL_QUERY_TEMPLATES,
    COMPANY_PRODUCT_QUERY_TERMS,
    EXCLUSIVE_RIGHT_COMMON_QUERIES,
    EXCLUSIVE_RIGHT_COMPANY_QUERY_TEMPLATES,
    PRODUCT_GROUP_CRAWL_QUERIES,
    append_unique_query,
)
from app.services.extract_service import ExtractService
from app.services.batch_llm_service import BatchLLMService
from app.services.exclusive_right_consolidation_service import ExclusiveRightConsolidationService
from app.services.exclusive_right_service import ExclusiveRightService
from app.services.multi_company_article_filter_service import MultiCompanyArticleFilterService
from app.services.product_consolidation_service import ProductConsolidationService
from app.services.screening_service import ScreeningService
from app.services.snippet_service import SnippetService
from app.utils.dates import utcnow
from app.utils.hashing import sha256_text

EXTRACTION_MODES = {"none", "screening_only", "enqueue_only", "realtime", "batch"}


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def parse_iso_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def month_ranges(start: date, end: date) -> list[tuple[date, date, int, int]]:
    cursor = date(start.year, start.month, 1)
    ranges: list[tuple[date, date, int, int]] = []
    while cursor <= end:
        last_day = calendar.monthrange(cursor.year, cursor.month)[1]
        month_start = max(start, cursor)
        month_end = min(end, date(cursor.year, cursor.month, last_day))
        ranges.append((month_start, month_end, cursor.year, cursor.month))
        cursor = date(cursor.year + (1 if cursor.month == 12 else 0), 1 if cursor.month == 12 else cursor.month + 1, 1)
    return ranges


def item_in_range(item: NewsItem, start: date, end: date) -> bool:
    if item.pub_date is None:
        return False
    item_date = item.pub_date.date()
    return start <= item_date <= end


def crawl_article_hash(item: NewsItem) -> str:
    basis = (item.original_link or "").strip() or (item.link or "").strip()
    if not basis:
        basis = f"{item.title or ''}\n{item.pub_date.isoformat() if item.pub_date else ''}\n{item.publisher or ''}"
    return sha256_text(basis)


class CrawlJobService:
    def __init__(self, client_factory: Callable[[], Any] | None = None) -> None:
        self.client_factory = client_factory or NaverNewsClient

    def create_test_2026_01(
        self,
        db: Session,
        *,
        include_llm_extraction: bool = False,
        extraction_mode: str | None = None,
        include_exclusive_right_pipeline: bool = False,
        exclusive_right_pipeline_mode: str = "batch",
        exclusive_right_auto_submit_batch: bool = False,
        exclusive_right_auto_import_when_completed: bool = False,
        exclusive_right_auto_consolidate: bool = True,
        exclusive_right_limit: int | None = None,
        include_reinsurers: bool = False,
        include_foreign_branches: bool = False,
        requested_by: str | None = None,
        requested_from: str | None = None,
    ) -> FactCrawlJob:
        return self.create_crawl_job(
            db,
            job_name="test_2026_01",
            job_type="test_2026_01",
            date_from="2026-01-01",
            date_to="2026-01-31",
            include_llm_extraction=include_llm_extraction,
            extraction_mode=extraction_mode,
            include_exclusive_right_pipeline=include_exclusive_right_pipeline,
            exclusive_right_pipeline_mode=exclusive_right_pipeline_mode,
            exclusive_right_auto_submit_batch=exclusive_right_auto_submit_batch,
            exclusive_right_auto_import_when_completed=exclusive_right_auto_import_when_completed,
            exclusive_right_auto_consolidate=exclusive_right_auto_consolidate,
            exclusive_right_limit=exclusive_right_limit,
            include_reinsurers=include_reinsurers,
            include_foreign_branches=include_foreign_branches,
            requested_by=requested_by,
            requested_from=requested_from,
            split_by_month=True,
        )

    def create_backfill_2024_2026_05(
        self,
        db: Session,
        *,
        include_llm_extraction: bool = False,
        extraction_mode: str | None = None,
        include_exclusive_right_pipeline: bool = False,
        exclusive_right_pipeline_mode: str = "batch",
        exclusive_right_auto_submit_batch: bool = False,
        exclusive_right_auto_import_when_completed: bool = False,
        exclusive_right_auto_consolidate: bool = True,
        exclusive_right_limit: int | None = None,
        include_reinsurers: bool = False,
        include_foreign_branches: bool = False,
        requested_by: str | None = None,
        requested_from: str | None = None,
    ) -> FactCrawlJob:
        return self.create_crawl_job(
            db,
            job_name="backfill_2024_2026_05",
            job_type="backfill",
            date_from="2024-01-01",
            date_to="2026-05-31",
            include_llm_extraction=include_llm_extraction,
            extraction_mode=extraction_mode,
            include_exclusive_right_pipeline=include_exclusive_right_pipeline,
            exclusive_right_pipeline_mode=exclusive_right_pipeline_mode,
            exclusive_right_auto_submit_batch=exclusive_right_auto_submit_batch,
            exclusive_right_auto_import_when_completed=exclusive_right_auto_import_when_completed,
            exclusive_right_auto_consolidate=exclusive_right_auto_consolidate,
            exclusive_right_limit=exclusive_right_limit,
            include_reinsurers=include_reinsurers,
            include_foreign_branches=include_foreign_branches,
            requested_by=requested_by,
            requested_from=requested_from,
            split_by_month=True,
        )

    def create_incremental(
        self,
        db: Session,
        *,
        days_back: int = 14,
        include_llm_extraction: bool = False,
        extraction_mode: str | None = None,
        include_exclusive_right_pipeline: bool = False,
        exclusive_right_pipeline_mode: str = "batch",
        exclusive_right_auto_submit_batch: bool = False,
        exclusive_right_auto_import_when_completed: bool = False,
        exclusive_right_auto_consolidate: bool = True,
        exclusive_right_limit: int | None = None,
        include_reinsurers: bool = False,
        include_foreign_branches: bool = False,
        requested_by: str | None = None,
        requested_from: str | None = None,
    ) -> FactCrawlJob:
        today = utcnow().date()
        date_from = today - timedelta(days=days_back - 1)
        return self.create_crawl_job(
            db,
            job_name="weekly_incremental",
            job_type="incremental",
            date_from=date_from.isoformat(),
            date_to=today.isoformat(),
            include_llm_extraction=include_llm_extraction,
            extraction_mode=extraction_mode,
            include_exclusive_right_pipeline=include_exclusive_right_pipeline,
            exclusive_right_pipeline_mode=exclusive_right_pipeline_mode,
            exclusive_right_auto_submit_batch=exclusive_right_auto_submit_batch,
            exclusive_right_auto_import_when_completed=exclusive_right_auto_import_when_completed,
            exclusive_right_auto_consolidate=exclusive_right_auto_consolidate,
            exclusive_right_limit=exclusive_right_limit,
            include_reinsurers=include_reinsurers,
            include_foreign_branches=include_foreign_branches,
            requested_by=requested_by,
            requested_from=requested_from,
            split_by_month=False,
        )

    def create_manual_range(
        self,
        db: Session,
        *,
        date_from: str,
        date_to: str,
        include_llm_extraction: bool = False,
        extraction_mode: str | None = None,
        include_exclusive_right_pipeline: bool = False,
        exclusive_right_pipeline_mode: str = "batch",
        exclusive_right_auto_submit_batch: bool = False,
        exclusive_right_auto_import_when_completed: bool = False,
        exclusive_right_auto_consolidate: bool = True,
        exclusive_right_limit: int | None = None,
        include_reinsurers: bool = False,
        include_foreign_branches: bool = False,
        requested_by: str | None = None,
        requested_from: str | None = None,
    ) -> FactCrawlJob:
        return self.create_crawl_job(
            db,
            job_name=f"manual_range_{date_from}_{date_to}",
            job_type="manual_range",
            date_from=date_from,
            date_to=date_to,
            include_llm_extraction=include_llm_extraction,
            extraction_mode=extraction_mode,
            include_exclusive_right_pipeline=include_exclusive_right_pipeline,
            exclusive_right_pipeline_mode=exclusive_right_pipeline_mode,
            exclusive_right_auto_submit_batch=exclusive_right_auto_submit_batch,
            exclusive_right_auto_import_when_completed=exclusive_right_auto_import_when_completed,
            exclusive_right_auto_consolidate=exclusive_right_auto_consolidate,
            exclusive_right_limit=exclusive_right_limit,
            include_reinsurers=include_reinsurers,
            include_foreign_branches=include_foreign_branches,
            requested_by=requested_by,
            requested_from=requested_from,
            split_by_month=True,
        )

    def create_crawl_job(
        self,
        db: Session,
        *,
        job_name: str,
        job_type: str,
        date_from: str,
        date_to: str,
        include_llm_extraction: bool = False,
        extraction_mode: str | None = None,
        include_exclusive_right_pipeline: bool = False,
        exclusive_right_pipeline_mode: str = "batch",
        exclusive_right_auto_submit_batch: bool = False,
        exclusive_right_auto_import_when_completed: bool = False,
        exclusive_right_auto_consolidate: bool = True,
        exclusive_right_limit: int | None = None,
        include_article_body_fetch: bool = False,
        include_reinsurers: bool = False,
        include_foreign_branches: bool = False,
        requested_by: str | None = None,
        requested_from: str | None = None,
        split_by_month: bool = True,
        use_month_keyword: bool | None = None,
    ) -> FactCrawlJob:
        start_date = parse_iso_date(date_from)
        end_date = parse_iso_date(date_to)
        if end_date < start_date:
            raise ValueError("date_to must be greater than or equal to date_from")
        resolved_extraction_mode = self._resolve_extraction_mode(include_llm_extraction, extraction_mode)
        job = FactCrawlJob(
            job_name=job_name,
            job_type=job_type,
            status="pending",
            date_from=start_date.isoformat(),
            date_to=end_date.isoformat(),
            requested_by=requested_by,
            requested_from=requested_from,
            include_llm_extraction=resolved_extraction_mode not in {"none", "screening_only"},
            extraction_mode=resolved_extraction_mode,
            include_article_body_fetch=include_article_body_fetch,
            include_reinsurers=include_reinsurers,
            include_foreign_branches=include_foreign_branches,
            include_exclusive_right_pipeline=include_exclusive_right_pipeline,
            exclusive_right_pipeline_mode=self._resolve_exclusive_right_mode(include_exclusive_right_pipeline, exclusive_right_pipeline_mode),
            exclusive_right_auto_submit_batch=exclusive_right_auto_submit_batch,
            exclusive_right_auto_import_when_completed=exclusive_right_auto_import_when_completed,
            exclusive_right_auto_consolidate=exclusive_right_auto_consolidate,
            exclusive_right_limit=exclusive_right_limit,
            exclusive_right_pipeline_status="not_requested" if not include_exclusive_right_pipeline else "pending",
        )
        db.add(job)
        db.flush()
        self._log_event(db, job.crawl_job_id, None, "job_created", f"{job_name} job created")
        task_ranges = month_ranges(start_date, end_date) if split_by_month else [(start_date, end_date, None, None)]
        for task_start, task_end, year, month in task_ranges:
            for query in self.generate_queries(
                db,
                year=year,
                month=month,
                include_reinsurers=include_reinsurers,
                include_foreign_branches=include_foreign_branches,
                use_month_keyword=False,
            ):
                db.add(
                    FactCrawlTask(
                        crawl_job_id=job.crawl_job_id,
                        task_name=f"{task_start:%Y-%m-%d}_{task_end:%Y-%m-%d}_{query['query_text']}",
                        status="pending",
                        date_from=task_start.isoformat(),
                        date_to=task_end.isoformat(),
                        year=year,
                        month=month,
                        company_id=query.get("company_id"),
                        company_name=query.get("company_name"),
                        query_group=query["query_group"],
                        query_text=query["query_text"],
                        sort="date" if job_type == "incremental" else query.get("sort", "date"),
                        display=int(os.getenv("NAVER_NEWS_DISPLAY", "100")),
                        start_position=1,
                    )
                )
        db.flush()
        job.total_tasks = db.query(FactCrawlTask).filter(FactCrawlTask.crawl_job_id == job.crawl_job_id).count()
        db.commit()
        return job

    def generate_queries(
        self,
        db: Session,
        *,
        year: int | None = None,
        month: int | None = None,
        include_reinsurers: bool = False,
        include_foreign_branches: bool = False,
        include_changed_companies: bool = True,
        include_short_term_insurers: bool = True,
        use_month_keyword: bool = False,
        max_aliases_per_company: int | None = None,
        max_queries_per_company: int | None = None,
    ) -> list[dict[str, Any]]:
        max_queries = max_queries_per_company or int(os.getenv("MAX_QUERIES_PER_COMPANY_PER_MONTH", "40"))
        queries: list[dict[str, Any]] = []
        seen: set[str] = set()
        for query in COMMON_CRAWL_QUERIES:
            append_unique_query(queries, seen, query_group="common", query_text=query)
        for query in PRODUCT_GROUP_CRAWL_QUERIES:
            append_unique_query(queries, seen, query_group="product_group", query_text=query)
        for query in EXCLUSIVE_RIGHT_COMMON_QUERIES:
            append_unique_query(queries, seen, query_group="exclusive_right_common", query_text=query, query_source="exclusive_right_common")

        companies = CompanyService().list_companies(
            db,
            include_product_news_default_only=True,
            include_reinsurers=include_reinsurers,
            include_foreign_branches=include_foreign_branches,
            include_changed_companies=include_changed_companies,
            include_short_term_insurers=include_short_term_insurers,
        )
        alias_limit = max_aliases_per_company
        if alias_limit is None:
            alias_limit = int(os.getenv("MAX_COMPANY_ALIASES_FOR_QUERY", "3"))
        for company in companies:
            company_count = 0
            terms = [company["company_name_normalized"]]
            aliases = [item.strip() for item in (company.get("alias") or "").split("|") if item.strip()]
            terms.extend(aliases[: max(0, alias_limit)])
            deduped_terms = list(dict.fromkeys(terms))
            for term in deduped_terms:
                for template in EXCLUSIVE_RIGHT_COMPANY_QUERY_TEMPLATES:
                    if company_count >= max_queries:
                        break
                    if append_unique_query(
                        queries,
                        seen,
                        query_group="exclusive_right_company",
                        query_text=template.format(company=term),
                        query_source="exclusive_right_company",
                        company_id=company["company_id"],
                        company_name=company["company_name_normalized"],
                    ):
                        company_count += 1
                if company_count >= max_queries:
                    break
                for template in COMPANY_CRAWL_QUERY_TEMPLATES:
                    if company_count >= max_queries:
                        break
                    if append_unique_query(
                        queries,
                        seen,
                        query_group="company",
                        query_text=template.format(company=term),
                        company_id=company["company_id"],
                        company_name=company["company_name_normalized"],
                    ):
                        company_count += 1
                for product_term in COMPANY_PRODUCT_QUERY_TERMS:
                    if company_count >= max_queries:
                        break
                    if append_unique_query(
                        queries,
                        seen,
                        query_group="company_product_group",
                        query_text=f"{term} {product_term}",
                        company_id=company["company_id"],
                        company_name=company["company_name_normalized"],
                    ):
                        company_count += 1
                if company_count >= max_queries:
                    break
        self._append_product_followup_queries(db, queries, seen)
        return queries

    def _append_product_followup_queries(self, db: Session, queries: list[dict[str, Any]], seen: set[str]) -> None:
        limit = int(os.getenv("CRAWL_MAX_PRODUCT_FOLLOWUP_QUERIES", "100"))
        rows = (
            db.query(DimProduct, DimCompany)
            .outerjoin(DimCompany, DimProduct.company_id == DimCompany.company_id)
            .filter(DimProduct.normalized_product_name.isnot(None))
            .order_by(DimProduct.updated_at.desc(), DimProduct.product_id.desc())
            .limit(limit)
            .all()
        )
        for product, company in rows:
            product_name = (product.normalized_product_name or product.raw_product_name or "").strip()
            if not product_name:
                continue
            append_unique_query(
                queries,
                seen,
                query_group="product_followup",
                query_text=product_name,
                product_id=product.product_id,
                company_id=product.company_id,
                company_name=company.company_name_normalized if company else None,
            )
            if company and company.company_name_normalized:
                append_unique_query(
                    queries,
                    seen,
                    query_group="company_product_followup",
                    query_text=f"{company.company_name_normalized} {product_name}",
                    product_id=product.product_id,
                    company_id=product.company_id,
                    company_name=company.company_name_normalized,
                )

    def run_job_by_id(self, crawl_job_id: int) -> None:
        with SessionLocal() as db:
            job = db.get(FactCrawlJob, crawl_job_id)
            if not job or job.status == "cancelled":
                return
            job.status = "running"
            job.started_at = job.started_at or utcnow()
            self._log_event(db, job.crawl_job_id, None, "job_started", f"{job.job_name} started")
            db.commit()
            try:
                for task in db.query(FactCrawlTask).filter(FactCrawlTask.crawl_job_id == crawl_job_id, FactCrawlTask.status.in_(["pending", "failed"])).order_by(FactCrawlTask.crawl_task_id):
                    db.refresh(job)
                    if job.status == "cancelled":
                        break
                    self.run_task(db, job, task)
                self._sync_job_counts(db, job)
                db.refresh(job)
                if job.status == "cancelled":
                    job.finished_at = utcnow()
                    self._log_event(db, job.crawl_job_id, None, "job_cancelled", f"{job.job_name} cancelled")
                elif job.failed_tasks:
                    job.status = "failed"
                    job.finished_at = utcnow()
                    job.error_message = f"{job.failed_tasks} task(s) failed"
                    self._log_event(db, job.crawl_job_id, None, "job_failed", job.error_message)
                else:
                    job.status = "completed"
                    job.finished_at = utcnow()
                    self._log_event(db, job.crawl_job_id, None, "job_completed", f"{job.job_name} completed")
                db.commit()
                if job.status == "completed" and (job.extraction_mode or "none") != "none":
                    self._run_optional_extraction(db, job)
                if job.status == "completed" and job.include_exclusive_right_pipeline:
                    self._run_exclusive_right_pipeline_after_crawl(db, job)
                if job.status == "completed" and env_bool("PRODUCT_CONSOLIDATION_AUTO_AFTER_CRAWL", True):
                    try:
                        ProductConsolidationService().run(
                            db,
                            mode=os.getenv("PRODUCT_CONSOLIDATION_AUTO_MODE", "rule_only_apply"),
                            target="new_since_last_job",
                            limit=int(os.getenv("PRODUCT_CONSOLIDATION_BATCH_SIZE", "100")),
                            trigger_type="after_crawl",
                            use_llm_for_gray_blocks=False,
                        )
                    except Exception as consolidation_exc:
                        self._log_event(db, job.crawl_job_id, None, "product_consolidation_failed", str(consolidation_exc))
                        db.commit()
            except Exception as exc:
                job.status = "failed"
                job.finished_at = utcnow()
                job.error_message = str(exc)
                self._log_event(db, job.crawl_job_id, None, "job_failed", str(exc))
                db.commit()

    def run_task(self, db: Session, job: FactCrawlJob, task: FactCrawlTask) -> None:
        task.status = "running"
        task.started_at = utcnow()
        task.last_error = None
        self._log_event(db, job.crawl_job_id, task.crawl_task_id, "task_started", task.query_text)
        db.commit()
        client = self.client_factory()
        display = min(max(int(task.display or 100), 1), 100)
        max_start = int(os.getenv("NAVER_NEWS_MAX_START", "1000"))
        sleep_seconds = float(os.getenv("CRAWL_API_SLEEP_SECONDS", "0.2"))
        max_calls_per_job = int(os.getenv("CRAWL_MAX_API_CALLS_PER_JOB", "5000"))
        stop_when_older = env_bool("CRAWL_STOP_WHEN_OLDER_THAN_RANGE", True)
        start_date = parse_iso_date(task.date_from)
        end_date = parse_iso_date(task.date_to)
        try:
            for start_position in range(int(task.start_position or 1), max_start + 1, display):
                self._sync_job_counts(db, job)
                if job.total_api_calls >= max_calls_per_job:
                    raise RuntimeError("CRAWL_MAX_API_CALLS_PER_JOB exceeded")
                items = client.search_page(task.query_text, task.query_group or "crawl", display=display, start=start_position, sort=task.sort or "date")
                task.api_calls += 1
                task.start_position = start_position
                task.items_fetched += len(items)
                self._log_event(
                    db,
                    job.crawl_job_id,
                    task.crawl_task_id,
                    "api_call",
                    f"{task.query_text} start={start_position} items={len(items)}",
                    {"start": start_position, "display": display, "items": len(items)},
                )
                if not items:
                    break
                older_count = 0
                for item in items:
                    if item.pub_date and item.pub_date.date() < start_date:
                        older_count += 1
                    if not item_in_range(item, start_date, end_date):
                        task.articles_out_of_range += 1
                        continue
                    saved = self._save_article(db, item, job, task)
                    if saved:
                        task.articles_saved += 1
                    else:
                        task.articles_duplicated += 1
                db.commit()
                if len(items) < display:
                    break
                if stop_when_older and older_count == len(items):
                    break
                if sleep_seconds > 0:
                    time.sleep(sleep_seconds)
            task.status = "completed"
            task.finished_at = utcnow()
            self._log_event(db, job.crawl_job_id, task.crawl_task_id, "task_completed", task.query_text)
            db.commit()
        except Exception as exc:
            task.status = "failed"
            task.finished_at = utcnow()
            task.last_error = str(exc)
            self._log_event(db, job.crawl_job_id, task.crawl_task_id, "task_failed", str(exc))
            db.commit()
        finally:
            self._sync_job_counts(db, job)
            db.commit()

    def cancel_job(self, db: Session, crawl_job_id: int) -> FactCrawlJob:
        job = db.get(FactCrawlJob, crawl_job_id)
        if not job:
            raise ValueError(f"Crawl job not found: {crawl_job_id}")
        if job.status in {"pending", "running", "paused"}:
            job.status = "cancelled"
            job.finished_at = utcnow()
            self._log_event(db, job.crawl_job_id, None, "job_cancelled", f"{job.job_name} cancellation requested")
            db.commit()
        return job

    def retry_failed(self, db: Session, crawl_job_id: int) -> FactCrawlJob:
        job = db.get(FactCrawlJob, crawl_job_id)
        if not job:
            raise ValueError(f"Crawl job not found: {crawl_job_id}")
        for task in db.query(FactCrawlTask).filter(FactCrawlTask.crawl_job_id == crawl_job_id, FactCrawlTask.status == "failed"):
            task.status = "pending"
            task.last_error = None
            task.started_at = None
            task.finished_at = None
        job.status = "pending"
        job.error_message = None
        self._sync_job_counts(db, job)
        self._log_event(db, job.crawl_job_id, None, "job_retry_failed", f"{job.job_name} failed tasks queued")
        db.commit()
        return job

    def list_jobs(self, db: Session, limit: int = 20) -> list[dict[str, Any]]:
        jobs = db.query(FactCrawlJob).order_by(FactCrawlJob.created_at.desc(), FactCrawlJob.crawl_job_id.desc()).limit(limit).all()
        return [self.job_to_dict(job) for job in jobs]

    def get_job_detail(self, db: Session, crawl_job_id: int) -> dict[str, Any]:
        job = db.get(FactCrawlJob, crawl_job_id)
        if not job:
            raise ValueError(f"Crawl job not found: {crawl_job_id}")
        tasks = db.query(FactCrawlTask).filter(FactCrawlTask.crawl_job_id == crawl_job_id).order_by(FactCrawlTask.crawl_task_id).all()
        events = db.query(FactCrawlEventLog).filter(FactCrawlEventLog.crawl_job_id == crawl_job_id).order_by(FactCrawlEventLog.crawl_event_id.desc()).limit(100).all()
        result = self.job_to_dict(job)
        result["progress"] = (job.completed_tasks / job.total_tasks) if job.total_tasks else 0
        result["tasks"] = [self.task_to_dict(task) for task in tasks]
        result["events"] = [self.event_to_dict(event) for event in events]
        return result

    @staticmethod
    def job_to_dict(job: FactCrawlJob) -> dict[str, Any]:
        return {column.name: getattr(job, column.name) for column in job.__table__.columns}

    @staticmethod
    def task_to_dict(task: FactCrawlTask) -> dict[str, Any]:
        return {column.name: getattr(task, column.name) for column in task.__table__.columns}

    @staticmethod
    def event_to_dict(event: FactCrawlEventLog) -> dict[str, Any]:
        return {column.name: getattr(event, column.name) for column in event.__table__.columns}

    def _save_article(self, db: Session, item: NewsItem, job: FactCrawlJob, task: FactCrawlTask) -> bool:
        content_hash = crawl_article_hash(item)
        if db.query(FactArticle).filter(FactArticle.content_hash == content_hash).first():
            self._log_event(db, job.crawl_job_id, task.crawl_task_id, "duplicate_skipped", item.title, {"url": item.original_link or item.link})
            return False
        article = FactArticle(
            source_api=item.source_api,
            title=item.title,
            description=item.description,
            publisher=item.publisher,
            url=item.link,
            original_url=item.original_link,
            pub_date=item.pub_date,
            collected_at=utcnow(),
            query=item.query,
            query_group=item.query_group,
            crawl_job_id=job.crawl_job_id,
            crawl_task_id=task.crawl_task_id,
            content_hash=content_hash,
            extraction_status="pending",
        )
        db.add(article)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            self._log_event(db, job.crawl_job_id, task.crawl_task_id, "duplicate_skipped", item.title, {"url": item.original_link or item.link})
            return False
        self._log_event(db, job.crawl_job_id, task.crawl_task_id, "article_saved", item.title, {"article_id": article.article_id})
        screening = ScreeningService().screen_article(db, article)
        SnippetService().extract_for_article(db, article)
        multi_company = MultiCompanyArticleFilterService().mark_article(db, article)
        if multi_company.is_multi_company:
            self._log_event(
                db,
                job.crawl_job_id,
                task.crawl_task_id,
                "article_excluded_multi_company",
                item.title,
                {"article_id": article.article_id, "companies": multi_company.company_names},
            )
            return True
        if not screening.is_candidate:
            task.articles_irrelevant += 1
        if not screening.llm_required_yn and env_bool("LLM_SKIP_LOW_RELEVANCE", True):
            article.extraction_status = "screened_skip"
        return True

    def _sync_job_counts(self, db: Session, job: FactCrawlJob) -> None:
        counts = db.query(
            func.count(FactCrawlTask.crawl_task_id),
            func.sum(case((FactCrawlTask.status == "completed", 1), else_=0)),
            func.sum(case((FactCrawlTask.status == "failed", 1), else_=0)),
            func.coalesce(func.sum(FactCrawlTask.api_calls), 0),
            func.coalesce(func.sum(FactCrawlTask.items_fetched), 0),
            func.coalesce(func.sum(FactCrawlTask.articles_saved), 0),
            func.coalesce(func.sum(FactCrawlTask.articles_duplicated), 0),
            func.coalesce(func.sum(FactCrawlTask.articles_out_of_range), 0),
            func.coalesce(func.sum(FactCrawlTask.articles_irrelevant), 0),
        ).filter(FactCrawlTask.crawl_job_id == job.crawl_job_id).one()
        job.total_tasks = int(counts[0] or 0)
        job.completed_tasks = int(counts[1] or 0)
        job.failed_tasks = int(counts[2] or 0)
        job.total_api_calls = int(counts[3] or 0)
        job.total_items_fetched = int(counts[4] or 0)
        job.total_articles_saved = int(counts[5] or 0)
        job.total_articles_duplicated = int(counts[6] or 0)
        job.total_articles_out_of_range = int(counts[7] or 0)
        job.total_articles_irrelevant = int(counts[8] or 0)

    def _run_optional_extraction(self, db: Session, job: FactCrawlJob) -> None:
        try:
            mode = job.extraction_mode or ("realtime" if job.include_llm_extraction else "none")
            pending_count = db.query(FactArticle).filter(FactArticle.crawl_job_id == job.crawl_job_id, FactArticle.extraction_status == "pending").count()
            service = ExtractService()
            if mode == "screening_only":
                for article in db.query(FactArticle).filter(FactArticle.crawl_job_id == job.crawl_job_id, FactArticle.extraction_status == "pending").order_by(FactArticle.article_id).all():
                    ScreeningService().screen_article(db, article)
                self._log_event(db, job.crawl_job_id, None, "screening_completed", f"{pending_count} job articles screened")
            elif mode in {"enqueue_only", "batch"}:
                result = service.enqueue_articles_for_crawl_job(
                    db,
                    job.crawl_job_id,
                    force_batch_eligible=(mode == "batch"),
                )
                self._log_event(
                    db,
                    job.crawl_job_id,
                    None,
                    "llm_queue_created",
                    f"{result['queued']} job articles queued; {result['screened_skip']} skipped",
                    {"mode": mode, **{k: v for k, v in result.items() if k != "results"}},
                )
            elif mode == "realtime":
                result = service.extract_pending_articles_for_crawl_job(db, job.crawl_job_id, limit=pending_count)
                self._log_event(db, job.crawl_job_id, None, "extraction_completed", f"{result['processed']} job articles processed")
            else:
                self._log_event(db, job.crawl_job_id, None, "extraction_skipped", f"Extraction mode is {mode}")
            db.commit()
        except Exception as exc:
            self._log_event(db, job.crawl_job_id, None, "extraction_failed", str(exc))
            db.commit()

    def _run_exclusive_right_pipeline_after_crawl(self, db: Session, job: FactCrawlJob) -> None:
        mode = self._resolve_exclusive_right_mode(True, job.exclusive_right_pipeline_mode or "batch")
        limit = job.exclusive_right_limit or int(os.getenv("EXCLUSIVE_RIGHT_BATCH_LIMIT", "1000"))
        service = ExclusiveRightService()
        try:
            job.exclusive_right_pipeline_status = "running"
            job.exclusive_right_pipeline_error = None
            db.flush()
            if mode == "none":
                job.exclusive_right_pipeline_status = "not_requested"
                db.commit()
                return
            if mode == "screening_only":
                summary = service.screen_candidates_for_crawl_job(db, job.crawl_job_id, limit=limit)
                job.exclusive_right_candidate_count = summary["candidate_count"]
                job.exclusive_right_pipeline_status = "screening_completed"
                self._log_event(db, job.crawl_job_id, None, "exclusive_right_screening_completed", f"{summary['candidate_count']} exclusive-right candidates", summary)
                db.commit()
                return
            if mode in {"enqueue_only", "batch"}:
                summary = service.enqueue_pending_for_crawl_job(
                    db,
                    job.crawl_job_id,
                    batch_eligible=(mode == "batch"),
                    limit=limit,
                )
                queue_status = service.queue_status(db, crawl_job_id=job.crawl_job_id)
                job.exclusive_right_candidate_count = summary["candidate_count"]
                job.exclusive_right_queue_created_count = (
                    int(queue_status.get("queued_pending_count") or 0)
                    + int(queue_status.get("queued_completed_count") or 0)
                    + int(queue_status.get("queued_failed_count") or 0)
                )
                job.exclusive_right_pipeline_status = "queued"
                self._log_event(db, job.crawl_job_id, None, "exclusive_right_queue_created", f"{summary['queued_count']} exclusive-right queues created", summary)
                pending_batch_count = BatchLLMService().pending_batch_eligible_count(db, task_type="exclusive_right_extract", crawl_job_id=job.crawl_job_id)
                if mode == "batch" and pending_batch_count > 0:
                    batch_job = BatchLLMService().create_from_pending_queue(
                        db,
                        task_type="exclusive_right_extract",
                        limit=limit,
                        submit=False,
                        crawl_job_id=job.crawl_job_id,
                    )
                    job.exclusive_right_batch_job_id = batch_job.llm_batch_job_id
                    job.exclusive_right_batch_status = batch_job.status
                    job.exclusive_right_pipeline_status = "batch_created"
                    self._log_event(db, job.crawl_job_id, None, "exclusive_right_batch_created", f"Exclusive-right batch #{batch_job.llm_batch_job_id} created", {"llm_batch_job_id": batch_job.llm_batch_job_id})
                    if job.exclusive_right_auto_submit_batch:
                        BatchLLMService().submit_batch(db, batch_job)
                        job.exclusive_right_batch_status = batch_job.status
                        job.exclusive_right_pipeline_status = "batch_submitted"
                        self._log_event(db, job.crawl_job_id, None, "exclusive_right_batch_submitted", f"Exclusive-right batch #{batch_job.llm_batch_job_id} submitted", {"provider_batch_id": batch_job.provider_batch_id})
                db.commit()
                return
            if mode == "realtime":
                result = service.extract_pending_for_crawl_job(db, job.crawl_job_id, mode="realtime", limit=limit)
                job.exclusive_right_candidate_count = result["candidate_count"]
                job.exclusive_right_imported_count = result.get("saved", 0)
                job.exclusive_right_canonical_count = service.queue_status(db, crawl_job_id=job.crawl_job_id).get("canonical_count", 0)
                job.exclusive_right_pipeline_status = "imported"
                self._log_event(db, job.crawl_job_id, None, "exclusive_right_realtime_completed", f"{result.get('saved', 0)} exclusive-right events saved", result)
                if job.exclusive_right_auto_consolidate:
                    consolidation = ExclusiveRightConsolidationService().run(db, mode="rule_only_apply", crawl_job_id=job.crawl_job_id)
                    job.exclusive_right_pipeline_status = "consolidated"
                    self._log_event(db, job.crawl_job_id, None, "exclusive_right_consolidated", "Exclusive-right consolidation completed", consolidation)
                db.commit()
        except Exception as exc:
            job.exclusive_right_pipeline_status = "failed"
            job.exclusive_right_pipeline_error = str(exc)
            self._log_event(db, job.crawl_job_id, None, "exclusive_right_pipeline_failed", str(exc))
            db.commit()

    @staticmethod
    def _resolve_extraction_mode(include_llm_extraction: bool, extraction_mode: str | None = None) -> str:
        mode = (extraction_mode or "").strip() or None
        if mode is None:
            mode = os.getenv("CRAWL_EXTRACTION_MODE") or ("enqueue_only" if include_llm_extraction else "none")
        elif mode == "none" and include_llm_extraction:
            mode = os.getenv("CRAWL_EXTRACTION_MODE") or "enqueue_only"
        if mode not in EXTRACTION_MODES:
            raise ValueError(f"Unsupported extraction_mode: {mode}")
        if mode == "realtime" and not include_llm_extraction:
            return "none"
        return mode

    @staticmethod
    def _resolve_exclusive_right_mode(include_pipeline: bool, mode_value: str | None = None) -> str:
        if not include_pipeline:
            return "none"
        mode = (mode_value or os.getenv("EXCLUSIVE_RIGHT_EXTRACTION_DEFAULT_MODE") or "enqueue_only").strip()
        if mode not in EXTRACTION_MODES:
            raise ValueError(f"Unsupported exclusive_right_pipeline_mode: {mode}")
        return mode

    def _log_event(
        self,
        db: Session,
        crawl_job_id: int,
        crawl_task_id: int | None,
        event_type: str,
        event_message: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        db.add(
            FactCrawlEventLog(
                crawl_job_id=crawl_job_id,
                crawl_task_id=crawl_task_id,
                event_type=event_type,
                event_message=event_message,
                event_payload_json=json.dumps(payload, ensure_ascii=False) if payload else None,
            )
        )
