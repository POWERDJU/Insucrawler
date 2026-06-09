from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime, time as datetime_time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db.models import FactArticle, FactCrawlJob, FactLLMBatchJob, FactLLMQueue
from app.services.batch_llm_service import BatchLLMService
from app.services.crawl_job_service import CrawlJobService
from app.services.exclusive_right_consolidation_service import ExclusiveRightConsolidationService
from app.services.exclusive_right_service import ExclusiveRightService
from app.services.extract_service import ExtractService
from app.services.full_data_review_service import FullDataReviewService, FullReviewRequestData
from app.services.product_consolidation_service import ProductConsolidationService
from app.services.product_full_list_consolidation_service import ProductFullListConsolidationService
from app.services.product_llm_consolidation_service import ProductLLMConsolidationService
from app.services.qwen_adjudication_service import final_adjudication_disabled
from app.utils.dates import utcnow


ACTIVE_BATCH_STATUSES = {"prepared", "submitted", "running", "provider_completed"}
QUEUE_RUNNING_STATUSES = {"running"}
REFRESH_BATCH_MODEL = "gemini-2.5-flash-lite"


@dataclass(frozen=True)
class ScheduledRefreshConfig:
    enabled: bool
    timezone: str
    days_of_month: tuple[int, ...]
    hour: int
    lookback_days: int
    run_on_startup_catchup: bool
    max_concurrent_jobs: int


class ScheduledRefreshService:
    """Server-side scheduled recent-data refresh and one-batch-at-a-time pipeline."""

    _thread: threading.Thread | None = None
    _stop_event = threading.Event()
    _lock = threading.Lock()

    def __init__(self, *, config: ScheduledRefreshConfig | None = None) -> None:
        self.config = config or self.config_from_env()

    @staticmethod
    def config_from_env() -> ScheduledRefreshConfig:
        days = tuple(
            int(part)
            for part in os.getenv("SCHEDULED_REFRESH_DAYS_OF_MONTH", "1,6,11,16,21,26,31").split(",")
            if part.strip()
        )
        return ScheduledRefreshConfig(
            enabled=_env_bool("SCHEDULED_REFRESH_ENABLED", False),
            timezone=os.getenv("SCHEDULED_REFRESH_TIMEZONE", "Asia/Seoul"),
            days_of_month=days,
            hour=int(os.getenv("SCHEDULED_REFRESH_HOUR", "9")),
            lookback_days=int(os.getenv("SCHEDULED_REFRESH_LOOKBACK_DAYS", "5")),
            run_on_startup_catchup=_env_bool("SCHEDULED_REFRESH_RUN_ON_STARTUP_CATCHUP", False),
            max_concurrent_jobs=int(os.getenv("SCHEDULED_REFRESH_MAX_CONCURRENT_JOBS", "1")),
        )

    def should_run_today(self, now: datetime | None = None) -> bool:
        current = self._local_now(now)
        return self.config.enabled and current.day in self.config.days_of_month and current.hour == self.config.hour

    def compute_refresh_date_range(self, now: datetime | None = None) -> tuple[date, date]:
        current = self._local_now(now).date()
        return current - timedelta(days=self.config.lookback_days), current

    def next_run_at(self, now: datetime | None = None) -> datetime | None:
        if not self.config.enabled:
            return None
        current = self._local_now(now)
        tz = ZoneInfo(self.config.timezone)
        for offset in range(0, 370):
            candidate_date = current.date() + timedelta(days=offset)
            if candidate_date.day not in self.config.days_of_month:
                continue
            candidate = datetime.combine(candidate_date, datetime_time(hour=self.config.hour), tzinfo=tz)
            if candidate >= current:
                return candidate
        return None

    def create_scheduled_refresh_job(self, db: Session, *, now: datetime | None = None) -> FactCrawlJob:
        current = self._local_now(now)
        if self.running_job_count(db) >= self.config.max_concurrent_jobs:
            raise ValueError("Scheduled refresh lock is already held")
        existing = self._same_slot_job(db, current)
        if existing:
            return existing
        start, end = self.compute_refresh_date_range(current)
        job = CrawlJobService().create_crawl_job(
            db,
            job_name=f"scheduled_refresh_{start.isoformat()}_{end.isoformat()}",
            job_type="scheduled_refresh",
            date_from=start.isoformat(),
            date_to=end.isoformat(),
            include_llm_extraction=True,
            extraction_mode="batch",
            include_exclusive_right_pipeline=True,
            exclusive_right_pipeline_mode="batch",
            exclusive_right_auto_submit_batch=False,
            exclusive_right_auto_import_when_completed=False,
            exclusive_right_auto_consolidate=False,
            include_reinsurers=False,
            include_foreign_branches=False,
            pipeline_mode="crawl_parse_postprocess_qwen",
            include_qwen_adjudication=True,
            qwen_priority=True,
            run_postprocess=True,
            run_consolidation=True,
            scheduled_run_at=current,
            scheduled_timezone=self.config.timezone,
            requested_by="scheduled_refresh",
            requested_from="server",
            split_by_month=False,
        )
        return job

    def status(self, db: Session, *, now: datetime | None = None) -> dict[str, Any]:
        latest = (
            db.query(FactCrawlJob)
            .filter(FactCrawlJob.job_type == "scheduled_refresh")
            .order_by(FactCrawlJob.crawl_job_id.desc())
            .first()
        )
        next_run = self.next_run_at(now)
        return {
            "enabled": self.config.enabled,
            "timezone": self.config.timezone,
            "days_of_month": list(self.config.days_of_month),
            "hour": self.config.hour,
            "lookback_days": self.config.lookback_days,
            "run_on_startup_catchup": self.config.run_on_startup_catchup,
            "max_concurrent_jobs": self.config.max_concurrent_jobs,
            "running_job_count": self.running_job_count(db),
            "next_run_at": next_run.isoformat() if next_run else None,
            "latest_job": CrawlJobService.job_to_dict(latest) if latest else None,
        }

    def running_job_count(self, db: Session) -> int:
        return (
            db.query(FactCrawlJob)
            .filter(
                FactCrawlJob.job_type == "scheduled_refresh",
                FactCrawlJob.status.in_(["pending", "running"]),
            )
            .count()
        )

    def run_due_once(self, db: Session, *, now: datetime | None = None) -> dict[str, Any]:
        if not self.should_run_today(now):
            return {"status": "skipped", "reason": "not_due"}
        job = self.create_scheduled_refresh_job(db, now=now)
        return {"status": "created", "crawl_job_id": job.crawl_job_id, "date_from": job.date_from, "date_to": job.date_to}

    def run_scheduled_refresh_job(self, crawl_job_id: int) -> dict[str, Any]:
        CrawlJobService().run_job_by_id(crawl_job_id)
        with SessionLocal() as db:
            return self.run_pipeline_step(db, crawl_job_id=crawl_job_id)

    def run_pipeline_step(self, db: Session, *, crawl_job_id: int) -> dict[str, Any]:
        job = db.get(FactCrawlJob, crawl_job_id)
        if not job:
            raise ValueError(f"Crawl job not found: {crawl_job_id}")
        batch_service = BatchLLMService()
        active = self._latest_active_batch(db, crawl_job_id=crawl_job_id)
        if active:
            active_result = self._handle_active_batch(db, batch_service, active)
            if active_result["status"] != "completed_imported":
                return {"status": "active_batch", "batch": active_result, **self._queue_counts(db, crawl_job_id)}

        product_enqueue = self.enqueue_all_products(db, crawl_job_id=crawl_job_id)
        product_pending = batch_service.pending_batch_eligible_count(db, task_type="extract", crawl_job_id=crawl_job_id)
        if product_pending > 0:
            batch = batch_service.create_from_pending_queue(
                db,
                task_type="extract",
                limit=100,
                submit=True,
                crawl_job_id=crawl_job_id,
                model_name=REFRESH_BATCH_MODEL,
            )
            job.postprocess_status = "product_batch_submitted"
            db.commit()
            return {
                "status": "submitted_product_batch",
                "batch_job_id": batch.llm_batch_job_id,
                "request_count": batch.request_count,
                "product_enqueue": product_enqueue,
                **self._queue_counts(db, crawl_job_id),
            }
        if self._running_queue_count(db, crawl_job_id=crawl_job_id, task_type="extract") > 0:
            return {"status": "waiting_product_queues", **self._queue_counts(db, crawl_job_id)}

        exclusive_enqueue = self.enqueue_all_exclusive(db, crawl_job_id=crawl_job_id)
        exclusive_pending = batch_service.pending_batch_eligible_count(
            db,
            task_type="exclusive_right_extract",
            crawl_job_id=crawl_job_id,
        )
        if exclusive_pending > 0:
            batch = batch_service.create_from_pending_queue(
                db,
                task_type="exclusive_right_extract",
                limit=100,
                submit=True,
                crawl_job_id=crawl_job_id,
                model_name=REFRESH_BATCH_MODEL,
            )
            job.postprocess_status = "exclusive_batch_submitted"
            db.commit()
            return {
                "status": "submitted_exclusive_batch",
                "batch_job_id": batch.llm_batch_job_id,
                "request_count": batch.request_count,
                "exclusive_enqueue": exclusive_enqueue,
                **self._queue_counts(db, crawl_job_id),
            }
        if self._running_queue_count(db, crawl_job_id=crawl_job_id, task_type="exclusive_right_extract") > 0:
            return {"status": "waiting_exclusive_queues", **self._queue_counts(db, crawl_job_id)}

        post = self.run_postprocess_and_qwen(db, crawl_job_id=crawl_job_id)
        return {"status": "postprocessed", "postprocess": post, **self._queue_counts(db, crawl_job_id)}

    def enqueue_all_products(self, db: Session, *, crawl_job_id: int, chunk_size: int = 1000) -> dict[str, int]:
        total = {"processed": 0, "queued": 0, "screened_skip": 0, "cluster_extracted": 0}
        for _ in range(1000):
            result = ExtractService().enqueue_articles_for_crawl_job(
                db,
                crawl_job_id,
                force_batch_eligible=True,
                limit=chunk_size,
            )
            for key in total:
                total[key] += int(result.get(key) or 0)
            db.commit()
            if int(result.get("processed") or 0) == 0:
                break
        return total

    def enqueue_all_exclusive(self, db: Session, *, crawl_job_id: int, chunk_size: int = 1000) -> dict[str, int]:
        total = {"processed": 0, "queued": 0, "skipped_count": 0, "candidate_count": 0}
        for _ in range(1000):
            result = ExclusiveRightService().enqueue_pending_for_crawl_job(
                db,
                crawl_job_id,
                batch_eligible=True,
                limit=chunk_size,
            )
            total["processed"] += int(result.get("processed") or 0)
            total["queued"] += int(result.get("queued") or result.get("queued_count") or 0)
            total["skipped_count"] += int(result.get("skipped_count") or 0)
            total["candidate_count"] = int(result.get("candidate_count") or total["candidate_count"])
            db.commit()
            if int(result.get("processed") or 0) == 0:
                break
        return total

    def run_postprocess_and_qwen(self, db: Session, *, crawl_job_id: int) -> dict[str, Any]:
        job = db.get(FactCrawlJob, crawl_job_id)
        product = ProductConsolidationService().run(
            db,
            mode="rule_only_apply",
            target="all",
            limit=10000,
            trigger_type="scheduled_refresh" if job and job.job_type == "scheduled_refresh" else "manual_range",
            use_llm_for_gray_blocks=False,
        )
        exclusive = ExclusiveRightConsolidationService().run(db, mode="rule_only_apply", crawl_job_id=crawl_job_id)
        product_llm: dict[str, Any] = {}
        qwen: dict[str, Any] = {}
        if job and job.include_qwen_adjudication:
            if _env_bool("PRODUCT_QWEN_CONSOLIDATION_AFTER_POSTPROCESS", True):
                product_llm = ProductFullListConsolidationService(
                    llm_service=ProductLLMConsolidationService(
                        provider_name="qwen",
                        model_name=os.getenv("QWEN_PRODUCT_CONSOLIDATION_MODEL") or os.getenv("QWEN_EXTRACT_MODEL") or "qwen-plus",
                    )
                ).run_article_scope_consolidation(
                    db,
                    mode="apply",
                    crawl_job_id=crawl_job_id,
                    max_blocks=int(os.getenv("PRODUCT_QWEN_CONSOLIDATION_MAX_CALLS", "12")),
                    plan_file=f"data/exports/product_full_list_qwen_merge_plan_crawl_job_{crawl_job_id}.csv",
                    force_enabled=True,
                )
            review = FullDataReviewService().run(
                db,
                FullReviewRequestData(
                    mode="apply",
                    review_scope="all",
                    crawl_job_id=crawl_job_id,
                    include_rule_review=False,
                    include_qwen=True,
                    qwen_priority=bool(job.qwen_priority),
                    max_products=50,
                    max_exclusive=30,
                ),
            )
            job.full_review_job_id = review.get("full_review_job_id")
            job.qwen_review_status = "completed" if review.get("status") == "completed" else "failed"
            qwen = review
        if job:
            job.postprocess_status = "completed"
            job.consolidation_status = "completed"
            job.finished_at = job.finished_at or utcnow()
            db.commit()
        return {"product_consolidation": product, "product_qwen_consolidation": product_llm, "exclusive_consolidation": exclusive, "qwen": qwen}

    @classmethod
    def start_background_loop(cls) -> bool:
        service = cls()
        if not service.config.enabled:
            return False
        with cls._lock:
            if cls._thread and cls._thread.is_alive():
                return True
            cls._stop_event.clear()
            cls._thread = threading.Thread(target=cls._loop, name="scheduled-refresh", daemon=True)
            cls._thread.start()
            return True

    @classmethod
    def stop_background_loop(cls) -> None:
        cls._stop_event.set()

    @classmethod
    def _loop(cls) -> None:
        service = cls()
        while not cls._stop_event.is_set():
            try:
                with SessionLocal() as db:
                    if service.should_run_today():
                        result = service.run_due_once(db)
                        if result.get("status") == "created":
                            service.run_scheduled_refresh_job(int(result["crawl_job_id"]))
                    latest = (
                        db.query(FactCrawlJob)
                        .filter(FactCrawlJob.job_type == "scheduled_refresh", FactCrawlJob.status == "completed")
                        .order_by(FactCrawlJob.crawl_job_id.desc())
                        .first()
                    )
                    if latest and latest.postprocess_status not in {"completed", "failed"}:
                        service.run_pipeline_step(db, crawl_job_id=latest.crawl_job_id)
            except Exception:
                pass
            cls._stop_event.wait(600)

    def _same_slot_job(self, db: Session, current: datetime) -> FactCrawlJob | None:
        start = current.replace(minute=0, second=0, microsecond=0)
        end = start + timedelta(hours=1)
        return (
            db.query(FactCrawlJob)
            .filter(
                FactCrawlJob.job_type == "scheduled_refresh",
                FactCrawlJob.scheduled_run_at >= start,
                FactCrawlJob.scheduled_run_at < end,
            )
            .order_by(FactCrawlJob.crawl_job_id.desc())
            .first()
        )

    def _local_now(self, now: datetime | None) -> datetime:
        tz = ZoneInfo(self.config.timezone)
        if now is None:
            return datetime.now(tz)
        if now.tzinfo is None:
            return now.replace(tzinfo=tz)
        return now.astimezone(tz)

    @staticmethod
    def _latest_active_batch(db: Session, *, crawl_job_id: int) -> FactLLMBatchJob | None:
        return (
            db.query(FactLLMBatchJob)
            .filter(
                FactLLMBatchJob.crawl_job_id == crawl_job_id,
                FactLLMBatchJob.task_type.in_(["extract", "exclusive_right_extract"]),
                FactLLMBatchJob.status.in_(list(ACTIVE_BATCH_STATUSES)),
            )
            .order_by(FactLLMBatchJob.llm_batch_job_id.desc())
            .first()
        )

    @staticmethod
    def _handle_active_batch(db: Session, batch_service: BatchLLMService, job: FactLLMBatchJob) -> dict[str, Any]:
        if job.status in {"submitted", "running"}:
            batch_service.refresh_status(db, job)
            db.commit()
        if job.status == "provider_completed":
            with final_adjudication_disabled():
                imported = batch_service.import_results(db, job)
            db.commit()
            return {
                "status": "completed_imported",
                "llm_batch_job_id": job.llm_batch_job_id,
                "task_type": job.task_type,
                "request_count": job.request_count,
                "imported": imported,
            }
        if job.status == "prepared" and not job.provider_batch_id and int(job.request_count or 0) > 100:
            for item in db.query(FactLLMQueue).filter(FactLLMQueue.llm_batch_job_id == job.llm_batch_job_id).all():
                item.status = "pending"
                item.llm_batch_job_id = None
            job.status = "cancelled"
            job.error_message = "Cancelled oversized local prepared batch over 100 requests."
            db.commit()
            return {
                "status": "cancelled_oversized_prepared",
                "llm_batch_job_id": job.llm_batch_job_id,
                "request_count": job.request_count,
            }
        return {
            "status": job.status,
            "llm_batch_job_id": job.llm_batch_job_id,
            "task_type": job.task_type,
            "request_count": job.request_count,
            "provider_status": job.provider_status,
        }

    @staticmethod
    def _running_queue_count(db: Session, *, crawl_job_id: int, task_type: str) -> int:
        query = (
            db.query(FactLLMQueue)
            .filter(
                FactLLMQueue.task_type == task_type,
                FactLLMQueue.status.in_(list(QUEUE_RUNNING_STATUSES)),
            )
        )
        if task_type == "extract":
            return sum(1 for item in query.all() if BatchLLMService()._queue_matches_crawl_job(db, item, crawl_job_id))
        article_ids = db.query(FactArticle.article_id).filter(FactArticle.crawl_job_id == crawl_job_id)
        return query.filter(FactLLMQueue.target_id.in_(article_ids)).count()

    @staticmethod
    def _queue_counts(db: Session, crawl_job_id: int) -> dict[str, int]:
        batch = BatchLLMService()
        exclusive = ExclusiveRightService().queue_status(db, crawl_job_id=crawl_job_id)
        return {
            "product_pending_batch_eligible_count": batch.pending_batch_eligible_count(
                db,
                task_type="extract",
                crawl_job_id=crawl_job_id,
            ),
            "exclusive_pending_batch_eligible_count": batch.pending_batch_eligible_count(
                db,
                task_type="exclusive_right_extract",
                crawl_job_id=crawl_job_id,
            ),
            "exclusive_candidate_count": int(exclusive.get("exclusive_right_candidate_count") or 0),
            "exclusive_queued_completed_count": int(exclusive.get("queued_completed_count") or 0),
        }


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}
