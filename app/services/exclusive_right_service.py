from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from io import BytesIO
import json
import os
import re
from typing import Any

import pandas as pd
from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from app.db.models import (
    DimCompany,
    FactArticle,
    FactExclusiveUseRight,
    FactExclusiveUseRightAlias,
    FactExclusiveUseRightArticle,
    FactExclusiveUseRightMergeDecision,
    FactExclusiveUseRightObservation,
    FactLLMQueue,
)
from app.extractors.exclusive_right_schema import ExclusiveRightExtractionResult, validate_exclusive_right_payload
from app.normalizers.company_normalizer import CompanyMatch, CompanyNormalizer
from app.services.company_attribution_service import CompanyAttributionService
from app.services.exclusive_right_final_adjudication_service import ExclusiveRightFinalAdjudicationService
from app.services.final_adjudication_provider_factory import build_final_adjudication_provider
from app.services.company_logo_service import CompanyLogoService
from app.services.exclusive_right_local_context import (
    fallback_earliest_article_month,
    has_bad_subject_tail,
    is_generic_or_weak_subject,
    is_valid_year_month,
    is_weak_subject,
    looks_like_formal_exclusive_subject,
    parse_explicit_acquired_year_month,
    resolve_subject_reference,
    select_best_exclusive_context_window,
    validate_exclusive_subject_before_save,
)
from app.utils.text import compact_spaces, normalize_search_key
from app.services.llm_queue_service import LLMQueueService
from app.services.article_eligibility_filter_service import ArticleEligibilityFilterService
from app.services.product_company_eligibility import is_product_news_eligible_company
from app.services.screening_service import ScreeningService
from app.services.snippet_service import SnippetService


ALL_INSURANCE_TYPE_VALUES = {"", "전체", "?꾩껜", None}
EXCLUSIVE_KEYWORDS = ("배타적사용권", "배타적 사용권", "독점사용권", "독점 사용권", "신상품심의위원회", "신상품 심의위원회")
ACQUIRED_KEYWORDS = ("획득", "부여", "부여받", "취득", "승인", "인정", "인정받", "받았다")
NON_INSURER_PATTERNS = (
    re.compile(r"^[가-힣A-Za-z0-9]{1,12}(농협|축협)(중앙회|은행)?(지점|지역본부|본부)?$"),
    re.compile(r"^[가-힣A-Za-z0-9]{1,20}(지점|대리점|지역본부|본부|GA)$"),
    re.compile(r"^(LG유플러스|LG U\+|유플러스|카카오|네이버|토스|은행|카드)$"),
)


@dataclass
class ResolvedCompany:
    company_id: int | None
    company_name_normalized: str | None
    insurance_type: str
    confidence: float
    evidence_text: str | None
    needs_review: bool


class ExclusiveRightService:
    def __init__(self, normalizer: CompanyNormalizer | None = None) -> None:
        self.normalizer = normalizer or CompanyNormalizer()

    def create_from_text(
        self,
        db: Session,
        text: str,
        *,
        article: FactArticle | None = None,
        company_name_candidate: str | None = None,
        confidence: float = 0.8,
    ) -> FactExclusiveUseRight | None:
        if not self._looks_like_exclusive_right(text):
            return None
        payload = self._extract_minimal_payload(text, article)
        payload["company_name_raw"] = company_name_candidate or payload.get("company_name_raw")
        payload["confidence_total"] = confidence
        try:
            return self.upsert_observation(db, payload, article=article, full_text=text)
        except ValueError:
            return None

    def upsert_observation(
        self,
        db: Session,
        payload: dict[str, Any],
        *,
        article: FactArticle | None = None,
        full_text: str | None = None,
    ) -> FactExclusiveUseRight:
        context_text = self._local_context_text(payload, article=article, full_text=full_text)
        validation = validate_exclusive_subject_before_save(
            payload.get("subject_name"),
            evidence_text=payload.get("evidence_text"),
            window_text=context_text,
            article_title=article.title if article else payload.get("article_title"),
        )
        subject_name = compact_spaces(validation.subject_name)
        acquired_year_month = self._resolve_acquired_year_month_for_payload(payload, article=article, context_text=context_text)
        subject_core_key = normalize_search_key(subject_name)
        if not subject_name:
            self._save_review_observation(db, payload, article=article, status_candidate="rejected", full_text=full_text, review_reason=validation.reason)
            db.commit()
            raise ValueError(f"exclusive right subject rejected before save: {validation.reason}")
        text_for_company = " ".join(
            str(value or "")
            for value in [
                payload.get("evidence_text"),
                payload.get("company_evidence_text"),
                context_text,
                payload.get("company_name_candidate"),
            ]
        )
        resolved = self._resolve_company(
            db,
            payload.get("company_name_raw") or payload.get("company_name_candidate"),
            text_for_company,
            local_text=payload.get("evidence_text") or payload.get("company_evidence_text") or context_text,
            article_title=article.title if article else payload.get("article_title"),
            article_description=article.description if article else None,
            product_or_subject_name=subject_name,
        )
        company_row = db.get(DimCompany, resolved.company_id) if resolved.company_id else None
        ineligible_company = bool(resolved.company_id and not is_product_news_eligible_company(company_row))
        if ineligible_company:
            resolved.needs_review = True
        exclusivity_months = self._nullable_int(payload.get("exclusivity_months"))
        final_adjudication_service = ExclusiveRightFinalAdjudicationService(provider=build_final_adjudication_provider())
        final_decision = final_adjudication_service.adjudicate(
            db,
            final_adjudication_service.build_input(
                db,
                subject_name=subject_name,
                company_name=resolved.company_name_normalized or payload.get("company_name_raw") or payload.get("company_name_candidate"),
                acquired_year_month=acquired_year_month,
                exclusivity_months=exclusivity_months,
                article=article,
                context_text=context_text,
                evidence_text=payload.get("evidence_text"),
            ),
        )
        if final_decision.decision in {"reject", "ineligible_article"}:
            self._save_review_observation(
                db,
                payload,
                article=article,
                status_candidate="rejected",
                full_text=full_text,
                review_reason=final_decision.reason,
            )
            db.commit()
            raise ValueError(f"exclusive right rejected by final adjudication: {final_decision.reason}")
        if final_decision.subject_name:
            subject_name = final_decision.subject_name
            subject_core_key = normalize_search_key(subject_name)
        if final_decision.acquired_year_month:
            acquired_year_month = final_decision.acquired_year_month
        needs_review = (
            bool(payload.get("needs_review"))
            or resolved.needs_review
            or resolved.company_id is None
            or validation.needs_review
            or not is_valid_year_month(acquired_year_month)
            or exclusivity_months is None
            or ineligible_company
            or final_decision.decision != "accept"
        )
        confidence_total = float(payload.get("confidence_total") or payload.get("confidence") or 0.0)
        exclusive_right = self._find_canonical(
            db,
            resolved.company_id,
            resolved.company_name_normalized,
            subject_core_key,
            acquired_year_month,
            exclusivity_months,
        )
        if exclusive_right is None:
            exclusive_right = FactExclusiveUseRight(
                company_id=resolved.company_id,
                company_name_normalized=resolved.company_name_normalized,
                insurance_type=resolved.insurance_type,
                subject_name=subject_name,
                subject_core_key=subject_core_key,
                exclusivity_months=exclusivity_months,
                acquired_year_month=acquired_year_month,
                feature_summary=payload.get("feature_summary"),
                evidence_summary=payload.get("evidence_summary"),
                primary_article_id=article.article_id if article else payload.get("primary_article_id"),
                primary_article_title=article.title if article else payload.get("primary_article_title") or payload.get("article_title"),
                primary_article_url=self._article_url(article) if article else payload.get("primary_article_url") or payload.get("article_url"),
                article_count=1 if article else int(payload.get("article_count") or 0),
                confidence_total=confidence_total,
                needs_review=needs_review,
                event_status="active" if not needs_review else "review",
                alias_names_json=self._json_list([subject_name]),
                evidence_text=payload.get("evidence_text"),
            )
            db.add(exclusive_right)
            db.flush()
        else:
            exclusive_right.company_id = resolved.company_id or exclusive_right.company_id
            exclusive_right.company_name_normalized = resolved.company_name_normalized or exclusive_right.company_name_normalized
            exclusive_right.insurance_type = resolved.insurance_type or exclusive_right.insurance_type
            exclusive_right.confidence_total = max(float(exclusive_right.confidence_total or 0), confidence_total)
            exclusive_right.needs_review = bool(exclusive_right.needs_review) or needs_review
            exclusive_right.event_status = "active" if not exclusive_right.needs_review and exclusive_right.company_id else "review"
            exclusive_right.article_count = max(int(exclusive_right.article_count or 0), self._observation_count(db, exclusive_right.exclusive_right_id) + 1)
            exclusive_right.alias_names_json = self._json_list(sorted(set(self._json_load(exclusive_right.alias_names_json) + [subject_name])))
            if self._should_replace_canonical_subject(exclusive_right.subject_name, subject_name):
                exclusive_right.alias_names_json = self._json_list(sorted(set(self._json_load(exclusive_right.alias_names_json) + [exclusive_right.subject_name])))
                exclusive_right.subject_name = subject_name
                exclusive_right.subject_core_key = subject_core_key
            explicit_month = parse_explicit_acquired_year_month(context_text, article.pub_date if article else None)
            if explicit_month:
                exclusive_right.acquired_year_month = explicit_month
            elif not is_valid_year_month(exclusive_right.acquired_year_month):
                exclusive_right.acquired_year_month = acquired_year_month

        article_id = article.article_id if article else payload.get("article_id")
        observation = self._existing_observation(
            db,
            exclusive_right_id=exclusive_right.exclusive_right_id,
            article_id=article_id,
            subject_core_key=subject_core_key,
        )
        is_new_observation = observation is None
        if observation is None:
            observation = FactExclusiveUseRightObservation(
                exclusive_right_id=exclusive_right.exclusive_right_id,
                article_id=article_id,
            )
            db.add(observation)
        observation.company_id = resolved.company_id
        observation.company_name_normalized = resolved.company_name_normalized
        observation.insurance_type = resolved.insurance_type
        observation.source_url = self._article_url(article) if article else payload.get("article_url") or payload.get("source_url")
        observation.raw_subject_name = validation.original_subject_name or subject_name
        observation.normalized_subject_name_candidate = subject_name
        observation.subject_core_key = subject_core_key
        observation.exclusivity_months = exclusive_right.exclusivity_months
        observation.acquired_year_month = exclusive_right.acquired_year_month
        observation.feature_summary = payload.get("feature_summary") or observation.feature_summary
        observation.article_title = article.title if article else payload.get("article_title") or observation.article_title
        observation.evidence_text = payload.get("evidence_text") or context_text or observation.evidence_text
        observation.status_candidate = payload.get("status_candidate") or "acquired"
        observation.confidence = max(float(observation.confidence or 0), confidence_total)
        observation.needs_review = needs_review if is_new_observation else (bool(observation.needs_review) or needs_review)
        if exclusive_right.canonical_exclusive_right_id is None:
            exclusive_right.canonical_exclusive_right_id = exclusive_right.exclusive_right_id
        if article:
            self._link_article(db, exclusive_right, article, confidence_total, payload.get("evidence_text"))
        self._upsert_alias(db, exclusive_right, subject_name, subject_core_key, article.article_id if article else payload.get("article_id"))
        if validation.original_subject_name and validation.original_subject_name != subject_name:
            self._upsert_alias(db, exclusive_right, validation.original_subject_name, normalize_search_key(validation.original_subject_name), article.article_id if article else payload.get("article_id"))
        self._refresh_canonical_acquired_month(db, exclusive_right)
        db.commit()
        db.refresh(exclusive_right)
        return exclusive_right

    def list_rights(
        self,
        db: Session,
        *,
        insurance_type: str | None = None,
        company_id: int | None = None,
        company_name: str | None = None,
        company_names: list[str] | None = None,
        acquired_year_month_from: str | None = None,
        acquired_year_month_to: str | None = None,
        months_back: int | None = None,
        include_review: bool = False,
        keyword: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        query = db.query(FactExclusiveUseRight)
        query = self._apply_filters(
            query,
            insurance_type=insurance_type,
            company_id=company_id,
            company_name=company_name,
            company_names=company_names,
            acquired_year_month_from=acquired_year_month_from,
            acquired_year_month_to=acquired_year_month_to,
            months_back=months_back,
            include_review=include_review,
            keyword=keyword,
        )
        rows = (
            query.order_by(FactExclusiveUseRight.acquired_year_month.desc().nullslast(), FactExclusiveUseRight.exclusive_right_id.desc())
            .limit(max(1, min(limit * 5, 1000)))
            .all()
        )
        public_rows = [row for row in rows if include_review or self._is_public_subject(row)]
        return [self._list_item(row) for row in public_rows[: max(1, min(limit, 500))]]

    def detail(self, db: Session, exclusive_right_id: int) -> dict[str, Any] | None:
        row = db.get(FactExclusiveUseRight, exclusive_right_id)
        if row is None:
            return None
        observations = (
            db.query(FactExclusiveUseRightObservation)
            .filter(FactExclusiveUseRightObservation.exclusive_right_id == exclusive_right_id)
            .order_by(FactExclusiveUseRightObservation.observation_id.asc())
            .all()
        )
        item = self._list_item(row)
        item.update(
            {
                "observations": [
                    {
                        "observation_id": obs.observation_id,
                        "article_id": obs.article_id,
                        "company_id": obs.company_id,
                        "company_name_normalized": obs.company_name_normalized,
                        "insurance_type": obs.insurance_type,
                        "raw_subject_name": obs.raw_subject_name,
                        "subject_name": obs.normalized_subject_name_candidate or obs.raw_subject_name,
                        "source_url": obs.source_url,
                        "status_candidate": obs.status_candidate,
                        "evidence_text": obs.evidence_text,
                    }
                    for obs in observations
                ]
            }
        )
        return item

    def recent_dashboard(
        self,
        db: Session,
        *,
        insurance_type: str | None = None,
        months_back: int = 12,
        limit: int = 10,
        include_review: bool = False,
        fallback_latest: bool = True,
    ) -> dict[str, Any]:
        fallback_used = False
        items = self.list_rights(
            db,
            insurance_type=insurance_type,
            months_back=months_back,
            include_review=include_review,
            limit=limit,
        )
        if not items and fallback_latest:
            items = self.list_rights(
                db,
                insurance_type=insurance_type,
                include_review=include_review,
                limit=limit,
            )
            fallback_used = bool(items)
        return {
            "months_back": months_back,
            "display_period": f"최근 {months_back}개월",
            "fallback_used": fallback_used,
            "items": [
                {
                    "exclusive_right_id": item["exclusive_right_id"],
                    "insurance_type": item["insurance_type"],
                    "company_id": item["company_id"],
                    "company_name": item["company_name"],
                    "company_logo_url": CompanyLogoService().get_logo_url(item["company_name"], item["insurance_type"]),
                    "subject_name": item["subject_name"],
                    "exclusivity_months": item["exclusivity_months"],
                    "acquired_year_month": item["acquired_year_month"],
                    "summary": item["feature_summary"],
                    "article_title": item["article_title"],
                    "article_pub_date": item.get("article_pub_date"),
                    "article_url": item["primary_article_url"],
                }
                for item in items
            ],
        }

    def export_workbook(self, db: Session, filters: dict[str, Any]) -> BytesIO:
        rows = [
            {
                "배타적사용권 ID": item["exclusive_right_id"],
                "업종": item["insurance_type"],
                "보험회사": item["company_name"],
                "상품/특약/제도명": item["subject_name"],
                "배타적사용권 기간 개월 수": item["exclusivity_months"],
                "획득년월": item["acquired_year_month"],
                "주요 특징": item["feature_summary"],
                "대표 기사 제목": item["article_title"],
                "대표 기사 URL": item["primary_article_url"],
                "alias 목록": item["alias_names"],
                "근거문장": item["evidence_text"],
            }
            for item in self.list_rights(db, limit=500, **filters)
        ]
        columns = [
            "배타적사용권 ID",
            "업종",
            "보험회사",
            "상품/특약/제도명",
            "배타적사용권 기간 개월 수",
            "획득년월",
            "주요 특징",
            "대표 기사 제목",
            "대표 기사 URL",
            "alias 목록",
            "근거문장",
        ]
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            pd.DataFrame(rows, columns=columns).to_excel(writer, index=False, sheet_name="배타적사용권")
            worksheet = writer.sheets["배타적사용권"]
            worksheet.freeze_panes = "A2"
            worksheet.auto_filter.ref = worksheet.dimensions
            for column_cells in worksheet.columns:
                header = str(column_cells[0].value or "")
                width = 44 if header in {"주요 특징", "대표 기사 제목", "대표 기사 URL", "근거문장", "alias 목록"} else 18
                worksheet.column_dimensions[column_cells[0].column_letter].width = width
        output.seek(0)
        return output

    def extract_pending(
        self,
        db: Session,
        *,
        limit: int = 100,
        mode: str = "enqueue_only",
        date_from: str | None = None,
        date_to: str | None = None,
        crawl_job_id: int | None = None,
    ) -> dict[str, Any]:
        if mode not in {"none", "screening_only", "enqueue_only", "realtime", "batch"}:
            raise ValueError(f"Unsupported exclusive extraction mode: {mode}")
        if mode == "none":
            return self._empty_extract_summary(mode, date_from, date_to)
        screening_count = self._ensure_candidate_screenings(db, date_from=date_from, date_to=date_to, crawl_job_id=crawl_job_id, limit=max(limit * 3, limit))
        if mode == "screening_only":
            summary = self._empty_extract_summary(mode, date_from, date_to)
            summary["crawl_job_id"] = crawl_job_id
            summary["screened_count"] = screening_count
            summary["candidate_count"] = self._candidate_count(db, date_from=date_from, date_to=date_to, crawl_job_id=crawl_job_id)
            db.commit()
            return summary
        if mode in {"enqueue_only", "batch"}:
            return self.enqueue_pending(
                db,
                date_from=date_from,
                date_to=date_to,
                crawl_job_id=crawl_job_id,
                limit=limit,
                batch_eligible=(mode == "batch"),
                mode=mode,
            )

        realtime_limit = int(os.getenv("EXCLUSIVE_RIGHT_REALTIME_LIMIT", "20"))
        if limit > realtime_limit:
            raise ValueError(f"Realtime exclusive-right extraction limit exceeds EXCLUSIVE_RIGHT_REALTIME_LIMIT={realtime_limit}")
        articles = self._candidate_articles(db, date_from=date_from, date_to=date_to, crawl_job_id=crawl_job_id, limit=limit, include_completed_queue=False)
        processed = saved = skipped_existing_observation_count = 0
        for article in articles:
            if self._article_has_observation(db, article.article_id):
                skipped_existing_observation_count += 1
                continue
            processed += 1
            snippets = SnippetService().extract_for_article(db, article)
            text_value = self._exclusive_snippet_text(article, snippets)
            if self.create_from_text(db, text_value, article=article):
                saved += 1
        db.commit()
        consolidation_result = None
        if saved:
            from app.services.exclusive_right_consolidation_service import ExclusiveRightConsolidationService

            consolidation_result = ExclusiveRightConsolidationService().run(
                db,
                mode="rule_only_apply",
                crawl_job_id=crawl_job_id,
                date_from=date_from,
                date_to=date_to,
            )
        return {
            "mode": mode,
            "date_from": date_from,
            "date_to": date_to,
            "crawl_job_id": crawl_job_id,
            "candidate_count": self._candidate_count(db, date_from=date_from, date_to=date_to, crawl_job_id=crawl_job_id),
            "processed": processed,
            "queued": 0,
            "queued_count": 0,
            "saved": saved,
            "realtime_processed_count": processed,
            "batch_eligible": 0,
            "batch_eligible_count": 0,
            "skipped_count": skipped_existing_observation_count,
            "skipped_existing_observation_count": skipped_existing_observation_count,
            "consolidation": consolidation_result,
        }

    def screen_candidates_for_crawl_job(self, db: Session, crawl_job_id: int, *, limit: int | None = None) -> dict[str, Any]:
        effective_limit = limit or int(os.getenv("EXCLUSIVE_RIGHT_BATCH_LIMIT", "1000"))
        screened_count = self._ensure_candidate_screenings(
            db,
            date_from=None,
            date_to=None,
            crawl_job_id=crawl_job_id,
            limit=max(effective_limit * 3, effective_limit),
        )
        candidate_count = self._candidate_count(db, date_from=None, date_to=None, crawl_job_id=crawl_job_id)
        db.commit()
        return {
            "mode": "screening_only",
            "crawl_job_id": crawl_job_id,
            "screened_count": screened_count,
            "candidate_count": candidate_count,
            "queued_count": 0,
        }

    def enqueue_pending_for_crawl_job(
        self,
        db: Session,
        crawl_job_id: int,
        *,
        batch_eligible: bool,
        limit: int | None = None,
    ) -> dict[str, Any]:
        return self.enqueue_pending(
            db,
            crawl_job_id=crawl_job_id,
            limit=limit or int(os.getenv("EXCLUSIVE_RIGHT_BATCH_LIMIT", "1000")),
            batch_eligible=batch_eligible,
            mode="batch" if batch_eligible else "enqueue_only",
        )

    def extract_pending_for_crawl_job(
        self,
        db: Session,
        crawl_job_id: int,
        *,
        mode: str = "realtime",
        limit: int | None = None,
    ) -> dict[str, Any]:
        return self.extract_pending(
            db,
            crawl_job_id=crawl_job_id,
            mode=mode,
            limit=limit or int(os.getenv("EXCLUSIVE_RIGHT_REALTIME_LIMIT", "20")),
        )

    def enqueue_pending(
        self,
        db: Session,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
        crawl_job_id: int | None = None,
        limit: int = 100,
        batch_eligible: bool = False,
        mode: str | None = None,
    ) -> dict[str, Any]:
        self._ensure_candidate_screenings(db, date_from=date_from, date_to=date_to, crawl_job_id=crawl_job_id, limit=max(limit * 3, limit))
        articles = self._candidate_articles(db, date_from=date_from, date_to=date_to, crawl_job_id=crawl_job_id, limit=limit, include_completed_queue=True)
        queue_service = LLMQueueService()
        candidate_count = self._candidate_count(db, date_from=date_from, date_to=date_to, crawl_job_id=crawl_job_id)
        queued_count = skipped_existing_queue_count = skipped_existing_observation_count = skipped_no_snippet_count = 0
        skipped_ineligible_count = 0
        for article in articles:
            decision = ArticleEligibilityFilterService().classify_article(db, article)
            if not decision.is_eligible:
                ArticleEligibilityFilterService().mark_article(db, article, decision)
                skipped_ineligible_count += 1
                continue
            if self._article_has_observation(db, article.article_id):
                skipped_existing_observation_count += 1
                continue
            if self._article_has_queue(db, article.article_id, include_completed=True):
                skipped_existing_queue_count += 1
                continue
            snippets = SnippetService().extract_for_article(db, article)
            exclusive_snippets = [
                snippet for snippet in snippets if str(snippet.snippet_type).startswith("exclusive_") or snippet.snippet_type == "exclusive_right"
            ]
            if not exclusive_snippets and not (article.title or article.description):
                skipped_no_snippet_count += 1
                continue
            queue = queue_service.enqueue(
                db,
                target_type="article",
                target_id=article.article_id,
                task_type="exclusive_right_extract",
                priority="high",
                batch_eligible_yn=batch_eligible,
            )
            queue.batch_eligible_yn = batch_eligible
            queue.crawl_job_id = queue.crawl_job_id or crawl_job_id or article.crawl_job_id
            queued_count += 1
        db.commit()
        return {
            "mode": mode or ("batch" if batch_eligible else "enqueue_only"),
            "date_from": date_from,
            "date_to": date_to,
            "crawl_job_id": crawl_job_id,
            "candidate_count": candidate_count,
            "processed": len(articles),
            "queued": queued_count,
            "queued_count": queued_count,
            "realtime_processed_count": 0,
            "saved": 0,
            "batch_eligible": queued_count if batch_eligible else 0,
            "batch_eligible_count": queued_count if batch_eligible else 0,
            "skipped_count": skipped_existing_queue_count + skipped_existing_observation_count + skipped_no_snippet_count + skipped_ineligible_count,
            "skipped_ineligible_count": skipped_ineligible_count,
            "skipped_existing_queue_count": skipped_existing_queue_count,
            "skipped_existing_observation_count": skipped_existing_observation_count,
            "skipped_no_snippet_count": skipped_no_snippet_count,
        }

    def queue_status(
        self,
        db: Session,
        *,
        crawl_job_id: int | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> dict[str, Any]:
        candidate_count = self._candidate_count(db, date_from=date_from, date_to=date_to, crawl_job_id=crawl_job_id)
        queue_query = db.query(FactLLMQueue).filter(
            FactLLMQueue.target_type == "article",
            FactLLMQueue.task_type == "exclusive_right_extract",
        )
        if crawl_job_id is not None:
            article_ids = db.query(FactArticle.article_id).filter(FactArticle.crawl_job_id == crawl_job_id)
            queue_query = queue_query.filter(or_(FactLLMQueue.crawl_job_id == crawl_job_id, FactLLMQueue.target_id.in_(article_ids)))
        if date_from or date_to:
            article_query = db.query(FactArticle.article_id)
            if date_from:
                article_query = article_query.filter(FactArticle.pub_date >= datetime.fromisoformat(date_from))
            if date_to:
                article_query = article_query.filter(FactArticle.pub_date < datetime.fromisoformat(date_to) + timedelta(days=1))
            queue_query = queue_query.filter(FactLLMQueue.target_id.in_(article_query))
        return {
            "crawl_job_id": crawl_job_id,
            "date_from": date_from,
            "date_to": date_to,
            "exclusive_right_candidate_count": candidate_count,
            "queued_pending_count": queue_query.filter(FactLLMQueue.status == "pending").count(),
            "queued_batch_eligible_count": queue_query.filter(FactLLMQueue.batch_eligible_yn.is_(True), FactLLMQueue.status == "pending").count(),
            "queued_completed_count": queue_query.filter(FactLLMQueue.status == "completed").count(),
            "queued_failed_count": queue_query.filter(FactLLMQueue.status == "failed").count(),
            "observation_count": self._observation_count_for_period(db, date_from=date_from, date_to=date_to, crawl_job_id=crawl_job_id),
            "canonical_count": self._canonical_count_for_period(db, date_from=date_from, date_to=date_to, crawl_job_id=crawl_job_id),
        }

    def _ensure_candidate_screenings(
        self,
        db: Session,
        *,
        date_from: str | None,
        date_to: str | None,
        crawl_job_id: int | None = None,
        limit: int,
    ) -> int:
        existing_ids = {
            row[0]
            for row in db.execute(
                text("SELECT article_id FROM fact_content_screening WHERE exclusive_right_candidate_yn = 1")
            ).all()
        }
        query = db.query(FactArticle).order_by(FactArticle.article_id)
        if crawl_job_id is not None:
            query = query.filter(FactArticle.crawl_job_id == crawl_job_id)
        if date_from:
            query = query.filter(FactArticle.pub_date >= datetime.fromisoformat(date_from))
        if date_to:
            query = query.filter(FactArticle.pub_date < datetime.fromisoformat(date_to) + timedelta(days=1))
        service = ScreeningService()
        screened = 0
        for article in query.limit(max(1, min(limit, 3000))).all():
            if article.article_id not in existing_ids:
                service.screen_article(db, article)
                screened += 1
        db.flush()
        return screened

    def save_extraction_result(
        self,
        db: Session,
        article_id: int | None,
        extraction: ExclusiveRightExtractionResult | dict[str, Any],
        *,
        llm_run_id: int | None = None,
    ) -> dict[str, Any]:
        result = extraction if isinstance(extraction, ExclusiveRightExtractionResult) else validate_exclusive_right_payload(extraction)
        article = db.get(FactArticle, article_id) if article_id else None
        if article:
            decision = ArticleEligibilityFilterService().classify_article(db, article)
            if not decision.is_eligible:
                ArticleEligibilityFilterService().mark_article(db, article, decision)
                return {
                    "status": "excluded_article_eligibility",
                    "saved_count": 0,
                    "observation_count": 0,
                    "skipped_count": len(result.exclusive_rights),
                    "llm_run_id": llm_run_id,
                }
        if article and bool(article.multi_company_article_yn):
            return {
                "status": "excluded_multi_company",
                "saved_count": 0,
                "observation_count": 0,
                "skipped_count": len(result.exclusive_rights),
                "llm_run_id": llm_run_id,
            }
        saved_count = 0
        observation_count = 0
        skipped_count = 0
        status = result.exclusive_right_relevance.status
        for item in result.exclusive_rights:
            payload = self._payload_from_schema_item(item)
            payload["article_id"] = article_id
            if status == "acquired":
                try:
                    self.upsert_observation(
                        db,
                        payload,
                        article=article,
                        full_text=self._exclusive_snippet_text(article, SnippetService().extract_for_article(db, article)) if article else None,
                    )
                    saved_count += 1
                    observation_count += 1
                except ValueError:
                    observation_count += 1
            elif status == "applied_or_planned":
                self._save_review_observation(db, payload, article=article, status_candidate="applied_or_planned")
                observation_count += 1
            else:
                skipped_count += 1
        return {
            "status": status,
            "saved_count": saved_count,
            "observation_count": observation_count,
            "skipped_count": skipped_count,
            "llm_run_id": llm_run_id,
        }

    def _payload_from_schema_item(self, item: Any) -> dict[str, Any]:
        subject_name = item.subject.normalized_subject_name_candidate or item.subject.raw_subject_name or "배타적사용권 대상 미확인"
        period_evidence = getattr(item.exclusivity, "evidence_text", None)
        evidence_summary = getattr(item, "evidence_summary", None)
        return {
            "company_name_raw": getattr(item, "company_name_raw", None) or item.company_name_candidate,
            "company_name_candidate": item.company_name_candidate,
            "company_evidence_text": getattr(item, "company_evidence_text", None),
            "subject_name": subject_name,
            "subject_core_key": item.subject.subject_core_key or normalize_search_key(subject_name),
            "exclusivity_months": item.exclusivity.months,
            "acquired_year_month": item.acquired.year_month,
            "feature_summary": item.feature_summary,
            "evidence_summary": evidence_summary,
            "evidence_text": evidence_summary or period_evidence,
            "confidence_total": item.confidence,
            "needs_review": item.needs_review,
        }

    def _save_review_observation(
        self,
        db: Session,
        payload: dict[str, Any],
        *,
        article: FactArticle | None = None,
        status_candidate: str = "unknown",
        full_text: str | None = None,
        review_reason: str | None = None,
    ) -> FactExclusiveUseRightObservation:
        context_text = self._local_context_text(payload, article=article, full_text=full_text)
        text_for_company = " ".join(
            str(value or "")
            for value in [
                context_text,
                payload.get("company_evidence_text"),
                payload.get("evidence_text"),
                payload.get("subject_name"),
            ]
        )
        resolved = self._resolve_company(
            db,
            payload.get("company_name_raw") or payload.get("company_name_candidate"),
            text_for_company,
            local_text=payload.get("evidence_text") or payload.get("evidence_summary") or text_for_company,
            article_title=payload.get("article_title"),
            product_or_subject_name=payload.get("subject_name"),
        )
        subject_name = compact_spaces(payload.get("subject_name")) or "배타적사용권 대상 미확인"
        subject_core_key = normalize_search_key(subject_name)
        article_id = article.article_id if article else payload.get("article_id")
        observation = self._existing_observation(db, exclusive_right_id=None, article_id=article_id, subject_core_key=subject_core_key)
        if observation is None:
            observation = FactExclusiveUseRightObservation(article_id=article_id, raw_subject_name=subject_name)
            db.add(observation)
        observation.exclusive_right_id = None
        observation.company_id = resolved.company_id
        observation.company_name_normalized = resolved.company_name_normalized
        observation.insurance_type = resolved.insurance_type
        observation.source_url = self._article_url(article) if article else payload.get("article_url") or payload.get("source_url")
        observation.raw_subject_name = subject_name
        observation.normalized_subject_name_candidate = None if is_weak_subject(subject_name) else subject_name
        observation.subject_core_key = subject_core_key
        observation.exclusivity_months = self._nullable_int(payload.get("exclusivity_months"))
        observation.acquired_year_month = self._resolve_acquired_year_month_for_payload(payload, article=article, context_text=context_text)
        observation.feature_summary = payload.get("feature_summary")
        observation.article_title = article.title if article else payload.get("article_title")
        observation.evidence_text = payload.get("evidence_text") or review_reason or context_text
        observation.status_candidate = status_candidate or payload.get("status_candidate") or "unknown"
        observation.confidence = max(float(observation.confidence or 0), float(payload.get("confidence_total") or payload.get("confidence") or 0.0))
        observation.needs_review = True
        db.flush()
        return observation

    def _candidate_articles(
        self,
        db: Session,
        *,
        date_from: str | None,
        date_to: str | None,
        crawl_job_id: int | None = None,
        limit: int,
        include_completed_queue: bool,
    ) -> list[FactArticle]:
        candidate_ids_query = text(
            """
            SELECT DISTINCT article_id
            FROM fact_content_screening
            WHERE exclusive_right_candidate_yn = 1
            """
        )
        candidate_ids = [row[0] for row in db.execute(candidate_ids_query).all()]
        if not candidate_ids:
            return []
        query = db.query(FactArticle).filter(FactArticle.article_id.in_(candidate_ids))
        query = query.filter(FactArticle.multi_company_article_yn == False)  # noqa: E712
        if crawl_job_id is not None:
            query = query.filter(FactArticle.crawl_job_id == crawl_job_id)
        if date_from:
            query = query.filter(FactArticle.pub_date >= datetime.fromisoformat(date_from))
        if date_to:
            query = query.filter(FactArticle.pub_date < datetime.fromisoformat(date_to) + timedelta(days=1))
        if include_completed_queue:
            queued_ids = [
                row[0]
                for row in db.query(FactLLMQueue.target_id)
                .filter(
                    FactLLMQueue.target_type == "article",
                    FactLLMQueue.task_type == "exclusive_right_extract",
                    FactLLMQueue.status.in_(["pending", "running", "completed"]),
                )
                .all()
            ]
            if queued_ids:
                query = query.filter(~FactArticle.article_id.in_(queued_ids))
        return query.order_by(FactArticle.article_id).limit(max(1, min(limit, 1000))).all()

    def _candidate_count(self, db: Session, *, date_from: str | None, date_to: str | None, crawl_job_id: int | None = None) -> int:
        sql = """
            SELECT COUNT(DISTINCT a.article_id)
            FROM fact_article a
            JOIN fact_content_screening s ON s.article_id = a.article_id
            WHERE s.exclusive_right_candidate_yn = 1
              AND COALESCE(a.multi_company_article_yn, 0) = 0
        """
        params: dict[str, Any] = {}
        if crawl_job_id is not None:
            sql += " AND a.crawl_job_id = :crawl_job_id"
            params["crawl_job_id"] = crawl_job_id
        if date_from:
            sql += " AND a.pub_date >= :date_from"
            params["date_from"] = datetime.fromisoformat(date_from)
        if date_to:
            sql += " AND a.pub_date < :date_to"
            params["date_to"] = datetime.fromisoformat(date_to) + timedelta(days=1)
        return int(db.execute(text(sql), params).scalar() or 0)

    @staticmethod
    def _empty_extract_summary(mode: str, date_from: str | None, date_to: str | None) -> dict[str, Any]:
        return {
            "mode": mode,
            "date_from": date_from,
            "date_to": date_to,
            "candidate_count": 0,
            "processed": 0,
            "queued": 0,
            "queued_count": 0,
            "realtime_processed_count": 0,
            "saved": 0,
            "batch_eligible": 0,
            "batch_eligible_count": 0,
            "skipped_count": 0,
        }

    @staticmethod
    def _article_has_observation(db: Session, article_id: int) -> bool:
        return (
            db.query(FactExclusiveUseRightObservation)
            .filter(FactExclusiveUseRightObservation.article_id == article_id)
            .first()
            is not None
        )

    @staticmethod
    def _article_has_queue(db: Session, article_id: int, *, include_completed: bool) -> bool:
        statuses = ["pending", "running", "completed"] if include_completed else ["pending", "running"]
        return (
            db.query(FactLLMQueue)
            .filter(
                FactLLMQueue.target_type == "article",
                FactLLMQueue.target_id == article_id,
                FactLLMQueue.task_type == "exclusive_right_extract",
                FactLLMQueue.status.in_(statuses),
            )
            .first()
            is not None
        )

    @staticmethod
    def _existing_observation(
        db: Session,
        *,
        exclusive_right_id: int | None,
        article_id: int | None,
        subject_core_key: str | None,
    ) -> FactExclusiveUseRightObservation | None:
        query = db.query(FactExclusiveUseRightObservation).filter(FactExclusiveUseRightObservation.subject_core_key == subject_core_key)
        if article_id is not None:
            query = query.filter(FactExclusiveUseRightObservation.article_id == article_id)
        if exclusive_right_id is None:
            query = query.filter(FactExclusiveUseRightObservation.exclusive_right_id.is_(None))
        else:
            query = query.filter(FactExclusiveUseRightObservation.exclusive_right_id == exclusive_right_id)
        return query.first()

    def _observation_count_for_period(
        self,
        db: Session,
        *,
        date_from: str | None,
        date_to: str | None,
        crawl_job_id: int | None = None,
    ) -> int:
        query = db.query(FactExclusiveUseRightObservation)
        if crawl_job_id is not None or date_from or date_to:
            query = query.join(FactArticle, FactArticle.article_id == FactExclusiveUseRightObservation.article_id)
            if crawl_job_id is not None:
                query = query.filter(FactArticle.crawl_job_id == crawl_job_id)
            if date_from:
                query = query.filter(FactArticle.pub_date >= datetime.fromisoformat(date_from))
            if date_to:
                query = query.filter(FactArticle.pub_date < datetime.fromisoformat(date_to) + timedelta(days=1))
        return query.count()

    def _canonical_count_for_period(
        self,
        db: Session,
        *,
        date_from: str | None,
        date_to: str | None,
        crawl_job_id: int | None = None,
    ) -> int:
        query = db.query(FactExclusiveUseRight).filter(FactExclusiveUseRight.event_status != "merged")
        if crawl_job_id is not None or date_from or date_to:
            query = query.join(FactExclusiveUseRightArticle, FactExclusiveUseRightArticle.exclusive_right_id == FactExclusiveUseRight.exclusive_right_id)
            query = query.join(FactArticle, FactArticle.article_id == FactExclusiveUseRightArticle.article_id)
            if crawl_job_id is not None:
                query = query.filter(FactArticle.crawl_job_id == crawl_job_id)
            if date_from:
                query = query.filter(FactArticle.pub_date >= datetime.fromisoformat(date_from))
            if date_to:
                query = query.filter(FactArticle.pub_date < datetime.fromisoformat(date_to) + timedelta(days=1))
        return query.distinct().count()

    @staticmethod
    def _exclusive_snippet_text(article: FactArticle, snippets: list[Any]) -> str:
        exclusive_snippets = [
            snippet.snippet_text
            for snippet in snippets
            if str(snippet.snippet_type).startswith("exclusive_") or snippet.snippet_type == "exclusive_right"
        ]
        text_parts = [article.title, article.description, *exclusive_snippets]
        return "\n".join(str(part) for part in text_parts if part)

    def _link_article(self, db: Session, exclusive_right: FactExclusiveUseRight, article: FactArticle, confidence: float, evidence_summary: str | None) -> None:
        existing = (
            db.query(FactExclusiveUseRightArticle)
            .filter(
                FactExclusiveUseRightArticle.exclusive_right_id == exclusive_right.exclusive_right_id,
                FactExclusiveUseRightArticle.article_id == article.article_id,
            )
            .first()
        )
        if existing:
            existing.confidence = max(float(existing.confidence or 0), confidence)
            existing.evidence_summary = existing.evidence_summary or evidence_summary
            return
        db.add(
            FactExclusiveUseRightArticle(
                exclusive_right_id=exclusive_right.exclusive_right_id,
                article_id=article.article_id,
                confidence=confidence,
                evidence_summary=evidence_summary,
            )
        )

    def _upsert_alias(self, db: Session, exclusive_right: FactExclusiveUseRight, raw_subject_name: str, subject_core_key: str, article_id: int | None) -> None:
        existing = (
            db.query(FactExclusiveUseRightAlias)
            .filter(
                FactExclusiveUseRightAlias.exclusive_right_id == exclusive_right.exclusive_right_id,
                FactExclusiveUseRightAlias.subject_core_key == subject_core_key,
                FactExclusiveUseRightAlias.raw_subject_name == raw_subject_name,
            )
            .first()
        )
        if existing:
            existing.observation_count += 1
            existing.last_seen_at = datetime.utcnow()
            return
        db.add(
            FactExclusiveUseRightAlias(
                exclusive_right_id=exclusive_right.exclusive_right_id,
                raw_subject_name=raw_subject_name,
                normalized_subject_name_candidate=raw_subject_name,
                subject_core_key=subject_core_key,
                article_id=article_id,
            )
        )

    def _resolve_company(
        self,
        db: Session,
        raw_name: str | None,
        text_value: str,
        *,
        local_text: str | None = None,
        article_title: str | None = None,
        article_description: str | None = None,
        product_or_subject_name: str | None = None,
    ) -> ResolvedCompany:
        attribution = CompanyAttributionService(self.normalizer).resolve_company_for_context(
            db,
            raw_company_name=raw_name,
            local_text=local_text or text_value,
            article_title=article_title,
            article_description=article_description,
            full_text=text_value,
            association_hint=text_value,
            product_or_subject_name=product_or_subject_name,
        )
        if attribution.company_name_normalized:
            return ResolvedCompany(
                company_id=attribution.company_id,
                company_name_normalized=attribution.company_name_normalized,
                insurance_type=attribution.insurance_type or "unknown",
                confidence=attribution.confidence,
                evidence_text=attribution.matched_alias,
                needs_review=attribution.needs_review,
            )
        return ResolvedCompany(
            company_id=None,
            company_name_normalized=None,
            insurance_type="unknown",
            confidence=0.2 if self._is_non_insurer_org(raw_name) else 0.3,
            evidence_text=raw_name,
            needs_review=True,
        )

    @staticmethod
    def _first_company_match_in_text(matches: list[CompanyMatch], text_value: str) -> CompanyMatch | None:
        if not matches:
            return None
        text_key = normalize_search_key(text_value)

        def position(match: CompanyMatch) -> tuple[int, int]:
            candidates = [match.company_name_raw, match.company_name_normalized]
            positions = [text_key.find(normalize_search_key(value)) for value in candidates if value]
            positions = [value for value in positions if value >= 0]
            first = min(positions) if positions else 10**9
            return (first, -len(normalize_search_key(match.company_name_raw)))

        return sorted(matches, key=position)[0]

    def _apply_filters(self, query, **filters: Any):
        query = query.filter(FactExclusiveUseRight.event_status.notin_(["merged", "rejected", "rejected_multi_company_only"]))
        query = query.filter(
            or_(
                FactExclusiveUseRight.exclusive_right_id.in_(
                    select(FactExclusiveUseRightArticle.exclusive_right_id)
                    .join(FactArticle, FactArticle.article_id == FactExclusiveUseRightArticle.article_id)
                    .where(FactArticle.multi_company_article_yn == False)  # noqa: E712
                ),
                ~FactExclusiveUseRight.exclusive_right_id.in_(
                    select(FactExclusiveUseRightArticle.exclusive_right_id)
                ),
            )
        )
        insurance_type = filters.get("insurance_type")
        if insurance_type not in ALL_INSURANCE_TYPE_VALUES:
            query = query.filter(FactExclusiveUseRight.insurance_type == insurance_type)
        if filters.get("company_id"):
            query = query.filter(FactExclusiveUseRight.company_id == int(filters["company_id"]))
        names = self._normalized_company_names(filters.get("company_name"), filters.get("company_names"))
        if names:
            query = query.filter(FactExclusiveUseRight.company_name_normalized.in_(names))
        if filters.get("acquired_year_month_from"):
            query = query.filter(FactExclusiveUseRight.acquired_year_month >= filters["acquired_year_month_from"])
        if filters.get("acquired_year_month_to"):
            query = query.filter(FactExclusiveUseRight.acquired_year_month <= filters["acquired_year_month_to"])
        if filters.get("months_back"):
            cutoff = (datetime.now() - timedelta(days=max(1, int(filters["months_back"])) * 31)).strftime("%Y-%m")
            query = query.filter(FactExclusiveUseRight.acquired_year_month >= cutoff)
        if not filters.get("include_review"):
            query = query.filter(FactExclusiveUseRight.needs_review.is_(False))
        keyword = compact_spaces(filters.get("keyword"))
        if keyword:
            keyword_like = f"%{keyword.lower()}%"
            compact_like = f"%{normalize_search_key(keyword)}%"
            query = query.filter(
                or_(
                    FactExclusiveUseRight.subject_name.ilike(keyword_like),
                    FactExclusiveUseRight.feature_summary.ilike(keyword_like),
                    FactExclusiveUseRight.company_name_normalized.ilike(keyword_like),
                    FactExclusiveUseRight.primary_article_title.ilike(keyword_like),
                    FactExclusiveUseRight.primary_article_url.ilike(keyword_like),
                    FactExclusiveUseRight.evidence_text.ilike(keyword_like),
                    FactExclusiveUseRight.evidence_summary.ilike(keyword_like),
                    FactExclusiveUseRight.alias_names_json.ilike(keyword_like),
                    FactExclusiveUseRight.subject_core_key.ilike(compact_like),
                    FactExclusiveUseRight.exclusive_right_id.in_(
                        select(FactExclusiveUseRightAlias.exclusive_right_id).where(
                            or_(
                                FactExclusiveUseRightAlias.raw_subject_name.ilike(keyword_like),
                                FactExclusiveUseRightAlias.normalized_subject_name_candidate.ilike(keyword_like),
                                FactExclusiveUseRightAlias.subject_core_key.ilike(compact_like),
                            )
                        )
                    ),
                    FactExclusiveUseRight.exclusive_right_id.in_(
                        select(FactExclusiveUseRightObservation.exclusive_right_id).where(
                            or_(
                                FactExclusiveUseRightObservation.evidence_text.ilike(keyword_like),
                                FactExclusiveUseRightObservation.article_title.ilike(keyword_like),
                                FactExclusiveUseRightObservation.raw_subject_name.ilike(keyword_like),
                                FactExclusiveUseRightObservation.normalized_subject_name_candidate.ilike(keyword_like),
                                FactExclusiveUseRightObservation.subject_core_key.ilike(compact_like),
                            )
                        )
                    ),
                )
            )
        return query

    def _normalized_company_names(self, company_name: str | None, company_names: list[str] | None) -> list[str]:
        names: list[str] = []
        raw_values = []
        if company_name:
            raw_values.append(company_name)
        raw_values.extend(company_names or [])
        for value in raw_values:
            for part in str(value).split(","):
                part = compact_spaces(part)
                if not part:
                    continue
                match = self.normalizer.normalize(part)
                if match and match.is_known_insurer and match.company_name_normalized:
                    names.append(match.company_name_normalized)
                else:
                    names.append(part)
        return sorted(set(names))

    def _find_canonical(
        self,
        db: Session,
        company_id: int | None,
        company_name_normalized: str | None,
        subject_core_key: str,
        acquired_year_month: str | None,
        exclusivity_months: int | None = None,
    ) -> FactExclusiveUseRight | None:
        query = db.query(FactExclusiveUseRight).filter(FactExclusiveUseRight.subject_core_key == subject_core_key)
        if company_id is not None:
            query = query.filter(FactExclusiveUseRight.company_id == company_id)
        else:
            query = query.filter(FactExclusiveUseRight.company_id.is_(None), FactExclusiveUseRight.company_name_normalized == company_name_normalized)
        if acquired_year_month:
            query = query.filter(FactExclusiveUseRight.acquired_year_month == acquired_year_month)
        if exclusivity_months is not None:
            query = query.filter(FactExclusiveUseRight.exclusivity_months == exclusivity_months)
        return query.first()

    def _list_item(self, row: FactExclusiveUseRight) -> dict[str, Any]:
        return {
            "exclusive_right_id": row.exclusive_right_id,
            "insurance_type": row.insurance_type or "unknown",
            "company_id": row.company_id,
            "company_name": row.company_name_normalized,
            "company_name_normalized": row.company_name_normalized,
            "subject_name": row.subject_name,
            "exclusivity_months": row.exclusivity_months,
            "acquired_year_month": row.acquired_year_month,
            "feature_summary": row.feature_summary,
            "evidence_summary": row.evidence_summary,
            "article_title": row.primary_article_title,
            "primary_article_title": row.primary_article_title,
            "primary_article_url": row.primary_article_url,
            "alias_names": "\n".join(self._json_load(row.alias_names_json)),
            "evidence_text": row.evidence_text,
        }

    @staticmethod
    def _is_public_subject(row: FactExclusiveUseRight) -> bool:
        subject = row.subject_name
        if is_generic_or_weak_subject(subject) or has_bad_subject_tail(subject):
            return False
        if not looks_like_formal_exclusive_subject(subject):
            return False
        return True

    def _company_by_normalized(self, db: Session, normalized: str) -> DimCompany | None:
        return db.query(DimCompany).filter(DimCompany.company_name_normalized == normalized).first()

    @staticmethod
    def _looks_like_exclusive_right(text_value: str) -> bool:
        text = compact_spaces(text_value)
        return any(keyword in text for keyword in EXCLUSIVE_KEYWORDS) and any(keyword in text for keyword in ACQUIRED_KEYWORDS)

    def _extract_minimal_payload(self, text: str, article: FactArticle | None) -> dict[str, Any]:
        best_window = select_best_exclusive_context_window(
            None,
            None,
            text,
            article_title=article.title if article else None,
            article_description=article.description if article else None,
        )
        window_text = best_window.window_text if best_window else text
        evidence_text = best_window.evidence_text if best_window else text
        subject_name = self._extract_subject_name(window_text)
        months_match = re.search(r"(\d{1,2})\s*\uac1c\uc6d4", window_text)
        acquired_year_month = parse_explicit_acquired_year_month(window_text, article.pub_date if article else None) or self._article_year_month(article)
        return {
            "company_name_raw": self._extract_company_phrase(evidence_text) or self._extract_company_phrase(window_text),
            "subject_name": subject_name,
            "exclusivity_months": int(months_match.group(1)) if months_match else None,
            "acquired_year_month": acquired_year_month,
            "feature_summary": self._truncate(window_text, 220),
            "evidence_summary": self._truncate(window_text, 220),
            "evidence_text": self._truncate(evidence_text or window_text, 500),
            "article_title": article.title if article else None,
            "article_url": self._article_url(article),
        }

    @staticmethod
    def _extract_subject_name(text: str) -> str:
        resolved = resolve_subject_reference(None, text)
        if resolved:
            return resolved
        target = re.search(r"(?:은|는)\s+(.{2,80}?)(?:에 대해|에 대한|으로|로)\s+\d{0,2}\s*개월?\s*배타적\s*사용권", text)
        if target:
            return compact_spaces(target.group(1))
        target = re.search(r"(.{2,80}?)(?:에 대해|에 대한)\s+배타적\s*사용권", text)
        if target:
            return compact_spaces(target.group(1))
        return "배타적사용권 대상 미확인"

    @staticmethod
    def _extract_company_phrase(text: str) -> str | None:
        match = re.search(r"^\s*([가-힣A-Za-z0-9+ ]{2,30}?)(?:은|는|이|가)\s", text)
        return compact_spaces(match.group(1)) if match else None

    @staticmethod
    def _normalize_year_month(value: str | None) -> str | None:
        if not value:
            return None
        digits = re.findall(r"\d+", value)
        if len(digits) >= 2 and len(digits[0]) == 4:
            return f"{digits[0]}-{int(digits[1]):02d}"
        return value if re.fullmatch(r"\d{4}-\d{2}", value) else None

    def _local_context_text(self, payload: dict[str, Any], *, article: FactArticle | None, full_text: str | None) -> str:
        source_text = compact_spaces(
            "\n".join(
                str(value)
                for value in [
                    full_text,
                    payload.get("evidence_text"),
                    payload.get("evidence_summary"),
                    payload.get("feature_summary"),
                    article.description if article else None,
                ]
                if value
            )
        )
        best_window = select_best_exclusive_context_window(
            payload.get("subject_name"),
            payload.get("evidence_text") or payload.get("evidence_summary"),
            source_text,
            article_title=article.title if article else payload.get("article_title"),
            article_description=article.description if article else None,
            company_name=payload.get("company_name_candidate") or payload.get("company_name_raw"),
            exclusivity_months=self._nullable_int(payload.get("exclusivity_months")),
        )
        if best_window:
            return best_window.window_text
        return compact_spaces(
            "\n".join(
                str(value)
                for value in [
                    payload.get("evidence_text"),
                    payload.get("feature_summary"),
                    article.description if article else None,
                    article.title if article else payload.get("article_title"),
                ]
                if value
            )
        )

    def _resolve_acquired_year_month_for_payload(
        self,
        payload: dict[str, Any],
        *,
        article: FactArticle | None,
        context_text: str | None,
    ) -> str | None:
        explicit = parse_explicit_acquired_year_month(context_text, article.pub_date if article else None)
        if explicit:
            return explicit
        payload_month = self._normalize_year_month(payload.get("acquired_year_month"))
        if is_valid_year_month(payload_month):
            return payload_month
        return self._article_year_month(article)

    def _refresh_canonical_acquired_month(self, db: Session, exclusive_right: FactExclusiveUseRight) -> None:
        observations = (
            db.query(FactExclusiveUseRightObservation)
            .filter(FactExclusiveUseRightObservation.exclusive_right_id == exclusive_right.exclusive_right_id)
            .all()
        )
        explicit_months: list[str] = []
        articles: list[FactArticle] = []
        for observation in observations:
            article = db.get(FactArticle, observation.article_id) if observation.article_id else None
            if article:
                articles.append(article)
            parsed = parse_explicit_acquired_year_month(observation.evidence_text, article.pub_date if article else None)
            if parsed:
                explicit_months.append(parsed)
        chosen = sorted(set(explicit_months))[0] if explicit_months else fallback_earliest_article_month(articles)
        if chosen and is_valid_year_month(chosen):
            exclusive_right.acquired_year_month = chosen

    @staticmethod
    def _should_replace_canonical_subject(current: str | None, candidate: str | None) -> bool:
        if not candidate:
            return False
        if is_weak_subject(current):
            return True
        current_key = normalize_search_key(current)
        candidate_key = normalize_search_key(candidate)
        return len(candidate_key) > len(current_key) + 4 and current_key in candidate_key

    @staticmethod
    def _article_year_month(article: FactArticle | None) -> str | None:
        if article and article.pub_date:
            return article.pub_date.strftime("%Y-%m")
        return None

    @staticmethod
    def _article_url(article: FactArticle | None) -> str | None:
        if not article:
            return None
        return article.original_url or article.url

    @staticmethod
    def _nullable_int(value: Any) -> int | None:
        if value in {None, ""}:
            return None
        if isinstance(value, str):
            match = re.search(r"\d+", value)
            return int(match.group(0)) if match else None
        return int(value)

    @staticmethod
    def _truncate(value: str | None, limit: int) -> str | None:
        cleaned = compact_spaces(value)
        if not cleaned:
            return None
        return cleaned if len(cleaned) <= limit else cleaned[:limit].rstrip() + "..."

    @staticmethod
    def _json_list(values: list[str]) -> str:
        return json.dumps([value for value in values if value], ensure_ascii=False)

    @staticmethod
    def _json_load(value: str | None) -> list[str]:
        if not value:
            return []
        try:
            payload = json.loads(value)
            return [str(item) for item in payload if item]
        except json.JSONDecodeError:
            return []

    @staticmethod
    def _observation_count(db: Session, exclusive_right_id: int) -> int:
        return (
            db.query(FactExclusiveUseRightObservation)
            .filter(FactExclusiveUseRightObservation.exclusive_right_id == exclusive_right_id)
            .count()
        )

    @staticmethod
    def _is_non_insurer_org(value: str | None) -> bool:
        text = compact_spaces(value)
        return bool(text and any(pattern.fullmatch(text) for pattern in NON_INSURER_PATTERNS))
