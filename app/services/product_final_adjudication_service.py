from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.db.models import FactArticle
from app.services.article_eligibility_filter_service import ArticleEligibilityDecision, ArticleEligibilityFilterService
from app.services.company_attribution_service import CompanyAttributionService
from app.services.product_name_validation_service import ProductNameValidationService
from app.services.release_month_resolver import is_valid_year_month
from app.utils.text import compact_spaces


PRODUCT_FINAL_ADJUDICATION_TASK_TYPE = "product_final_adjudication"
PRODUCT_FINAL_ADJUDICATION_SCHEMA_VERSION = "2026-06-07-v1"

PRODUCT_FINAL_DECISIONS = {
    "accept",
    "reject",
    "review",
    "reassign_company",
    "alias_only",
    "non_insurance",
    "ineligible_article",
}


class ProductFinalAdjudicationProvider(Protocol):
    def adjudicate_product(self, payload: dict[str, Any]) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class ProductFinalAdjudicationInput:
    current_product_name: str
    current_company: str | None = None
    current_product_type: str | None = None
    current_release_year_month: str | None = None
    current_release_year_month_basis: str | None = None
    partner_company_name: str | None = None
    partner_role: str | None = None
    partner_context_summary: str | None = None
    candidate_type: str | None = None
    representative_article: dict[str, Any] = field(default_factory=dict)
    related_article_titles: list[str] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)
    article_eligibility_decision: ArticleEligibilityDecision | None = None


@dataclass(frozen=True)
class ProductFinalAdjudicationDecision:
    decision: str
    canonical_product_name: str | None
    company_name: str | None
    insurance_type: str | None = None
    product_type_code: str | None = None
    release_year_month: str | None = None
    release_year_month_basis: str | None = None
    partner_company_name: str | None = None
    partner_role: str | None = None
    article_suitability: str | None = None
    correction_summary: str | None = None
    reason: str = ""
    evidence_quote: str | None = None
    confidence: float = 0.0
    provider_called: bool = False


class ProductFinalAdjudicationService:
    """Compact-context final product adjudication with deterministic guardrails."""

    def __init__(
        self,
        *,
        provider: ProductFinalAdjudicationProvider | None = None,
        name_validator: ProductNameValidationService | None = None,
        article_filter: ArticleEligibilityFilterService | None = None,
        company_attribution: CompanyAttributionService | None = None,
        force_provider: bool = False,
    ) -> None:
        self.provider = provider
        self.name_validator = name_validator or ProductNameValidationService()
        self.article_filter = article_filter or ArticleEligibilityFilterService()
        self.company_attribution = company_attribution or CompanyAttributionService()
        self.force_provider = force_provider
        self.provider_call_count = 0

    def build_input(
        self,
        db: Session,
        *,
        product_name: str,
        company_name: str | None = None,
        product_type_code: str | None = None,
        release_year_month: str | None = None,
        release_year_month_basis: str | None = None,
        partner_company_name: str | None = None,
        partner_role: str | None = None,
        partner_context_summary: str | None = None,
        candidate_type: str | None = None,
        article: FactArticle | None = None,
        context_text: str | None = None,
        aliases: list[str] | None = None,
    ) -> ProductFinalAdjudicationInput:
        article_decision = self.article_filter.classify_article(db, article) if article else None
        return ProductFinalAdjudicationInput(
            current_product_name=product_name,
            current_company=company_name,
            current_product_type=product_type_code,
            current_release_year_month=release_year_month,
            current_release_year_month_basis=release_year_month_basis,
            partner_company_name=partner_company_name,
            partner_role=partner_role,
            partner_context_summary=partner_context_summary,
            candidate_type=candidate_type,
            representative_article=self._representative_article_payload(article, context_text),
            related_article_titles=[article.title] if article and article.title else [],
            aliases=aliases or [],
            article_eligibility_decision=article_decision,
        )

    def adjudicate(self, db: Session, payload: ProductFinalAdjudicationInput) -> ProductFinalAdjudicationDecision:
        article_decision = payload.article_eligibility_decision
        context_text = self._context_from_payload(payload)
        if article_decision and not article_decision.is_eligible:
            return ProductFinalAdjudicationDecision(
                decision="ineligible_article",
                canonical_product_name=None,
                company_name=None,
                reason=article_decision.exclusion_reason or "article_ineligible",
                confidence=article_decision.confidence,
            )

        name_decision = self.name_validator.validate(
            payload.current_product_name,
            article_title=str(payload.representative_article.get("title") or ""),
            evidence_text=context_text,
            context_text=context_text,
        )
        risky = self.force_provider or self.requires_llm_adjudication(
            payload,
            name_reason=name_decision.reason,
            removed_prefixes=name_decision.removed_prefixes,
        )
        provider_output: dict[str, Any] | None = None
        provider_called = False
        if risky and self.provider is not None:
            provider_called = True
            self.provider_call_count += 1
            provider_output = self.provider.adjudicate_product(self._provider_payload(payload))

        candidate = self._decision_from_provider(provider_output) if provider_output else None
        candidate = self._coerce_recoverable_reject(candidate, payload, article_decision)
        candidate = self._reject_provider_accept_for_wrong_current_identity(candidate, payload)
        if candidate and candidate.decision in {"accept", "reassign_company", "alias_only"}:
            final_name = candidate.canonical_product_name or payload.current_product_name
            final_name_decision = self.name_validator.validate(
                final_name,
                article_title=str(payload.representative_article.get("title") or ""),
                evidence_text=candidate.evidence_quote or context_text,
                context_text=context_text,
            )
            if not final_name_decision.accepted:
                return ProductFinalAdjudicationDecision(
                    decision="review",
                    canonical_product_name=final_name_decision.cleaned_name,
                    company_name=candidate.company_name or payload.current_company,
                    release_year_month=candidate.release_year_month or payload.current_release_year_month,
                    release_year_month_basis=candidate.release_year_month_basis or payload.current_release_year_month_basis,
                    partner_company_name=candidate.partner_company_name or payload.partner_company_name,
                    partner_role=candidate.partner_role or payload.partner_role,
                    reason=f"provider_output_failed_name_validator:{final_name_decision.reason}",
                    confidence=min(candidate.confidence, 0.5),
                    provider_called=provider_called,
                )
            if candidate.release_year_month and not is_valid_year_month(candidate.release_year_month):
                return ProductFinalAdjudicationDecision(
                    decision="review",
                    canonical_product_name=final_name_decision.cleaned_name,
                    company_name=candidate.company_name or payload.current_company,
                    release_year_month=candidate.release_year_month,
                    release_year_month_basis=candidate.release_year_month_basis or payload.current_release_year_month_basis,
                    partner_company_name=candidate.partner_company_name or payload.partner_company_name,
                    partner_role=candidate.partner_role or payload.partner_role,
                    reason="provider_output_failed_release_month_validator",
                    confidence=min(candidate.confidence, 0.5),
                    provider_called=provider_called,
                )
            company = candidate.company_name or payload.current_company
            attribution = self.company_attribution.resolve_company_for_context(
                db,
                raw_company_name=company,
                local_text=context_text,
                article_title=str(payload.representative_article.get("title") or ""),
                product_or_subject_name=final_name_decision.cleaned_name,
            )
            if candidate.decision == "reassign_company" and attribution.needs_review:
                return ProductFinalAdjudicationDecision(
                    decision="review",
                    canonical_product_name=final_name_decision.cleaned_name,
                    company_name=attribution.company_name_normalized or company,
                    release_year_month=candidate.release_year_month or payload.current_release_year_month,
                    release_year_month_basis=candidate.release_year_month_basis or payload.current_release_year_month_basis,
                    partner_company_name=candidate.partner_company_name or payload.partner_company_name,
                    partner_role=candidate.partner_role or payload.partner_role,
                    reason=f"reassigned_company_failed_local_validation:{attribution.reason}",
                    confidence=min(candidate.confidence, 0.5),
                    provider_called=provider_called,
                )
            return ProductFinalAdjudicationDecision(
                decision="accept" if candidate.decision == "reassign_company" else candidate.decision,
                canonical_product_name=final_name_decision.cleaned_name,
                company_name=attribution.company_name_normalized or company,
                insurance_type=attribution.insurance_type or candidate.insurance_type,
                product_type_code=candidate.product_type_code,
                release_year_month=candidate.release_year_month or payload.current_release_year_month,
                release_year_month_basis=candidate.release_year_month_basis or payload.current_release_year_month_basis,
                partner_company_name=candidate.partner_company_name or payload.partner_company_name,
                partner_role=candidate.partner_role or payload.partner_role,
                article_suitability=candidate.article_suitability,
                correction_summary=candidate.correction_summary,
                reason=candidate.reason,
                evidence_quote=candidate.evidence_quote,
                confidence=candidate.confidence,
                provider_called=provider_called,
            )

        if candidate:
            return ProductFinalAdjudicationDecision(
                **{**candidate.__dict__, "provider_called": provider_called}
            )

        if not name_decision.accepted:
            return ProductFinalAdjudicationDecision(
                decision="review" if risky else "reject",
                canonical_product_name=name_decision.cleaned_name,
                company_name=payload.current_company,
                release_year_month=payload.current_release_year_month,
                release_year_month_basis=payload.current_release_year_month_basis,
                partner_company_name=payload.partner_company_name,
                partner_role=payload.partner_role,
                reason=name_decision.reason,
                confidence=0.5,
                provider_called=provider_called,
            )
        return ProductFinalAdjudicationDecision(
            decision="accept",
            canonical_product_name=name_decision.cleaned_name,
            company_name=payload.current_company,
            product_type_code=payload.current_product_type,
            release_year_month=payload.current_release_year_month,
            release_year_month_basis=payload.current_release_year_month_basis,
            partner_company_name=payload.partner_company_name,
            partner_role=payload.partner_role,
            reason="deterministic_validators_passed",
            confidence=0.8,
            provider_called=provider_called,
        )

    @staticmethod
    def requires_llm_adjudication(
        payload: ProductFinalAdjudicationInput,
        *,
        name_reason: str | None = None,
        removed_prefixes: tuple[str, ...] = (),
    ) -> bool:
        if name_reason:
            return True
        if removed_prefixes:
            return True
        article_decision = payload.article_eligibility_decision
        if article_decision and not article_decision.is_eligible:
            return True
        if not payload.current_release_year_month:
            return True
        if (payload.current_release_year_month_basis or "unknown") in {"unknown", "first_seen_only", "earliest_related_article_month"}:
            return True
        if payload.partner_company_name or payload.partner_context_summary:
            return True
        if article_decision and (
            article_decision.detected_non_insurance_financial_institutions
            or article_decision.detected_insurer_companies and len(article_decision.detected_insurer_companies) > 1
        ):
            return True
        return False

    @staticmethod
    def _coerce_recoverable_reject(
        candidate: ProductFinalAdjudicationDecision | None,
        payload: ProductFinalAdjudicationInput,
        article_decision: ArticleEligibilityDecision | None,
    ) -> ProductFinalAdjudicationDecision | None:
        if candidate is None or candidate.decision != "reject":
            return candidate
        if article_decision and not article_decision.is_eligible:
            return candidate
        suitability = (candidate.article_suitability or "").casefold()
        reason = (candidate.reason or "").casefold()
        discard_markers = (
            "non_insurance",
            "ineligible",
            "multi_company",
            "marketing",
            "campaign",
            "not an insurance",
            "not insurance",
            "not a valid insurance",
            "not a product",
            "non-insurance",
            "서비스, not",
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
            "no textual evidence",
            "zero textual evidence",
            "no reference",
            "no support in the article",
            "unsupported by any evidence",
            "unsupported by the local context",
            "unsupported by evidence",
            "unsupported by textual evidence",
            "unsupported product attribution",
            "fails mutual support",
            "lack evidentiary support",
            "lacks evidentiary support",
            "exclusively discusses",
            "does not constitute product coverage",
            "not ambiguous or correctable",
            "not correctable",
        )
        if any(marker in suitability for marker in discard_markers + unsupported_discard_markers) or any(
            marker in reason for marker in discard_markers
        ):
            return candidate
        if ProductFinalAdjudicationService._reason_says_current_product_is_unsupported(
            reason,
            payload.current_product_name,
        ):
            return candidate
        if ProductFinalAdjudicationService._reason_says_current_product_identity_is_wrong(reason):
            return candidate
        has_correction = any(
            [
                candidate.canonical_product_name and candidate.canonical_product_name != payload.current_product_name,
                candidate.company_name and candidate.company_name != payload.current_company,
                candidate.release_year_month and candidate.release_year_month != payload.current_release_year_month,
                candidate.product_type_code and candidate.product_type_code != payload.current_product_type,
                candidate.partner_company_name != payload.partner_company_name if candidate.partner_company_name is not None else False,
            ]
        )
        uncertain_rejection_markers = (
            "must be rejected",
            "record invalid",
            "invalidates the record",
            "invalid for downstream",
            "irreconcilable",
            "fails core factual",
            "factually impossible",
            "most plausibly",
            "unrecoverable without external verification",
            "no explicit month",
            "no explicit release",
            "no supporting evidence",
        )
        if has_correction and candidate.confidence >= 0.75 and not any(marker in reason for marker in uncertain_rejection_markers):
            return replace(candidate, decision="accept", reason=f"recoverable_field_correction:{candidate.reason}")
        recoverable_review_markers = (
            "genuine insurance product",
            "genuinely about a specific insurance product",
            "article confirms",
            "article supports",
            "product-related",
            "field correction",
            "current fields are wrong",
            "current name",
            "current company",
            "company attribution",
            "release month",
            "release date",
            "release_year_month",
            "misdate",
            "misdates",
            "contradict",
            "contradicts",
            "product type",
            "correction is uncertain",
            "safe correction",
        )
        if not has_correction and not (
            any(marker in suitability for marker in recoverable_review_markers)
            or any(marker in reason for marker in recoverable_review_markers)
        ):
            return candidate
        return replace(
            candidate,
            decision="review",
            reason=f"recoverable_insurance_product_needs_review:{candidate.reason}",
            confidence=min(candidate.confidence, 0.65),
        )

    @staticmethod
    def _reject_provider_accept_for_wrong_current_identity(
        candidate: ProductFinalAdjudicationDecision | None,
        payload: ProductFinalAdjudicationInput,
    ) -> ProductFinalAdjudicationDecision | None:
        if candidate is None or candidate.decision not in {"accept", "reassign_company", "alias_only"}:
            return candidate
        reason = (candidate.reason or "").casefold()
        if ProductFinalAdjudicationService._reason_says_current_product_identity_is_wrong(reason):
            return replace(
                candidate,
                decision="reject",
                reason=f"provider_accept_rejected_current_product_identity_mismatch:{candidate.reason}",
                confidence=min(candidate.confidence, 0.85),
            )
        if ProductFinalAdjudicationService._reason_says_current_product_is_unsupported(
            reason,
            payload.current_product_name,
        ):
            return replace(
                candidate,
                decision="reject",
                reason=f"provider_accept_rejected_current_product_unsupported:{candidate.reason}",
                confidence=min(candidate.confidence, 0.85),
            )
        if ProductFinalAdjudicationService._provider_accept_replaces_current_product_without_support(candidate, payload, reason):
            return replace(
                candidate,
                decision="reject",
                reason=f"provider_accept_rejected_cross_product_misattribution:{candidate.reason}",
                confidence=min(candidate.confidence, 0.85),
            )
        return candidate

    @staticmethod
    def _reason_says_current_product_is_unsupported(reason: str, current_product_name: str | None) -> bool:
        product = (current_product_name or "").casefold().strip()
        if not reason or not product or product not in reason:
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
            "launch",
            "feature",
            "context",
        )
        for index in ProductFinalAdjudicationService._find_all(reason, product):
            window = reason[max(0, index - 100) : index + len(product) + 140]
            if any(marker in window for marker in negative_markers) and any(term in window for term in support_terms):
                return True
        return False

    @staticmethod
    def _reason_says_current_product_identity_is_wrong(reason: str) -> bool:
        if not reason or "current product" not in reason:
            return False
        identity_problem_markers = (
            "factually inconsistent with all evidence",
            "factually inconsistent with the article",
            "factually inconsistent with article",
            "factually inconsistent with the article's explicit content",
            "factually incompatible",
            "inconsistent with all evidence",
            "unsupported by the text",
            "unsupported by text",
            "unsupported by all evidence",
            "no mention or implication",
            "different product entirely",
            "mismatched product assignment",
            "fundamentally misaligned",
            "sole, unambiguous subject",
        )
        return any(marker in reason for marker in identity_problem_markers)

    @staticmethod
    def _provider_accept_replaces_current_product_without_support(
        candidate: ProductFinalAdjudicationDecision,
        payload: ProductFinalAdjudicationInput,
        reason: str,
    ) -> bool:
        if not candidate.canonical_product_name:
            return False
        current = (payload.current_product_name or "").casefold().strip()
        canonical = candidate.canonical_product_name.casefold().strip()
        if not current or current == canonical:
            return False
        no_support_markers = (
            "no mention of",
            "zero mention of",
            "contains no mention",
            "does not mention",
            "no evidence supports",
            "no textual support",
            "unsupported by the text",
            "any variant",
            "variant thereof",
        )
        return any(marker in reason for marker in no_support_markers)

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
    def _representative_article_payload(article: FactArticle | None, context_text: str | None) -> dict[str, Any]:
        if article is None:
            return {"local_product_windows": [compact_spaces(context_text)[:1200]] if context_text else []}
        return {
            "title": article.title,
            "url": article.original_url or article.url,
            "pub_date": article.pub_date.isoformat() if article.pub_date else None,
            "snippets": [],
            "local_product_windows": [compact_spaces(context_text)[:1200]] if context_text else [],
        }

    @staticmethod
    def _context_from_payload(payload: ProductFinalAdjudicationInput) -> str:
        article = payload.representative_article or {}
        parts = [
            str(article.get("title") or ""),
            *[str(item) for item in article.get("snippets") or []],
            *[str(item) for item in article.get("local_product_windows") or []],
        ]
        return compact_spaces(" ".join(part for part in parts if part))[:2400]

    @staticmethod
    def _provider_payload(payload: ProductFinalAdjudicationInput) -> dict[str, Any]:
        article_decision = payload.article_eligibility_decision
        return {
            "task_type": PRODUCT_FINAL_ADJUDICATION_TASK_TYPE,
            "schema_version": PRODUCT_FINAL_ADJUDICATION_SCHEMA_VERSION,
            "current_product_name": payload.current_product_name,
            "current_company": payload.current_company,
            "current_product_type": payload.current_product_type,
            "current_release_year_month": payload.current_release_year_month,
            "current_release_year_month_basis": payload.current_release_year_month_basis,
            "partner_company_name": payload.partner_company_name,
            "partner_role": payload.partner_role,
            "partner_context_summary": payload.partner_context_summary,
            "candidate_type": payload.candidate_type,
            "representative_article": payload.representative_article,
            "related_article_titles": payload.related_article_titles[:10],
            "aliases": payload.aliases[:20],
            "article_eligibility_decision": article_decision.__dict__ if article_decision else None,
        }

    @staticmethod
    def _decision_from_provider(output: dict[str, Any] | None) -> ProductFinalAdjudicationDecision | None:
        if not output:
            return None
        decision = str(output.get("decision") or "review")
        if decision not in PRODUCT_FINAL_DECISIONS:
            decision = "review"
        confidence = float(output.get("confidence") or 0.0)
        return ProductFinalAdjudicationDecision(
            decision=decision,
            canonical_product_name=ProductFinalAdjudicationService._optional_text(output.get("canonical_product_name")),
            company_name=ProductFinalAdjudicationService._optional_text(output.get("company_name")),
            insurance_type=ProductFinalAdjudicationService._optional_text(output.get("insurance_type")),
            product_type_code=ProductFinalAdjudicationService._optional_text(output.get("product_type_code")),
            release_year_month=ProductFinalAdjudicationService._optional_text(output.get("release_year_month")),
            release_year_month_basis=ProductFinalAdjudicationService._optional_text(output.get("release_year_month_basis")),
            partner_company_name=ProductFinalAdjudicationService._optional_text(output.get("partner_company_name")),
            partner_role=ProductFinalAdjudicationService._optional_text(output.get("partner_role")),
            article_suitability=ProductFinalAdjudicationService._optional_text(output.get("article_suitability")),
            correction_summary=ProductFinalAdjudicationService._optional_text(output.get("correction_summary")),
            reason=ProductFinalAdjudicationService._optional_text(output.get("reason")) or "provider_adjudication",
            evidence_quote=ProductFinalAdjudicationService._optional_text(output.get("evidence_quote")),
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
    def to_json(decision: ProductFinalAdjudicationDecision) -> str:
        return json.dumps(decision.__dict__, ensure_ascii=False)
