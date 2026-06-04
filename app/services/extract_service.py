from __future__ import annotations

import json
import os
import re
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.classifiers.product_type_classifier import ProductTypeClassifier
from app.db import repository
from app.db.models import DimProduct, FactArticle, FactExtractionRawJson, FactManualIngestion
from app.extractors.extraction_schema import (
    ExtractionResult,
    VerificationResult,
    extraction_save_issues,
    validate_extraction_payload,
    validate_verification_payload,
)
from app.extractors.product_launch_candidate import is_negative_product_name
from app.extractors.product_name_reconciliation import reconcile_extraction
from app.extractors.verifier import summarize_verification
from app.llm.prompts import PROMPT_VERSION
from app.llm.base import LLMResponse
from app.llm.router import LLMRouter
from app.llm.schemas import extraction_json_schema, verification_json_schema
from app.services.llm_cache_service import LLMCacheService
from app.services.llm_cost_service import LLMCostService
from app.services.llm_queue_service import LLMQueueService
from app.services.product_candidate_cluster_service import ProductCandidateClusterService
from app.services.product_canonicalization_service import ProductCanonicalizationService, product_core_key_for_keyword
from app.services.screening_service import ScreeningResult, ScreeningService
from app.services.snippet_service import SnippetService
from app.utils.hashing import sha256_text
from app.normalizers.product_name_normalizer import validate_product_name_before_save


SCHEMA_VERSION = "2026-05-26-v1"
VERIFICATION_VERDICTS = {"supported", "unsupported", "inferred", "incorrect", "ambiguous"}


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


class ExtractService:
    def __init__(self, router: LLMRouter | None = None) -> None:
        self.router = router or LLMRouter()
        self.screening_service = ScreeningService()
        self.snippet_service = SnippetService()
        self.cluster_service = ProductCandidateClusterService()
        self.canonicalization_service = ProductCanonicalizationService()
        self.queue_service = LLMQueueService()
        self.cache_service = LLMCacheService()
        self.cost_service = LLMCostService()

    def extract_article(self, db: Session, article_id: int) -> dict[str, Any]:
        article = db.get(FactArticle, article_id)
        if not article:
            raise ValueError(f"Article not found: {article_id}")
        if bool(article.multi_company_article_yn):
            article.extraction_status = "excluded_multi_company"
            article.extraction_exclusion_reason = "multiple insurer companies detected in article"
            db.commit()
            return {"status": "excluded_multi_company", "article_id": article_id, "product_ids": []}
        screening = self.screening_service.screen_article(db, article)
        if not screening.llm_required_yn and env_bool("LLM_SKIP_LOW_RELEVANCE", True):
            article.extraction_status = "screened_skip"
            db.commit()
            return {
                "status": "screened_skip",
                "article_id": article_id,
                "screening_score": screening.rule_relevance_score,
                "llm_priority": screening.llm_priority,
                "product_ids": [],
            }
        snippets = self.snippet_service.extract_for_article(db, article)
        cluster = None
        queue_item = None
        if env_bool("ENABLE_PRODUCT_CLUSTER_EXTRACTION", True):
            cluster = self.cluster_service.upsert_for_article(db, article, screening, snippets)
        if cluster and cluster.llm_status == "extracted":
            product_ids = self.cluster_service.link_article_to_existing_products(
                db,
                cluster,
                article,
                confidence_total=screening.rule_relevance_score,
            )
            article.extraction_status = "cluster_extracted"
            db.commit()
            return {
                "status": "cluster_extracted",
                "article_id": article_id,
                "candidate_cluster_id": cluster.candidate_cluster_id,
                "product_ids": product_ids,
            }
        target_type = "product_candidate_cluster" if cluster else "article"
        target_id = cluster.candidate_cluster_id if cluster else article.article_id
        queue_item = self.queue_service.enqueue(
            db,
            target_type=target_type,
            target_id=target_id,
            task_type="extract",
            priority=screening.llm_priority,
            batch_eligible_yn=bool(cluster),
        )
        input_text = self._llm_input_for_article(db, article, screening, snippets, cluster)
        # Release SQLite write locks before the comparatively slow provider call.
        db.commit()
        try:
            result = self._run_and_save(db, input_text=input_text, article_id=article_id, screening=screening)
            if cluster:
                cluster.llm_status = "extracted" if result.get("status") == "saved" else "failed"
            self.queue_service.complete(db, queue_item)
            db.commit()
            return result
        except Exception as exc:
            if cluster:
                cluster.llm_status = "failed"
            self.queue_service.fail(db, queue_item, str(exc))
            db.commit()
            raise

    def extract_pending_articles(self, db: Session, limit: int = 20) -> dict[str, Any]:
        articles = db.query(FactArticle).filter(FactArticle.extraction_status == "pending").limit(limit).all()
        results = []
        for article in articles:
            results.append(self.extract_article(db, article.article_id))
        return {"processed": len(results), "results": results}

    def extract_pending_articles_for_crawl_job(self, db: Session, crawl_job_id: int, limit: int | None = None) -> dict[str, Any]:
        query = (
            db.query(FactArticle)
            .filter(FactArticle.crawl_job_id == crawl_job_id, FactArticle.extraction_status == "pending")
            .order_by(FactArticle.article_id)
        )
        if limit is not None:
            query = query.limit(limit)
        results = []
        for article in query.all():
            results.append(self.extract_article(db, article.article_id))
        return {"processed": len(results), "results": results}

    def enqueue_article_extraction(self, db: Session, article_id: int, *, force_batch_eligible: bool = False) -> dict[str, Any]:
        article = db.get(FactArticle, article_id)
        if not article:
            raise ValueError(f"Article not found: {article_id}")
        if bool(article.multi_company_article_yn):
            article.extraction_status = "excluded_multi_company"
            article.extraction_exclusion_reason = "multiple insurer companies detected in article"
            db.flush()
            return {
                "status": "excluded_multi_company",
                "article_id": article_id,
                "llm_queue_id": None,
            }
        screening = self.screening_service.screen_article(db, article)
        if not screening.llm_required_yn and env_bool("LLM_SKIP_LOW_RELEVANCE", True):
            article.extraction_status = "screened_skip"
            db.flush()
            return {
                "status": "screened_skip",
                "article_id": article_id,
                "screening_score": screening.rule_relevance_score,
                "llm_priority": screening.llm_priority,
                "llm_queue_id": None,
            }
        snippets = self.snippet_service.extract_for_article(db, article)
        cluster = None
        if env_bool("ENABLE_PRODUCT_CLUSTER_EXTRACTION", True):
            cluster = self.cluster_service.upsert_for_article(db, article, screening, snippets)
        if cluster and cluster.llm_status == "extracted":
            product_ids = self.cluster_service.link_article_to_existing_products(
                db,
                cluster,
                article,
                confidence_total=screening.rule_relevance_score,
            )
            article.extraction_status = "cluster_extracted"
            db.flush()
            return {
                "status": "cluster_extracted",
                "article_id": article_id,
                "candidate_cluster_id": cluster.candidate_cluster_id,
                "product_ids": product_ids,
                "llm_queue_id": None,
            }
        target_type = "product_candidate_cluster" if cluster else "article"
        target_id = cluster.candidate_cluster_id if cluster else article.article_id
        queue_item = self.queue_service.enqueue(
            db,
            target_type=target_type,
            target_id=target_id,
            task_type="extract",
            priority=screening.llm_priority,
            batch_eligible_yn=force_batch_eligible or bool(cluster),
        )
        article.extraction_status = "queued"
        db.flush()
        return {
            "status": "queued",
            "article_id": article_id,
            "candidate_cluster_id": cluster.candidate_cluster_id if cluster else None,
            "target_type": target_type,
            "target_id": target_id,
            "llm_queue_id": queue_item.llm_queue_id,
            "batch_eligible_yn": queue_item.batch_eligible_yn,
        }

    def enqueue_articles_for_crawl_job(
        self,
        db: Session,
        crawl_job_id: int,
        *,
        force_batch_eligible: bool = False,
        limit: int | None = None,
    ) -> dict[str, Any]:
        query = (
            db.query(FactArticle)
            .filter(FactArticle.crawl_job_id == crawl_job_id, FactArticle.extraction_status == "pending")
            .order_by(FactArticle.article_id)
        )
        if limit is not None:
            query = query.limit(limit)
        results = []
        for article in query.all():
            results.append(self.enqueue_article_extraction(db, article.article_id, force_batch_eligible=force_batch_eligible))
        return {
            "processed": len(results),
            "queued": sum(1 for item in results if item.get("status") == "queued"),
            "screened_skip": sum(1 for item in results if item.get("status") == "screened_skip"),
            "cluster_extracted": sum(1 for item in results if item.get("status") == "cluster_extracted"),
            "results": results,
        }

    def extract_from_text(self, db: Session, title: str | None, text: str, source_note: str | None = None) -> dict[str, Any]:
        manual = repository.create_manual_ingestion(db, "manual_text", title=title, text=text, input_json={"source_note": source_note} if source_note else None)
        db.commit()
        return self._run_and_save(db, input_text=text, manual_ingestion_id=manual.manual_ingestion_id)

    def _run_and_save(
        self,
        db: Session,
        input_text: str,
        article_id: int | None = None,
        manual_ingestion_id: int | None = None,
        screening: ScreeningResult | None = None,
    ) -> dict[str, Any]:
        try:
            routed = self._run_pipeline_with_cache(db, input_text, screening=screening)
        except Exception as exc:
            failed = repository.create_llm_run(
                db,
                article_id=article_id,
                manual_ingestion_id=manual_ingestion_id,
                task_type="extract",
                provider="router",
                model_name="unconfigured",
                prompt_version=PROMPT_VERSION,
                schema_version=SCHEMA_VERSION,
                input_hash=sha256_text(input_text),
                output_json=json.dumps({"error": str(exc)}, ensure_ascii=False),
                validation_status="failed",
                estimated_cost_usd=0.0,
            )
            self.cost_service.record_run(db, failed, input_text=input_text)
            if article_id:
                article = db.get(FactArticle, article_id)
                if article:
                    article.extraction_status = "failed"
            if manual_ingestion_id:
                manual = db.get(FactManualIngestion, manual_ingestion_id)
                if manual:
                    manual.processing_status = "failed"
            db.commit()
            return {"status": "failed", "message": str(exc), "llm_run_id": failed.llm_run_id, "product_ids": []}

        extractor_response = routed.get("extractor")
        verifier_response = routed.get("verifier")
        if extractor_response is None:
            return {"status": "failed", "message": "No extractor response", "product_ids": []}
        extractor_output_json = normalize_extraction_payload(extractor_response.output_json)

        extractor_run = repository.create_llm_run(
            db,
            article_id=article_id,
            manual_ingestion_id=manual_ingestion_id,
            task_type=extractor_response.task_type,
            provider=extractor_response.provider,
            model_name=extractor_response.model_name,
            prompt_version=PROMPT_VERSION,
            schema_version=SCHEMA_VERSION,
            input_hash=sha256_text(input_text),
            output_json=json.dumps(extractor_output_json, ensure_ascii=False),
            validation_status="unknown",
            token_input=extractor_response.token_input,
            token_output=extractor_response.token_output,
            latency_ms=extractor_response.latency_ms,
            cost_estimate=extractor_response.cost_estimate,
            cached_yn=bool(getattr(extractor_response, "cached_yn", False)),
            batch_yn=False,
            estimated_cost_usd=extractor_response.cost_estimate,
        )
        self.cost_service.record_run(db, extractor_run, input_text=input_text)
        db.add(
            FactExtractionRawJson(
                article_id=article_id,
                manual_ingestion_id=manual_ingestion_id,
                input_source_type="article" if article_id else "manual_text",
                input_source_id=article_id or manual_ingestion_id,
                model_name=extractor_response.model_name,
                provider=extractor_response.provider,
                prompt_version=PROMPT_VERSION,
                schema_version=SCHEMA_VERSION,
                raw_json=json.dumps(extractor_output_json, ensure_ascii=False),
                validation_status="unknown",
            )
        )
        try:
            extraction = validate_extraction_payload(extractor_output_json)
            extractor_run.validation_status = "pass"
        except ValidationError as exc:
            extractor_run.validation_status = "schema_fail"
            if article_id:
                article = db.get(FactArticle, article_id)
                if article:
                    article.extraction_status = "schema_fail"
            if manual_ingestion_id:
                manual = db.get(FactManualIngestion, manual_ingestion_id)
                if manual:
                    manual.processing_status = "schema_fail"
            db.commit()
            return {"status": "schema_fail", "message": str(exc), "product_ids": []}

        verifier_run_id = None
        verification = None
        if verifier_response is not None:
            verifier_run = repository.create_llm_run(
                db,
                article_id=article_id,
                manual_ingestion_id=manual_ingestion_id,
                task_type=verifier_response.task_type,
                provider=verifier_response.provider,
                model_name=verifier_response.model_name,
                prompt_version=PROMPT_VERSION,
                schema_version=SCHEMA_VERSION,
                input_hash=sha256_text(input_text + json.dumps(extractor_output_json, ensure_ascii=False)),
                output_json=json.dumps(verifier_response.output_json, ensure_ascii=False),
                validation_status="unknown",
                token_input=verifier_response.token_input,
                token_output=verifier_response.token_output,
                latency_ms=verifier_response.latency_ms,
                cost_estimate=verifier_response.cost_estimate,
                cached_yn=bool(getattr(verifier_response, "cached_yn", False)),
                batch_yn=False,
                estimated_cost_usd=verifier_response.cost_estimate,
            )
            verifier_input_text = input_text + json.dumps(extractor_output_json, ensure_ascii=False)
            self.cost_service.record_run(db, verifier_run, input_text=verifier_input_text)
            verifier_run_id = verifier_run.llm_run_id
            try:
                verification_payload = normalize_verification_payload(verifier_response.output_json)
                verification = validate_verification_payload(verification_payload)
                verifier_run.output_json = json.dumps(verification_payload, ensure_ascii=False)
                verifier_run.validation_status = "pass"
            except ValidationError:
                verifier_run.validation_status = "schema_fail"

        extraction, deterministic_corrections = reconcile_extraction(extraction, input_text, verification)
        product_ids = self.save_extraction_result(db, extraction, article_id=article_id, manual_ingestion_id=manual_ingestion_id, source_text=input_text)
        if verification or deterministic_corrections:
            summary = summarize_verification(verification) if verification else {
                "agreement_score": 0.0,
                "conflict_count": len(deterministic_corrections),
                "critical_conflict_count": sum(1 for item in deterministic_corrections if item.get("severity") == "critical"),
                "final_status": "corrected",
                "needs_human_review": False,
            }
            comparison = repository.create_comparison(
                db,
                article_id=article_id,
                manual_ingestion_id=manual_ingestion_id,
                product_id=product_ids[0] if product_ids else None,
                extractor_run_id=extractor_run.llm_run_id,
                verifier_run_id=verifier_run_id,
                agreement_score=summary["agreement_score"],
                conflict_count=summary["conflict_count"],
                critical_conflict_count=summary["critical_conflict_count"],
                final_status=summary["final_status"],
                needs_human_review=summary["needs_human_review"],
            )
            if verification:
                for check in verification.field_checks:
                    repository.create_field_audit(db, comparison.comparison_id, check.model_dump())
            for correction in deterministic_corrections:
                repository.create_field_audit(db, comparison.comparison_id, correction)
        if article_id:
            article = db.get(FactArticle, article_id)
            if article:
                article.extraction_status = "extracted"
        if manual_ingestion_id:
            manual = db.get(FactManualIngestion, manual_ingestion_id)
            if manual:
                manual.processing_status = "processed"
        db.commit()
        return {"status": "saved", "article_id": article_id, "manual_ingestion_id": manual_ingestion_id, "product_ids": product_ids}

    def _run_pipeline_with_cache(self, db: Session, input_text: str, screening: ScreeningResult | None = None) -> dict[str, Any]:
        if not all(hasattr(self.router, name) for name in ["mode", "route_plan"]):
            return self.router.run_pipeline(input_text)
        mode = self.router.mode()
        plan = self.router.route_plan(mode)
        extractor_conf = (plan.get("extractors") or [None])[0] if mode == "parallel_consensus" else plan.get("extractor")
        if not extractor_conf:
            return self.router.run_pipeline(input_text, mode=mode)
        extractor_response = self._run_extract_with_cache(db, input_text, extractor_conf)
        extractor_output = normalize_extraction_payload(extractor_response.output_json)
        verifier_response = None
        verifier_conf = plan.get("verifier")
        verify_only_risky = env_bool("LLM_VERIFY_ONLY_RISKY", True)
        should_verify = (not verify_only_risky) or self.is_risky_for_verification(extractor_output, screening)
        if should_verify and verifier_conf:
            verifier_response = self._run_verify_with_cache(db, input_text, extractor_output, verifier_conf)
        return {"extractor": extractor_response, "verifier": verifier_response, "diff": [], "adjudicator": None}

    def _run_extract_with_cache(self, db: Session, input_text: str, extractor_conf: dict[str, Any]) -> LLMResponse:
        provider_name = extractor_conf["provider"]
        provider = self.router._provider(provider_name, extractor_conf.get("model_env"))
        model_name = self._cache_model_name(provider, provider_name, extractor_conf.get("model_env"))
        cached = self.cache_service.get(
            db,
            input_text=input_text,
            prompt_version=PROMPT_VERSION,
            schema_version=SCHEMA_VERSION,
            provider=provider_name,
            model_name=model_name,
            task_type="extract",
        )
        if cached is not None:
            response = LLMResponse(
                provider=provider_name,
                model_name=model_name,
                task_type="extract",
                output_json=cached,
                raw_text=json.dumps(cached, ensure_ascii=False),
                token_input=LLMCostService.rough_token_count(input_text),
                token_output=LLMCostService.rough_token_count(json.dumps(cached, ensure_ascii=False)),
                cost_estimate=0.0,
            )
            setattr(response, "cached_yn", True)
            return response
        response = provider.extract_product_info(input_text, extraction_json_schema(), PROMPT_VERSION)
        self.cache_service.put(
            db,
            input_text=input_text,
            prompt_version=PROMPT_VERSION,
            schema_version=SCHEMA_VERSION,
            provider=response.provider,
            model_name=response.model_name,
            task_type=response.task_type,
            output_json=response.output_json,
        )
        return response

    def _run_verify_with_cache(self, db: Session, input_text: str, extractor_output_json: dict[str, Any], verifier_conf: dict[str, Any]) -> LLMResponse:
        provider_name = verifier_conf["provider"]
        provider = self.router._provider(provider_name, verifier_conf.get("model_env"))
        model_name = self._cache_model_name(provider, provider_name, verifier_conf.get("model_env"))
        verifier_input_text = input_text + json.dumps(extractor_output_json, ensure_ascii=False)
        cached = self.cache_service.get(
            db,
            input_text=verifier_input_text,
            prompt_version=PROMPT_VERSION,
            schema_version=SCHEMA_VERSION,
            provider=provider_name,
            model_name=model_name,
            task_type="verify",
        )
        if cached is not None:
            response = LLMResponse(
                provider=provider_name,
                model_name=model_name,
                task_type="verify",
                output_json=cached,
                raw_text=json.dumps(cached, ensure_ascii=False),
                token_input=LLMCostService.rough_token_count(verifier_input_text),
                token_output=LLMCostService.rough_token_count(json.dumps(cached, ensure_ascii=False)),
                cost_estimate=0.0,
            )
            setattr(response, "cached_yn", True)
            return response
        response = provider.verify_extraction(input_text, extractor_output_json, verification_json_schema(), PROMPT_VERSION)
        self.cache_service.put(
            db,
            input_text=verifier_input_text,
            prompt_version=PROMPT_VERSION,
            schema_version=SCHEMA_VERSION,
            provider=response.provider,
            model_name=response.model_name,
            task_type=response.task_type,
            output_json=response.output_json,
        )
        return response

    @staticmethod
    def _cache_model_name(provider: Any, provider_name: str, model_env: str | None = None) -> str:
        return (
            getattr(provider, "model_name", None)
            or getattr(provider, "model", None)
            or (os.getenv(model_env or "") if model_env else None)
            or provider_name
        )

    def _llm_input_for_article(self, db: Session, article: FactArticle, screening: ScreeningResult, snippets: list[Any], cluster: Any = None) -> str:
        max_chars = int(os.getenv("LLM_MAX_INPUT_CHARS", "6000"))
        if cluster and env_bool("ENABLE_PRODUCT_CLUSTER_EXTRACTION", True):
            text = self.cluster_service.build_cluster_llm_input(
                db,
                cluster,
                max_articles=int(os.getenv("MAX_ARTICLES_PER_CLUSTER_FOR_LLM", "5")),
                max_chars=int(os.getenv("MAX_CLUSTER_SNIPPET_CHARS", "5000")),
            )
        elif env_bool("LLM_USE_SNIPPETS_ONLY", True):
            text = self.snippet_service.build_llm_input(
                title=article.title,
                description=article.description,
                source_type=article.source_api,
                article_date=article.pub_date,
                company_candidates=screening.matched_company_names,
                product_type_candidates=screening.matched_product_type_codes,
                snippets=snippets,
            )
            text = self._compact_snippet_llm_input(text, max_chars)
        else:
            text = f"{article.title}\n\n{article.description or ''}"
        return text[:max_chars]

    @staticmethod
    def _compact_snippet_llm_input(input_text: str, max_chars: int) -> str:
        """Keep the snippet bundle visible even when title/description are long."""
        if len(input_text or "") <= max_chars:
            return input_text
        try:
            payload = json.loads(input_text)
        except (TypeError, json.JSONDecodeError):
            return (input_text or "")[:max_chars]

        snippets = payload.get("snippets") or {}
        compact_snippets: dict[str, list[str]] = {}
        for snippet_type, values in snippets.items():
            compact_values = []
            for value in (values or [])[:3]:
                compact_values.append(str(value)[: max(60, min(240, max_chars // 5))])
            if compact_values:
                compact_snippets[snippet_type] = compact_values

        compact_payload = {
            "title": payload.get("title"),
            "source_type": payload.get("source_type"),
            "article_date": payload.get("article_date"),
            "company_candidates": payload.get("company_candidates") or [],
            "product_type_candidates": payload.get("product_type_candidates") or [],
            "snippets": compact_snippets,
            "description": str(payload.get("description") or "")[: max(40, min(240, max_chars // 5))],
        }
        compact = json.dumps(compact_payload, ensure_ascii=False, indent=2)
        if len(compact) <= max_chars:
            return compact

        compact_payload["description"] = ""
        for snippet_type, values in list(compact_snippets.items()):
            compact_snippets[snippet_type] = [value[: max(40, min(120, max_chars // 8))] for value in values[:2]]
        compact = json.dumps(compact_payload, ensure_ascii=False, indent=2)
        return compact[:max_chars]

    @staticmethod
    def is_risky_for_verification(extractor_output_json: dict[str, Any] | None, screening: ScreeningResult | None = None) -> bool:
        if not extractor_output_json:
            return True
        normalized = normalize_extraction_payload(extractor_output_json)
        products = normalized.get("products") or []
        for product in products:
            identity = product.get("identity") or {}
            if not identity.get("release_year_month") or identity.get("release_year_month_basis") in {None, "unknown", "first_seen_only"}:
                return True
            if product.get("sales_metrics"):
                return True
            if product.get("needs_human_review"):
                return True
            classification = product.get("product_type_classification") or {}
            if classification.get("needs_human_review"):
                return True
            for coverage in product.get("major_coverages") or []:
                if coverage.get("max_amount_krw"):
                    return True
        if screening and screening.llm_priority == "high":
            reasons = {part.strip() for part in (screening.candidate_reason or "").split(",")}
            return bool({"sales metric", "coverage keyword", "negative keyword"}.intersection(reasons))
        return False

    def save_extraction_result(
        self,
        db: Session,
        extraction: ExtractionResult,
        article_id: int | None = None,
        manual_ingestion_id: int | None = None,
        source_text: str | None = None,
    ) -> list[int]:
        issues = extraction_save_issues(extraction)
        product_ids: list[int] = []
        classifier = ProductTypeClassifier()
        product_plans = self.canonicalization_service.plan_extraction_products(extraction.products, source_text)
        plans_by_index = {plan.index: plan for plan in product_plans}
        first_seen_month = None
        article = None
        if article_id:
            article = db.get(FactArticle, article_id)
            if article and bool(article.multi_company_article_yn):
                article.extraction_status = "excluded_multi_company"
                article.extraction_exclusion_reason = "multiple insurer companies detected in article"
                db.flush()
                return []
            if article and article.pub_date:
                first_seen_month = article.pub_date.strftime("%Y-%m")
        for product_index, product in enumerate(extraction.products):
            identity = product.identity
            plan = plans_by_index.get(product_index)
            observed_name = identity.raw_product_name or identity.normalized_product_name_candidate
            observed_core_key = product_core_key_for_keyword(observed_name)
            observed_primary = product.product_type_classification.primary_product_type
            repository.record_product_observation(
                db,
                article=article,
                raw_product_name=observed_name,
                normalized_product_name_candidate=identity.normalized_product_name_candidate or observed_name,
                product_core_key=observed_core_key,
                company_name_raw=identity.company_name_candidate or identity.company_name_raw,
                partner_company_name=plan.partner_company_name if plan else None,
                product_type_code=observed_primary.code,
                release_year_month=identity.release_year_month,
                observation_context_text=source_text,
                candidate_type=plan.candidate_type if plan else "unknown",
                confidence=product.confidence.total(),
            )
            if plan and not plan.create_product:
                continue
            raw_candidate = identity.raw_product_name or identity.normalized_product_name_candidate
            canonical_name = plan.canonical_name if plan and plan.canonical_name else None
            if canonical_name:
                raw_candidate = canonical_name
            if not raw_candidate or is_negative_product_name(raw_candidate):
                continue
            product_name_validation = validate_product_name_before_save(
                raw_candidate,
                article_title=article.title if article else None,
                context_text=source_text,
            )
            if not product_name_validation.accepted:
                continue
            raw_candidate = product_name_validation.cleaned_name
            primary_llm = product.product_type_classification.primary_product_type
            rule = classifier.classify(canonical_name or identity.raw_product_name or identity.normalized_product_name_candidate)
            primary_code = rule.primary.code if rule.primary.code != "UNKNOWN" else primary_llm.code
            if primary_code == "UNKNOWN":
                continue
            product_row = repository.upsert_product(
                db,
                {
                    "raw_product_name": identity.raw_product_name or identity.normalized_product_name_candidate or canonical_name or "unknown",
                    "normalized_product_name": canonical_name or identity.normalized_product_name_candidate or identity.raw_product_name or "unknown",
                    "company_name": identity.company_name_candidate or identity.company_name_raw,
                    "insurance_type": identity.insurance_type,
                    "release_year_month": identity.release_year_month,
                    "release_year_month_basis": identity.release_year_month_basis,
                    "first_seen_month": first_seen_month,
                    "primary_product_type_code": primary_code,
                    "confidence_total": product.confidence.total(),
                    "needs_review": product.needs_human_review or bool(issues),
                    "product_status": "active" if plan and plan.candidate_type in {"official_name", "launch_name"} else "provisional",
                    "article_id": article_id,
                    "source_type": "article" if article_id else "manual_text",
                    "context_text": source_text,
                    "partner_company_name": plan.partner_company_name if plan else None,
                    "partner_context_summary": plan.partner_context_summary if plan else None,
                    "partner_role": "distribution_partner",
                    "partner_confidence": 0.85 if plan and plan.partner_company_name else 0.0,
                },
                allow_unknown_company=False,
            )
            if product_row is None:
                continue
            repository.record_product_observation(
                db,
                product=product_row,
                article=article,
                raw_product_name=observed_name,
                normalized_product_name_candidate=identity.normalized_product_name_candidate or observed_name,
                product_core_key=product_row.product_core_key or observed_core_key,
                company_name_raw=identity.company_name_candidate or identity.company_name_raw,
                partner_company_name=plan.partner_company_name if plan else None,
                product_type_code=primary_code,
                release_year_month=identity.release_year_month,
                observation_context_text=source_text,
                candidate_type=plan.candidate_type if plan else "unknown",
                confidence=product.confidence.total(),
            )
            product_ids.append(product_row.product_id)
            if plan:
                alias_names = list(dict.fromkeys([plan.raw_name, *plan.alias_names]))
                for alias_name in alias_names:
                    repository.record_product_alias(
                        db,
                        product_row,
                        alias_name,
                        self.canonicalization_service.canonical_name_from_raw(alias_name),
                        None,
                        article_id=article_id,
                        source_type=plan.candidate_type,
                    )
                    if alias_name != observed_name:
                        repository.record_product_observation(
                            db,
                            product=product_row,
                            article=article,
                            raw_product_name=alias_name,
                            normalized_product_name_candidate=self.canonicalization_service.canonical_name_from_raw(alias_name),
                            product_core_key=product_core_key_for_keyword(alias_name),
                            company_name_raw=identity.company_name_candidate or identity.company_name_raw,
                            partner_company_name=plan.partner_company_name,
                            product_type_code=primary_code,
                            release_year_month=identity.release_year_month,
                            observation_context_text=source_text,
                            candidate_type=plan.candidate_type,
                            confidence=product.confidence.total(),
                        )
            repository.add_type_assignment(
                db,
                product_row.product_id,
                {
                    "product_type_code": primary_code,
                    "assignment_role": "primary",
                    "classification_basis": "rule" if primary_code == rule.primary.code else primary_llm.basis,
                    "evidence_text": rule.primary.evidence_text or primary_llm.evidence_text,
                    "confidence": max(rule.primary.confidence, primary_llm.confidence),
                    "needs_human_review": product.product_type_classification.needs_human_review,
                },
                article_id=article_id,
            )
            for secondary in product.product_type_classification.secondary_product_types:
                if secondary.code != primary_code:
                    repository.add_type_assignment(
                        db,
                        product_row.product_id,
                        {
                            "product_type_code": secondary.code,
                            "assignment_role": "secondary",
                            "classification_basis": secondary.basis,
                            "evidence_text": secondary.evidence_text,
                            "confidence": secondary.confidence,
                            "needs_human_review": False,
                        },
                        article_id=article_id,
                    )
            for secondary in rule.secondary:
                if secondary.code != primary_code:
                    repository.add_type_assignment(
                        db,
                        product_row.product_id,
                        {
                            "product_type_code": secondary.code,
                            "assignment_role": "secondary",
                            "classification_basis": "rule",
                            "evidence_text": secondary.evidence_text,
                            "confidence": secondary.confidence,
                            "needs_human_review": False,
                        },
                        article_id=article_id,
                    )
            features = product.structured_features.model_dump()
            features["evidence_text"] = product.evidence.feature_evidence
            features["confidence"] = product.confidence.features
            repository.add_structured_feature(db, product_row.product_id, features, article_id=article_id)
            insight = product.narrative_insights.model_dump()
            insight["missing_fields"] = product.missing_fields
            insight["evidence_text"] = "\n".join(filter(None, [product.evidence.feature_evidence, product.evidence.coverage_evidence, product.evidence.sales_evidence]))
            insight["confidence"] = product.confidence.narrative
            insight["needs_review"] = product.needs_human_review
            repository.add_narrative_insight(db, product_row.product_id, insight, article_id=article_id)
            for coverage in product.major_coverages:
                repository.add_major_coverage(db, product_row.product_id, coverage.model_dump(), article_id=article_id)
            for metric in product.sales_metrics:
                repository.add_sales_metric(db, product_row.product_id, metric.model_dump(), article_id=article_id)
            if article_id:
                repository.link_product_article(
                    db,
                    product_row.product_id,
                    article_id,
                    confidence_total=product.confidence.total(),
                    needs_review=product.needs_human_review,
                    evidence_summary=product.evidence.product_name_evidence,
                )
        if article_id:
            self.canonicalization_service.merge_same_article_products(db, article_id)
            canonical_ids: list[int] = []
            for product_id in product_ids:
                product_row = db.get(DimProduct, product_id)
                if product_row:
                    product_id = repository.canonical_product_for(db, product_row).product_id
                if product_id not in canonical_ids:
                    canonical_ids.append(product_id)
            product_ids = canonical_ids
        return product_ids


def normalize_verification_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return payload
    if "verification_status" in payload and "field_checks" in payload:
        return payload

    field_checks: list[dict[str, Any]] = []

    def walk(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                next_path = f"{path}.{key}" if path else str(key)
                walk(child, next_path)
            return
        if isinstance(value, list):
            for index, child in enumerate(value):
                walk(child, f"{path}[{index}]")
            return
        if isinstance(value, str):
            verdict = value.strip().lower()
            if verdict in VERIFICATION_VERDICTS:
                field_checks.append(
                    {
                        "field_path": path,
                        "verdict": verdict,
                        "reason": None,
                        "severity": "medium" if verdict in {"unsupported", "incorrect", "ambiguous"} else "low",
                    }
                )

    walk(payload, "")
    unsupported_fields = [
        check["field_path"]
        for check in field_checks
        if check["verdict"] in {"unsupported", "incorrect", "ambiguous"}
    ]
    inferred_fields = [check["field_path"] for check in field_checks if check["verdict"] == "inferred"]
    supported_count = sum(1 for check in field_checks if check["verdict"] == "supported")
    overall_confidence = supported_count / len(field_checks) if field_checks else 0.0
    needs_review = bool(unsupported_fields or inferred_fields)
    if unsupported_fields:
        verification_status = "partial"
    elif inferred_fields:
        verification_status = "partial"
    else:
        verification_status = "pass"
    return {
        "verification_status": verification_status,
        "field_checks": field_checks,
        "unsupported_fields": unsupported_fields,
        "inferred_fields": inferred_fields,
        "corrected_fields": [],
        "overall_confidence": overall_confidence,
        "needs_human_review": needs_review,
        "recommended_action": "save_with_review" if needs_review else "save",
    }


def normalize_extraction_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return payload
    normalized = json.loads(json.dumps(payload, ensure_ascii=False))
    products = normalized.get("products")
    if products is None:
        products = []
        normalized["products"] = products
    if "article_relevance" not in normalized:
        normalized["article_relevance"] = {
            "is_relevant": bool(products),
            "relevance_type": "new_product" if products else "irrelevant",
            "reason": "normalized from extractor response",
        }
    relevance = normalized.get("article_relevance") or {}
    relevance_type = relevance.get("relevance_type")
    valid_relevance = {"new_product", "sales_performance", "product_feature", "market_trend", "irrelevant"}
    if relevance_type not in valid_relevance:
        parts = re.split(r"[|,/]+|\s+and\s+|\s*&\s*", str(relevance_type or ""))
        relevance["relevance_type"] = next((part.strip() for part in parts if part.strip() in valid_relevance), "new_product" if products else "irrelevant")
    relevance["is_relevant"] = bool(relevance.get("is_relevant", bool(products)))
    normalized["article_relevance"] = relevance

    for product in products:
        if not isinstance(product, dict):
            continue
        identity = product.get("identity") or {}
        release_year_month = identity.get("release_year_month")
        if isinstance(release_year_month, str):
            parsed = _normalize_year_month(release_year_month)
            identity["release_year_month"] = parsed
        valid_release_basis = {
            "explicit_in_article",
            "inferred_from_article_date",
            "first_seen_only",
            "earliest_related_article_month",
            "external_grounded_source",
            "manual",
            "unknown",
        }
        if identity.get("release_year_month_basis") not in valid_release_basis:
            identity["release_year_month_basis"] = "unknown"
        product["identity"] = identity

        features = product.get("structured_features") or {}
        for key in ("join_age_min", "join_age_max"):
            features[key] = _int_like_to_int(features.get(key))
        for key in ("notification_type", "renewal_type", "payment_period", "coverage_period"):
            features[key] = _evidence_like_to_text(features.get(key))
        sales_channels = features.get("sales_channels")
        if sales_channels is None:
            features["sales_channels"] = []
        elif not isinstance(sales_channels, list):
            features["sales_channels"] = [str(sales_channels)]
        else:
            features["sales_channels"] = [str(item) for item in sales_channels if item is not None]
        product["structured_features"] = features

        for coverage in product.get("major_coverages") or []:
            if not isinstance(coverage, dict):
                continue
            if not isinstance(coverage.get("risk_area"), str):
                coverage["risk_area"] = "unknown"
            detail_level = coverage.get("detail_level")
            if detail_level not in {"exact_coverage", "coverage_group", "marketing_statement", "unknown"}:
                coverage["detail_level"] = "unknown"
            if not isinstance(coverage.get("benefit_type"), str):
                coverage["benefit_type"] = "unknown"
            if not isinstance(coverage.get("display_order"), int):
                coverage["display_order"] = 0
            for key in ("evidence_text", "condition_text", "limit_text", "coverage_summary"):
                coverage[key] = _evidence_like_to_text(coverage.get(key))

        evidence = product.get("evidence") or {}
        if isinstance(evidence, dict):
            for key in (
                "product_name_evidence",
                "company_evidence",
                "release_date_evidence",
                "feature_evidence",
                "coverage_evidence",
                "sales_evidence",
            ):
                evidence[key] = _evidence_like_to_text(evidence.get(key))
        product["evidence"] = evidence

        for metric in product.get("sales_metrics") or []:
            if not isinstance(metric, dict):
                continue
            metric["evidence_text"] = _evidence_like_to_text(metric.get("evidence_text"))
    return normalized


def _normalize_year_month(value: str) -> str | None:
    stripped = value.strip()
    if re.fullmatch(r"\d{4}-\d{2}", stripped):
        return stripped
    match = re.search(r"(\d{4})\D+(\d{1,2})", stripped)
    if match:
        month = int(match.group(2))
        if 1 <= month <= 12:
            return f"{match.group(1)}-{month:02d}"
    return None


def _evidence_like_to_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("evidence_text", "text", "value", "quote", "reason"):
            nested = value.get(key)
            if nested:
                return str(nested)
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return " ".join(str(item) for item in value if item is not None) or None
    return str(value)


def _int_like_to_int(value: Any) -> int | None:
    if value is None or isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, dict):
        for key in ("value", "number", "age"):
            parsed = _int_like_to_int(value.get(key))
            if parsed is not None:
                return parsed
        return None
    match = re.search(r"\d+", str(value))
    return int(match.group(0)) if match else None
