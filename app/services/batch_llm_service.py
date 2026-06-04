from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Iterable

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db import repository
from app.db.models import FactArticle, FactCrawlJob, FactLLMBatchJob, FactLLMQueue, FactLLMRun, FactProductCandidateCluster
from app.extractors.extraction_schema import validate_extraction_payload
from app.extractors.exclusive_right_schema import validate_exclusive_right_payload
from app.llm.gemini_batch_adapter import GeminiBatchAdapter
from app.llm.prompts import EXCLUSIVE_RIGHT_EXTRACTOR_PROMPT, EXTRACTOR_PROMPT, PROMPT_VERSION
from app.services.extract_service import SCHEMA_VERSION, ExtractService, normalize_extraction_payload
from app.services.exclusive_right_consolidation_service import ExclusiveRightConsolidationService
from app.services.exclusive_right_service import ExclusiveRightService
from app.services.llm_cost_service import LLMCostService
from app.services.product_candidate_cluster_service import ProductCandidateClusterService
from app.services.snippet_service import Snippet, SnippetService
from app.utils.dates import utcnow
from app.utils.hashing import sha256_text


SUCCESS_PROVIDER_STATES = {"JOB_STATE_SUCCEEDED", "BATCH_STATE_SUCCEEDED"}
TERMINAL_PROVIDER_STATES = {
    "JOB_STATE_SUCCEEDED",
    "JOB_STATE_FAILED",
    "JOB_STATE_CANCELLED",
    "JOB_STATE_EXPIRED",
    "BATCH_STATE_SUCCEEDED",
    "BATCH_STATE_FAILED",
    "BATCH_STATE_CANCELLED",
    "BATCH_STATE_EXPIRED",
}


class BatchLLMService:
    def __init__(self, adapter: Any | None = None) -> None:
        self.adapter = adapter
        self.cost_service = LLMCostService()
        self.extract_service = ExtractService()
        self.snippet_service = SnippetService()
        self.cluster_service = ProductCandidateClusterService()

    def create_from_pending_queue(
        self,
        db: Session,
        *,
        task_type: str = "extract",
        provider: str = "gemini",
        model_name: str | None = None,
        limit: int | None = None,
        submit: bool = False,
        crawl_job_id: int | None = None,
        output_dir: str | Path | None = None,
    ) -> FactLLMBatchJob:
        model = model_name or os.getenv("GEMINI_BATCH_MODEL") or os.getenv("GEMINI_EXTRACT_MODEL") or "gemini-2.5-flash"
        max_requests = limit or int(os.getenv("LLM_BATCH_MAX_REQUESTS", "1000"))
        query = (
            db.query(FactLLMQueue)
            .filter(
                FactLLMQueue.task_type == task_type,
                FactLLMQueue.batch_eligible_yn == True,  # noqa: E712
                FactLLMQueue.status == "pending",
            )
            .order_by(FactLLMQueue.priority.desc(), FactLLMQueue.llm_queue_id)
        )
        items: list[FactLLMQueue] = []
        for item in query.limit(max_requests * 5).all():
            if item.provider not in {None, provider} or item.model_name not in {None, model}:
                continue
            if self._queue_is_multi_company_article(db, item):
                item.status = "excluded_multi_company"
                item.last_error = "Excluded from batch queue because target article is multi-company."
                continue
            if crawl_job_id is not None and not self._queue_matches_crawl_job(db, item, crawl_job_id):
                continue
            items.append(item)
            if len(items) >= max_requests:
                break
        job = self.create_batch_input(
            db,
            queue_items=items,
            provider=provider,
            model_name=model,
            task_type=task_type,
            crawl_job_id=crawl_job_id,
            output_dir=output_dir or os.getenv("LLM_BATCH_OUTPUT_DIR", "data/llm_batches"),
        )
        if submit and items:
            self.submit_batch(db, job)
        return job

    def create_batch_input(
        self,
        db: Session,
        *,
        queue_items: Iterable[FactLLMQueue],
        provider: str,
        model_name: str,
        task_type: str,
        crawl_job_id: int | None = None,
        output_dir: str | Path = "data/llm_batches",
    ) -> FactLLMBatchJob:
        items = list(queue_items)
        if crawl_job_id is None:
            crawl_job_ids = {item.crawl_job_id for item in items if item.crawl_job_id is not None}
            crawl_job_id = next(iter(crawl_job_ids)) if len(crawl_job_ids) == 1 else None
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        job = FactLLMBatchJob(
            provider=provider,
            model_name=model_name,
            task_type=task_type,
            crawl_job_id=crawl_job_id,
            status="prepared",
            provider_status="LOCAL_PREPARED",
            request_count=len(items),
        )
        db.add(job)
        db.flush()
        file_path = output_path / f"llm_batch_{job.llm_batch_job_id}.jsonl"
        with file_path.open("w", encoding="utf-8") as f:
            for item in items:
                if self._queue_is_multi_company_article(db, item):
                    item.status = "excluded_multi_company"
                    item.last_error = "Excluded from batch input because target article is multi-company."
                    continue
                input_text = self.build_queue_input_text(db, item)
                request = self._batch_generate_content_request(input_text, task_type=task_type)
                item.crawl_job_id = item.crawl_job_id or crawl_job_id
                custom_id = self._custom_id_for_queue(item, task_type)
                f.write(
                    json.dumps(
                        {
                            "key": str(item.llm_queue_id),
                            "custom_id": custom_id,
                            "metadata": {
                                "queue_id": item.llm_queue_id,
                                "target_type": item.target_type,
                                "target_id": item.target_id,
                                "task_type": task_type,
                                "crawl_job_id": crawl_job_id or item.crawl_job_id,
                            },
                            "request": request,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                item.status = "running"
                item.provider = provider
                item.model_name = model_name
                item.llm_batch_job_id = job.llm_batch_job_id
        job.input_file_path = str(file_path)
        db.flush()
        return job

    def submit_batch(self, db: Session, job: FactLLMBatchJob) -> FactLLMBatchJob:
        if job.provider_batch_id:
            return job
        if job.provider != "gemini":
            raise ValueError(f"Unsupported batch provider: {job.provider}")
        if not job.input_file_path:
            raise ValueError("Batch job has no input_file_path")
        adapter = self.adapter or GeminiBatchAdapter()
        result = adapter.submit_jsonl(
            input_file_path=job.input_file_path,
            model_name=job.model_name,
            display_name=f"insurance-llm-batch-{job.llm_batch_job_id}",
        )
        job.provider_batch_id = result.provider_batch_id
        job.provider_status = result.provider_status
        job.status = "submitted"
        job.submitted_at = utcnow()
        db.flush()
        return job

    def mark_submitted(self, db: Session, job: FactLLMBatchJob) -> None:
        job.status = "submitted"
        job.submitted_at = utcnow()
        db.flush()

    def refresh_status(self, db: Session, job: FactLLMBatchJob) -> FactLLMBatchJob:
        if not job.provider_batch_id:
            return job
        adapter = self.adapter or GeminiBatchAdapter()
        result = adapter.get_status(job.provider_batch_id)
        job.provider_status = result.provider_status
        if result.provider_status in TERMINAL_PROVIDER_STATES:
            if result.provider_status in SUCCESS_PROVIDER_STATES:
                job.status = "provider_completed"
            else:
                job.status = "provider_failed"
            job.completed_at = utcnow()
        else:
            job.status = "running"
        if result.completed_count:
            job.completed_count = result.completed_count
        if result.failed_count:
            job.failed_count = result.failed_count
        if result.error_message:
            job.error_message = result.error_message
        if job.status == "provider_completed" and job.crawl_job_id:
            crawl_job = db.get(FactCrawlJob, job.crawl_job_id)
            if crawl_job and crawl_job.exclusive_right_auto_import_when_completed:
                try:
                    self.import_results(db, job)
                except Exception as exc:
                    job.error_message = str(exc)
                    crawl_job.exclusive_right_pipeline_status = "failed"
                    crawl_job.exclusive_right_pipeline_error = str(exc)
        db.flush()
        return job

    def download_provider_results(self, db: Session, job: FactLLMBatchJob, output_dir: str | Path | None = None) -> Path:
        if not job.provider_batch_id:
            raise ValueError("Batch job has no provider_batch_id")
        adapter = self.adapter or GeminiBatchAdapter()
        status = adapter.get_status(job.provider_batch_id)
        job.provider_status = status.provider_status
        if status.provider_status not in SUCCESS_PROVIDER_STATES:
            raise ValueError(f"Batch job is not succeeded: {status.provider_status}")
        if not status.output_file_name:
            raise ValueError("Provider completed batch has no output file")
        output_path = Path(output_dir or os.getenv("LLM_BATCH_OUTPUT_DIR", "data/llm_batches")) / f"llm_batch_{job.llm_batch_job_id}_output.jsonl"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        adapter.download_results(output_file_name=status.output_file_name, output_file_path=output_path)
        job.output_file_path = str(output_path)
        db.flush()
        return output_path

    def import_results(self, db: Session, job: FactLLMBatchJob, output_file_path: str | Path | None = None) -> dict[str, int]:
        path = Path(output_file_path or job.output_file_path) if (output_file_path or job.output_file_path) else None
        if path is None or not path.exists() or path.is_dir():
            if job.provider_batch_id:
                path = self.download_provider_results(db, job)
            else:
                raise ValueError("Batch output file does not exist")
        completed = 0
        failed = 0
        skipped = 0
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                payload = json.loads(line)
                queue_id = self._line_key(payload)
                queue_item = db.get(FactLLMQueue, queue_id) if queue_id else None
                if not queue_item:
                    failed += 1
                    continue
                if self._existing_completed_run(db, job, queue_item):
                    queue_item.status = "completed"
                    skipped += 1
                    continue
                if self._queue_is_multi_company_article(db, queue_item):
                    queue_item.status = "excluded_multi_company"
                    queue_item.last_error = "Skipped batch import because target article is multi-company."
                    skipped += 1
                    continue
                if payload.get("error"):
                    self._fail_queue(db, queue_item, payload.get("error"))
                    failed += 1
                    continue
                try:
                    response = payload.get("response") or {}
                    raw_text = self._response_text(response)
                    output_json = self._json_from_text(raw_text)
                    if job.task_type == "exclusive_right_extract":
                        input_text = self.build_queue_input_text(db, queue_item)
                        article_id = self._representative_article_id(db, queue_item)
                        exclusive_payload = validate_exclusive_right_payload(output_json)
                        run = repository.create_llm_run(
                            db,
                            article_id=article_id,
                            llm_queue_id=queue_item.llm_queue_id,
                            llm_batch_job_id=job.llm_batch_job_id,
                            task_type=job.task_type,
                            provider=job.provider,
                            model_name=job.model_name,
                            prompt_version=PROMPT_VERSION,
                            schema_version=SCHEMA_VERSION,
                            input_hash=sha256_text(input_text),
                            output_json=json.dumps(output_json, ensure_ascii=False),
                            validation_status="pass",
                            token_input=self._usage_input_tokens(response),
                            token_output=self._usage_output_tokens(response),
                            batch_yn=True,
                        )
                        self.cost_service.record_run(db, run, input_text=input_text)
                        ExclusiveRightService().save_extraction_result(db, article_id, exclusive_payload, llm_run_id=run.llm_run_id)
                        queue_item.status = "completed"
                        queue_item.last_error = None
                        completed += 1
                        continue
                    normalized = normalize_extraction_payload(output_json)
                    extraction = validate_extraction_payload(normalized)
                    input_text = self.build_queue_input_text(db, queue_item)
                    article_id = self._representative_article_id(db, queue_item)
                    run = repository.create_llm_run(
                        db,
                        article_id=article_id,
                        llm_queue_id=queue_item.llm_queue_id,
                        llm_batch_job_id=job.llm_batch_job_id,
                        task_type=job.task_type,
                        provider=job.provider,
                        model_name=job.model_name,
                        prompt_version=PROMPT_VERSION,
                        schema_version=SCHEMA_VERSION,
                        input_hash=sha256_text(input_text),
                        output_json=json.dumps(normalized, ensure_ascii=False),
                        validation_status="pass",
                        token_input=self._usage_input_tokens(response),
                        token_output=self._usage_output_tokens(response),
                        batch_yn=True,
                    )
                    self.cost_service.record_run(db, run, input_text=input_text)
                    product_ids = self.extract_service.save_extraction_result(db, extraction, article_id=article_id, source_text=input_text)
                    self._link_cluster_articles(db, queue_item, product_ids, extraction)
                    queue_item.status = "completed"
                    queue_item.last_error = None
                    self._mark_target_extracted(db, queue_item)
                    completed += 1
                except (ValidationError, ValueError, json.JSONDecodeError, KeyError, TypeError) as exc:
                    self._fail_queue(db, queue_item, str(exc))
                    failed += 1
        job.output_file_path = str(path)
        job.completed_count = completed + skipped
        job.failed_count = failed
        job.status = "completed" if failed == 0 else "completed_with_errors"
        job.provider_status = job.provider_status or "LOCAL_IMPORTED"
        job.completed_at = utcnow()
        if job.task_type == "exclusive_right_extract" and completed:
            crawl_job = db.get(FactCrawlJob, job.crawl_job_id) if job.crawl_job_id else None
            if crawl_job:
                self._update_exclusive_crawl_job_after_import(db, job, crawl_job, completed=completed, failed=failed)
                if crawl_job.exclusive_right_auto_consolidate:
                    ExclusiveRightConsolidationService().run(db, mode="rule_only_apply", crawl_job_id=crawl_job.crawl_job_id)
                    crawl_job.exclusive_right_pipeline_status = "consolidated"
                else:
                    crawl_job.exclusive_right_pipeline_status = "imported"
            else:
                ExclusiveRightConsolidationService().run(db, mode="rule_only_apply")
        db.flush()
        return {"completed": completed, "failed": failed, "skipped": skipped}

    def import_mock_output(self, db: Session, job: FactLLMBatchJob, output_file_path: str | Path) -> dict[str, int]:
        return self.import_results(db, job, output_file_path)

    def list_jobs(self, db: Session, limit: int = 50) -> list[dict[str, Any]]:
        return [self._job_dict(job) for job in db.query(FactLLMBatchJob).order_by(FactLLMBatchJob.llm_batch_job_id.desc()).limit(limit).all()]

    def get_job_detail(self, db: Session, job_id: int) -> dict[str, Any]:
        job = db.get(FactLLMBatchJob, job_id)
        if not job:
            raise ValueError(f"Batch job not found: {job_id}")
        queues = db.query(FactLLMQueue).filter(FactLLMQueue.llm_batch_job_id == job_id).order_by(FactLLMQueue.llm_queue_id).all()
        payload = self._job_dict(job)
        payload["queues"] = [
            {
                "llm_queue_id": item.llm_queue_id,
                "crawl_job_id": item.crawl_job_id,
                "target_type": item.target_type,
                "target_id": item.target_id,
                "task_type": item.task_type,
                "priority": item.priority,
                "status": item.status,
                "last_error": item.last_error,
            }
            for item in queues
        ]
        return payload

    def pending_batch_eligible_count(self, db: Session, task_type: str = "extract", crawl_job_id: int | None = None) -> int:
        query = db.query(FactLLMQueue).filter(
            FactLLMQueue.task_type == task_type,
            FactLLMQueue.batch_eligible_yn == True,  # noqa: E712
            FactLLMQueue.status == "pending",
        )
        if crawl_job_id is None:
            return query.count()
        return sum(1 for item in query.all() if self._queue_matches_crawl_job(db, item, crawl_job_id))

    def build_queue_input_text(self, db: Session, queue_item: FactLLMQueue) -> str:
        if queue_item.target_type == "product_candidate_cluster":
            cluster = db.get(FactProductCandidateCluster, queue_item.target_id)
            if not cluster:
                raise ValueError(f"Cluster not found: {queue_item.target_id}")
            return self.cluster_service.build_cluster_llm_input(db, cluster)
        if queue_item.target_type == "article":
            article = db.get(FactArticle, queue_item.target_id)
            if not article:
                raise ValueError(f"Article not found: {queue_item.target_id}")
            if bool(article.multi_company_article_yn):
                raise ValueError(f"Article is excluded as multi-company: {queue_item.target_id}")
            snippets = self._snippets_for_article(db, article.article_id)
            return self.snippet_service.build_llm_input(
                title=article.title,
                description=article.description,
                source_type=article.source_api,
                article_date=article.pub_date,
                snippets=snippets,
            )
        raise ValueError(f"Unsupported batch queue target_type: {queue_item.target_type}")

    def _queue_is_multi_company_article(self, db: Session, queue_item: FactLLMQueue) -> bool:
        if queue_item.target_type == "article":
            article = db.get(FactArticle, queue_item.target_id)
            return bool(article and article.multi_company_article_yn)
        if queue_item.target_type == "product_candidate_cluster":
            cluster = db.get(FactProductCandidateCluster, queue_item.target_id)
            if not cluster:
                return False
            article_ids = [int(item) for item in json.loads(cluster.source_article_ids_json or "[]")]
            if not article_ids:
                return False
            clean_count = (
                db.query(FactArticle)
                .filter(FactArticle.article_id.in_(article_ids), FactArticle.multi_company_article_yn == False)  # noqa: E712
                .count()
            )
            return clean_count == 0
        return False

    def _batch_generate_content_request(self, input_text: str, task_type: str = "extract") -> dict[str, Any]:
        prompt = EXCLUSIVE_RIGHT_EXTRACTOR_PROMPT if task_type == "exclusive_right_extract" else EXTRACTOR_PROMPT
        return {
            "contents": [{"role": "user", "parts": [{"text": f"{prompt}\n\nINPUT:\n{input_text}"}]}],
            "generation_config": {
                "response_mime_type": "application/json",
                "temperature": 0.0,
            },
        }

    def _snippets_for_article(self, db: Session, article_id: int) -> list[Snippet]:
        from app.db.models import FactArticleSnippet

        rows = db.query(FactArticleSnippet).filter(FactArticleSnippet.article_id == article_id).order_by(FactArticleSnippet.snippet_id).all()
        return [
            Snippet(
                snippet_type=row.snippet_type,
                snippet_text=row.snippet_text,
                sentence_index=row.sentence_index or 0,
                matched_keywords=json.loads(row.matched_keywords_json or "[]"),
            )
            for row in rows
        ]

    def _existing_completed_run(self, db: Session, job: FactLLMBatchJob, queue_item: FactLLMQueue) -> FactLLMRun | None:
        return (
            db.query(FactLLMRun)
            .filter(
                FactLLMRun.llm_batch_job_id == job.llm_batch_job_id,
                FactLLMRun.llm_queue_id == queue_item.llm_queue_id,
                FactLLMRun.batch_yn == True,  # noqa: E712
                FactLLMRun.validation_status == "pass",
            )
            .first()
        )

    def _queue_matches_crawl_job(self, db: Session, queue_item: FactLLMQueue, crawl_job_id: int) -> bool:
        if queue_item.crawl_job_id is not None:
            return queue_item.crawl_job_id == crawl_job_id
        if queue_item.target_type == "article":
            article = db.get(FactArticle, queue_item.target_id)
            return bool(article and article.crawl_job_id == crawl_job_id)
        if queue_item.target_type == "product_candidate_cluster":
            cluster = db.get(FactProductCandidateCluster, queue_item.target_id)
            if not cluster:
                return False
            article_ids = [int(item) for item in json.loads(cluster.source_article_ids_json or "[]")]
            if not article_ids:
                return False
            return (
                db.query(FactArticle)
                .filter(FactArticle.article_id.in_(article_ids), FactArticle.crawl_job_id == crawl_job_id)
                .count()
                > 0
            )
        return False

    def _representative_article_id(self, db: Session, queue_item: FactLLMQueue) -> int | None:
        if queue_item.target_type == "article":
            return queue_item.target_id
        if queue_item.target_type == "product_candidate_cluster":
            cluster = db.get(FactProductCandidateCluster, queue_item.target_id)
            if not cluster:
                return None
            article_ids = json.loads(cluster.source_article_ids_json or "[]")
            return int(article_ids[0]) if article_ids else None
        return None

    def _link_cluster_articles(self, db: Session, queue_item: FactLLMQueue, product_ids: list[int], extraction: Any) -> None:
        if queue_item.target_type != "product_candidate_cluster" or not product_ids:
            return
        cluster = db.get(FactProductCandidateCluster, queue_item.target_id)
        if not cluster:
            return
        article_ids = [int(item) for item in json.loads(cluster.source_article_ids_json or "[]")]
        primary_article_id = article_ids[0] if article_ids else None
        for product_id, product in zip(product_ids, extraction.products):
            for article_id in article_ids:
                if article_id == primary_article_id:
                    continue
                repository.link_product_article(
                    db,
                    product_id,
                    article_id,
                    confidence_total=product.confidence.total(),
                    needs_review=product.needs_human_review,
                    evidence_summary=product.evidence.product_name_evidence,
                )

    def _mark_target_extracted(self, db: Session, queue_item: FactLLMQueue) -> None:
        if queue_item.target_type == "article":
            article = db.get(FactArticle, queue_item.target_id)
            if article:
                article.extraction_status = "extracted"
        elif queue_item.target_type == "product_candidate_cluster":
            cluster = db.get(FactProductCandidateCluster, queue_item.target_id)
            if cluster:
                cluster.llm_status = "extracted"
                for article_id in json.loads(cluster.source_article_ids_json or "[]"):
                    article = db.get(FactArticle, int(article_id))
                    if article and article.extraction_status in {"queued", "failed"}:
                        article.extraction_status = "cluster_extracted"

    @staticmethod
    def _fail_queue(db: Session, queue_item: FactLLMQueue, error: Any) -> None:
        queue_item.status = "failed"
        queue_item.attempts += 1
        queue_item.last_error = json.dumps(error, ensure_ascii=False) if isinstance(error, (dict, list)) else str(error)
        db.flush()

    @staticmethod
    def _custom_id_for_queue(queue_item: FactLLMQueue, task_type: str) -> str:
        if task_type == "exclusive_right_extract" and queue_item.target_type == "article":
            suffix = f":crawl:{queue_item.crawl_job_id}" if queue_item.crawl_job_id else ""
            return f"exclusive_right_extract:queue:{queue_item.llm_queue_id}:article:{queue_item.target_id}{suffix}"
        return f"{task_type}:queue:{queue_item.llm_queue_id}:target:{queue_item.target_type}:{queue_item.target_id}"

    @staticmethod
    def _line_key(payload: dict[str, Any]) -> int | None:
        metadata = payload.get("metadata") or {}
        value = payload.get("key") or metadata.get("key") or metadata.get("queue_id")
        if value is None:
            custom_id = payload.get("custom_id")
            match = re.search(r"(?:^|:)queue:(\d+)(?:$|:)", str(custom_id or ""))
            value = match.group(1) if match else None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _response_text(response: dict[str, Any]) -> str:
        if "text" in response:
            return str(response["text"])
        candidates = response.get("candidates") or []
        parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
        for part in parts:
            if "text" in part:
                return str(part["text"])
        raise ValueError("Batch response has no text")

    @staticmethod
    def _json_from_text(text: str) -> dict[str, Any]:
        cleaned = (text or "").strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            cleaned = cleaned.removeprefix("json").strip()
        return json.loads(cleaned)

    @staticmethod
    def _usage_input_tokens(response: dict[str, Any]) -> int | None:
        usage = response.get("usageMetadata") or response.get("usage_metadata") or {}
        return usage.get("promptTokenCount") or usage.get("prompt_tokens")

    @staticmethod
    def _usage_output_tokens(response: dict[str, Any]) -> int | None:
        usage = response.get("usageMetadata") or response.get("usage_metadata") or {}
        return usage.get("candidatesTokenCount") or usage.get("completion_tokens")

    @staticmethod
    def _update_exclusive_crawl_job_after_import(
        db: Session,
        job: FactLLMBatchJob,
        crawl_job: FactCrawlJob,
        *,
        completed: int,
        failed: int,
    ) -> None:
        status = ExclusiveRightService().queue_status(db, crawl_job_id=crawl_job.crawl_job_id)
        crawl_job.exclusive_right_batch_status = job.status
        crawl_job.exclusive_right_imported_count = int(status.get("observation_count") or 0)
        crawl_job.exclusive_right_canonical_count = int(status.get("canonical_count") or 0)
        crawl_job.exclusive_right_pipeline_error = None if failed == 0 else f"{failed} batch result(s) failed during import"
        if failed:
            crawl_job.exclusive_right_pipeline_status = "failed"
        elif completed:
            crawl_job.exclusive_right_pipeline_status = "imported"

    @staticmethod
    def _job_dict(job: FactLLMBatchJob) -> dict[str, Any]:
        return {
            "llm_batch_job_id": job.llm_batch_job_id,
            "crawl_job_id": job.crawl_job_id,
            "provider": job.provider,
            "model_name": job.model_name,
            "task_type": job.task_type,
            "status": job.status,
            "provider_batch_id": job.provider_batch_id,
            "provider_status": job.provider_status,
            "input_file_path": job.input_file_path,
            "output_file_path": job.output_file_path,
            "request_count": job.request_count,
            "completed_count": job.completed_count,
            "failed_count": job.failed_count,
            "submitted_at": job.submitted_at.isoformat() if job.submitted_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "error_message": job.error_message,
        }
