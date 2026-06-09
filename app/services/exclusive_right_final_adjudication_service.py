from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.db.models import DimCompany, FactArticle
from app.services.article_eligibility_filter_service import ArticleEligibilityDecision, ArticleEligibilityFilterService
from app.services.company_attribution_service import CompanyAttributionService
from app.services.exclusive_right_local_context import validate_exclusive_subject_before_save
from app.services.product_company_eligibility import is_product_news_eligible_company
from app.utils.text import compact_spaces


EXCLUSIVE_RIGHT_FINAL_ADJUDICATION_TASK_TYPE = "exclusive_right_final_adjudication"
EXCLUSIVE_RIGHT_FINAL_ADJUDICATION_SCHEMA_VERSION = "2026-06-07-v1"

EXCLUSIVE_RIGHT_FINAL_DECISIONS = {"accept", "reject", "review", "reassign_company", "ineligible_article"}


class ExclusiveRightFinalAdjudicationProvider(Protocol):
    def adjudicate_exclusive_right(self, payload: dict[str, Any]) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class ExclusiveRightFinalAdjudicationInput:
    current_subject_name: str
    current_company: str | None = None
    acquired_year_month: str | None = None
    exclusivity_months: int | None = None
    representative_article: dict[str, Any] = field(default_factory=dict)
    evidence_text: str | None = None
    article_eligibility_decision: ArticleEligibilityDecision | None = None


@dataclass(frozen=True)
class ExclusiveRightFinalAdjudicationDecision:
    decision: str
    subject_name: str | None
    company_name: str | None
    acquired_year_month: str | None = None
    reason: str = ""
    evidence_quote: str | None = None
    confidence: float = 0.0
    provider_called: bool = False


class ExclusiveRightFinalAdjudicationService:
    """Final exclusive-right guard over compact article context."""

    def __init__(
        self,
        *,
        provider: ExclusiveRightFinalAdjudicationProvider | None = None,
        article_filter: ArticleEligibilityFilterService | None = None,
        company_attribution: CompanyAttributionService | None = None,
        force_provider: bool = False,
    ) -> None:
        self.provider = provider
        self.article_filter = article_filter or ArticleEligibilityFilterService()
        self.company_attribution = company_attribution or CompanyAttributionService()
        self.force_provider = force_provider
        self.provider_call_count = 0

    def build_input(
        self,
        db: Session,
        *,
        subject_name: str,
        company_name: str | None = None,
        acquired_year_month: str | None = None,
        exclusivity_months: int | None = None,
        article: FactArticle | None = None,
        context_text: str | None = None,
        evidence_text: str | None = None,
    ) -> ExclusiveRightFinalAdjudicationInput:
        return ExclusiveRightFinalAdjudicationInput(
            current_subject_name=subject_name,
            current_company=company_name,
            acquired_year_month=acquired_year_month,
            exclusivity_months=exclusivity_months,
            representative_article=self._representative_article_payload(article, context_text),
            evidence_text=evidence_text,
            article_eligibility_decision=self.article_filter.classify_article(db, article) if article else None,
        )

    def adjudicate(self, db: Session, payload: ExclusiveRightFinalAdjudicationInput) -> ExclusiveRightFinalAdjudicationDecision:
        article_decision = payload.article_eligibility_decision
        context_text = self._context_from_payload(payload)
        if article_decision and not article_decision.is_eligible:
            return ExclusiveRightFinalAdjudicationDecision(
                decision="ineligible_article",
                subject_name=None,
                company_name=None,
                acquired_year_month=payload.acquired_year_month,
                reason=article_decision.exclusion_reason or "article_ineligible",
                confidence=article_decision.confidence,
            )

        subject_validation = validate_exclusive_subject_before_save(
            payload.current_subject_name,
            evidence_text=payload.evidence_text,
            window_text=context_text,
            article_title=str(payload.representative_article.get("title") or ""),
        )
        attribution = self.company_attribution.resolve_company_for_context(
            db,
            raw_company_name=payload.current_company,
            local_text=context_text,
            article_title=str(payload.representative_article.get("title") or ""),
            product_or_subject_name=subject_validation.subject_name or payload.current_subject_name,
        )
        company_row = db.get(DimCompany, attribution.company_id) if attribution.company_id else None
        risky = bool(
            self.force_provider
            or subject_validation.needs_review
            or subject_validation.status != "pass"
            or (article_decision is not None and not article_decision.is_eligible)
            or self._future_month(payload.acquired_year_month, payload.representative_article)
            or attribution.needs_review
            or (payload.current_company and not is_product_news_eligible_company(company_row))
        )
        provider_output: dict[str, Any] | None = None
        provider_called = False
        if risky and self.provider is not None:
            provider_called = True
            self.provider_call_count += 1
            provider_output = self.provider.adjudicate_exclusive_right(self._provider_payload(payload))

        candidate = self._decision_from_provider(provider_output) if provider_output else None
        candidate = self._coerce_recoverable_reject(candidate, payload, article_decision)
        candidate = self._require_subject_name_for_provider_subject_correction(candidate, payload)
        if candidate and candidate.decision in {"accept", "reassign_company"}:
            subject_name = candidate.subject_name or subject_validation.subject_name
            post_subject = validate_exclusive_subject_before_save(
                subject_name,
                evidence_text=candidate.evidence_quote or payload.evidence_text,
                window_text=context_text,
                article_title=str(payload.representative_article.get("title") or ""),
            )
            if post_subject.needs_review or not post_subject.subject_name:
                return ExclusiveRightFinalAdjudicationDecision(
                    decision="review",
                    subject_name=post_subject.subject_name,
                    company_name=candidate.company_name or payload.current_company,
                    acquired_year_month=candidate.acquired_year_month or payload.acquired_year_month,
                    reason=f"provider_output_failed_subject_validator:{post_subject.reason}",
                    confidence=min(candidate.confidence, 0.5),
                    provider_called=provider_called,
                )
            attribution = self.company_attribution.resolve_company_for_context(
                db,
                raw_company_name=candidate.company_name or payload.current_company,
                local_text=context_text,
                article_title=str(payload.representative_article.get("title") or ""),
                product_or_subject_name=post_subject.subject_name,
            )
            company_row = db.get(DimCompany, attribution.company_id) if attribution.company_id else None
            if not is_product_news_eligible_company(company_row):
                return ExclusiveRightFinalAdjudicationDecision(
                    decision="review",
                    subject_name=post_subject.subject_name,
                    company_name=attribution.company_name_normalized,
                    acquired_year_month=candidate.acquired_year_month or payload.acquired_year_month,
                    reason="company_is_reinsurer_or_foreign_branch",
                    confidence=min(candidate.confidence, 0.5),
                    provider_called=provider_called,
                )
            month = candidate.acquired_year_month or payload.acquired_year_month
            if self._future_month(month, payload.representative_article):
                return ExclusiveRightFinalAdjudicationDecision(
                    decision="review",
                    subject_name=post_subject.subject_name,
                    company_name=attribution.company_name_normalized,
                    acquired_year_month=month,
                    reason="exclusive_right_future_acquired_month",
                    confidence=min(candidate.confidence, 0.5),
                    provider_called=provider_called,
                )
            return ExclusiveRightFinalAdjudicationDecision(
                decision="accept",
                subject_name=post_subject.subject_name,
                company_name=attribution.company_name_normalized or candidate.company_name,
                acquired_year_month=month,
                reason=candidate.reason,
                evidence_quote=candidate.evidence_quote,
                confidence=candidate.confidence,
                provider_called=provider_called,
            )
        if candidate:
            return ExclusiveRightFinalAdjudicationDecision(**{**candidate.__dict__, "provider_called": provider_called})

        if subject_validation.needs_review or not subject_validation.subject_name:
            return ExclusiveRightFinalAdjudicationDecision(
                decision="review",
                subject_name=subject_validation.subject_name,
                company_name=payload.current_company,
                acquired_year_month=payload.acquired_year_month,
                reason=subject_validation.reason,
                confidence=0.5,
                provider_called=provider_called,
            )
        if self._future_month(payload.acquired_year_month, payload.representative_article):
            return ExclusiveRightFinalAdjudicationDecision(
                decision="review",
                subject_name=subject_validation.subject_name,
                company_name=payload.current_company,
                acquired_year_month=payload.acquired_year_month,
                reason="exclusive_right_future_acquired_month",
                confidence=0.5,
                provider_called=provider_called,
            )
        return ExclusiveRightFinalAdjudicationDecision(
            decision="accept",
            subject_name=subject_validation.subject_name,
            company_name=payload.current_company,
            acquired_year_month=payload.acquired_year_month,
            reason="deterministic_validators_passed",
            confidence=0.8,
            provider_called=provider_called,
        )

    @staticmethod
    def _representative_article_payload(article: FactArticle | None, context_text: str | None) -> dict[str, Any]:
        if article is None:
            return {"local_exclusive_windows": [compact_spaces(context_text)[:1200]] if context_text else []}
        return {
            "title": article.title,
            "url": article.original_url or article.url,
            "pub_date": article.pub_date.isoformat() if article.pub_date else None,
            "local_exclusive_windows": [compact_spaces(context_text)[:1200]] if context_text else [],
        }

    @staticmethod
    def _context_from_payload(payload: ExclusiveRightFinalAdjudicationInput) -> str:
        article = payload.representative_article or {}
        parts = [
            str(article.get("title") or ""),
            *[str(item) for item in article.get("local_exclusive_windows") or []],
            payload.evidence_text or "",
        ]
        return compact_spaces(" ".join(part for part in parts if part))[:2400]

    @staticmethod
    def _provider_payload(payload: ExclusiveRightFinalAdjudicationInput) -> dict[str, Any]:
        article_decision = payload.article_eligibility_decision
        return {
            "task_type": EXCLUSIVE_RIGHT_FINAL_ADJUDICATION_TASK_TYPE,
            "schema_version": EXCLUSIVE_RIGHT_FINAL_ADJUDICATION_SCHEMA_VERSION,
            "current_subject_name": payload.current_subject_name,
            "current_company": payload.current_company,
            "acquired_year_month": payload.acquired_year_month,
            "exclusivity_months": payload.exclusivity_months,
            "representative_article": payload.representative_article,
            "evidence_text": payload.evidence_text,
            "article_eligibility_decision": article_decision.__dict__ if article_decision else None,
        }

    @staticmethod
    def _future_month(month: str | None, article_payload: dict[str, Any]) -> bool:
        if not month or len(month) != 7:
            return False
        pub_date = article_payload.get("pub_date")
        if not pub_date:
            return False
        try:
            pub_month = datetime.fromisoformat(str(pub_date)).strftime("%Y-%m")
        except ValueError:
            return False
        return month > pub_month

    @staticmethod
    def _coerce_recoverable_reject(
        candidate: ExclusiveRightFinalAdjudicationDecision | None,
        payload: ExclusiveRightFinalAdjudicationInput,
        article_decision: ArticleEligibilityDecision | None,
    ) -> ExclusiveRightFinalAdjudicationDecision | None:
        if candidate is None or candidate.decision != "reject":
            return candidate
        if article_decision and not article_decision.is_eligible:
            return candidate
        reason = (candidate.reason or "").casefold()
        discard_markers = (
            "ineligible",
            "multi_company",
            "not exclusive",
            "no exclusive",
            "non-exclusive",
            "unrecoverable",
            "non_insurance",
            "non-insurance",
            "does not mention the current subject",
            "doesn't mention the current subject",
            "no mention of the current subject",
            "no mention of any exclusive",
            "no reference to any exclusive",
        )
        unsupported_discard_markers = (
            "zero textual reference",
            "zero description",
            "does not reference",
            "doesn't reference",
            "does not mention",
            "doesn't mention",
            "makes no mention",
            "no mention",
            "provides no mention",
            "does not describe",
            "doesn't describe",
            "does not name",
            "doesn't name",
            "no evidence supports",
            "does not mention the current subject",
            "doesn't mention the current subject",
            "no mention of the current subject",
            "no mention of any exclusive",
            "no reference to any exclusive",
            "no textual evidence",
            "zero textual evidence",
            "no reference",
            "no support in the article",
            "unsupported by any evidence",
            "unsupported by the local context",
            "unsupported by evidence",
            "unsupported by textual evidence",
            "unsupported subject attribution",
            "fails mutual support",
            "lack evidentiary support",
            "lacks evidentiary support",
            "exclusively discusses",
            "does not constitute exclusive-right coverage",
            "not ambiguous or correctable",
            "not correctable",
        )
        if any(marker in reason for marker in discard_markers):
            return candidate
        if ExclusiveRightFinalAdjudicationService._reason_says_current_subject_is_unsupported(
            reason,
            payload.current_subject_name,
        ):
            return candidate
        has_correction = any(
            [
                candidate.subject_name and candidate.subject_name != payload.current_subject_name,
                candidate.company_name and candidate.company_name != payload.current_company,
                candidate.acquired_year_month and candidate.acquired_year_month != payload.acquired_year_month,
            ]
        )
        if has_correction and candidate.confidence >= 0.75:
            return replace(candidate, decision="accept", reason=f"recoverable_field_correction:{candidate.reason}")
        recoverable_review_markers = (
            "genuine exclusive",
            "exclusive-use-right event",
            "exclusive right event",
            "article confirms",
            "article supports",
            "subject-related",
            "field correction",
            "current subject",
            "current company",
            "company attribution",
            "acquired month",
            "acquired date",
            "future acquired",
            "correction is uncertain",
            "partial exclusive-right evidence",
        )
        if not has_correction and not any(marker in reason for marker in recoverable_review_markers):
            return candidate
        return replace(
            candidate,
            decision="review",
            reason=f"recoverable_exclusive_right_needs_review:{candidate.reason}",
            confidence=min(candidate.confidence, 0.65),
        )

    @staticmethod
    def _reason_says_current_subject_is_unsupported(reason: str, current_subject_name: str | None) -> bool:
        subject = (current_subject_name or "").casefold().strip()
        if not reason or not subject or subject not in reason:
            return False
        negative_markers = (
            "no ",
            "zero ",
            "does not ",
            "doesn't ",
            "unsupported",
        )
        support_terms = (
            "mention",
            "reference",
            "describe",
            "support",
            "evidence",
            "name",
            "subject",
            "exclusive",
            "right",
            "event",
            "approval",
        )
        for index in ExclusiveRightFinalAdjudicationService._find_all(reason, subject):
            window = reason[max(0, index - 100) : index + len(subject) + 140]
            if any(marker in window for marker in negative_markers) and any(term in window for term in support_terms):
                return True
        return False

    @staticmethod
    def _require_subject_name_for_provider_subject_correction(
        candidate: ExclusiveRightFinalAdjudicationDecision | None,
        payload: ExclusiveRightFinalAdjudicationInput,
    ) -> ExclusiveRightFinalAdjudicationDecision | None:
        if candidate is None or candidate.decision not in {"accept", "reassign_company"}:
            return candidate
        current = compact_spaces(payload.current_subject_name or "").casefold()
        subject = compact_spaces(candidate.subject_name or "").casefold()
        reason = (candidate.reason or "").casefold()
        correction_markers = (
            "current subject",
            "current name",
            "incorrect",
            "not canonical",
            "descriptive phrase",
            "generic descriptor",
            "generic",
            "fragment",
            "sentence-fragment",
            "unsupported",
            "corrected",
            "subject should be",
            "should be corrected",
        )
        if not any(marker in reason for marker in correction_markers):
            return candidate
        if subject and subject != current:
            return candidate
        return ExclusiveRightFinalAdjudicationDecision(
            decision="review",
            subject_name=candidate.subject_name,
            company_name=candidate.company_name or payload.current_company,
            acquired_year_month=candidate.acquired_year_month or payload.acquired_year_month,
            reason="provider_missing_subject_name_for_subject_correction",
            evidence_quote=candidate.evidence_quote,
            confidence=min(candidate.confidence, 0.5),
            provider_called=candidate.provider_called,
        )

    @staticmethod
    def _find_all(text: str, pattern: str) -> list[int]:
        indices: list[int] = []
        start = 0
        while True:
            index = text.find(pattern, start)
            if index < 0:
                return indices
            indices.append(index)
            start = index + max(1, len(pattern))

    @staticmethod
    def _decision_from_provider(output: dict[str, Any] | None) -> ExclusiveRightFinalAdjudicationDecision | None:
        if not output:
            return None
        decision = str(output.get("decision") or "review")
        if decision not in EXCLUSIVE_RIGHT_FINAL_DECISIONS:
            decision = "review"
        confidence = float(output.get("confidence") or 0.0)
        return ExclusiveRightFinalAdjudicationDecision(
            decision=decision,
            subject_name=ExclusiveRightFinalAdjudicationService._optional_text(output.get("subject_name")),
            company_name=ExclusiveRightFinalAdjudicationService._optional_text(output.get("company_name")),
            acquired_year_month=ExclusiveRightFinalAdjudicationService._optional_text(output.get("acquired_year_month")),
            reason=ExclusiveRightFinalAdjudicationService._optional_text(output.get("reason")) or "provider_adjudication",
            evidence_quote=ExclusiveRightFinalAdjudicationService._optional_text(output.get("evidence_quote")),
            confidence=max(0.0, min(1.0, confidence)),
            provider_called=True,
        )

    @staticmethod
    def _optional_text(value: Any) -> str | None:
        if value is None or isinstance(value, bool):
            return None
        text = compact_spaces(str(value))
        return text or None

    @staticmethod
    def to_json(decision: ExclusiveRightFinalAdjudicationDecision) -> str:
        return json.dumps(decision.__dict__, ensure_ascii=False)
