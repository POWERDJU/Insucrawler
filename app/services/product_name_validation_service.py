from __future__ import annotations

import re
from dataclasses import dataclass

from app.normalizers.product_name_normalizer import (
    clean_product_name_candidate_result,
    validate_product_name_before_save,
)
from app.utils.text import compact_spaces, normalize_search_key


MODEL_PERSON_CONTEXT_KEYWORDS = (
    "모델",
    "배우",
    "방송인",
    "광고",
    "캠페인",
    "화보",
    "홍보대사",
)


@dataclass(frozen=True)
class ProductNameQualityDecision:
    accepted: bool
    cleaned_name: str
    reason: str = ""
    removed_prefixes: tuple[str, ...] = ()
    needs_review: bool = False


class ProductNameValidationService:
    """Shared product-name gate used before entity creation and batch import.

    The lower-level normalizer owns canonical string cleanup. This service adds
    context-aware rejection reasons that are useful for diagnostics and tests.
    """

    def validate(
        self,
        raw_product_name: str | None,
        *,
        article_title: str | None = None,
        evidence_text: str | None = None,
        context_text: str | None = None,
        company_aliases: list[str] | None = None,
    ) -> ProductNameQualityDecision:
        cleaned_result = clean_product_name_candidate_result(raw_product_name, company_aliases)
        base = validate_product_name_before_save(
            raw_product_name,
            article_title=article_title,
            evidence_text=evidence_text,
            context_text=context_text,
            company_aliases=company_aliases,
        )
        if self._looks_like_model_person_name(cleaned_result.cleaned_name, context_text or evidence_text or article_title):
            return ProductNameQualityDecision(
                accepted=False,
                cleaned_name=cleaned_result.cleaned_name,
                reason="model_person_name_as_product",
                removed_prefixes=cleaned_result.removed_prefixes,
                needs_review=True,
            )
        if not base.accepted:
            return ProductNameQualityDecision(
                accepted=False,
                cleaned_name=base.cleaned_name,
                reason=base.reason,
                removed_prefixes=cleaned_result.removed_prefixes,
                needs_review=True,
            )
        return ProductNameQualityDecision(
            accepted=True,
            cleaned_name=base.cleaned_name,
            reason="",
            removed_prefixes=cleaned_result.removed_prefixes,
            needs_review=bool(cleaned_result.removed_prefixes),
        )

    @staticmethod
    def _looks_like_model_person_name(product_name: str | None, context_text: str | None) -> bool:
        name = compact_spaces(product_name)
        context = compact_spaces(context_text)
        if not name or not context:
            return False
        if not any(keyword in context for keyword in MODEL_PERSON_CONTEXT_KEYWORDS):
            return False
        key = normalize_search_key(name)
        if not key:
            return False
        return bool(re.match(r"^[가-힣]{2,5}(?:와|과|의)", name)) or any(
            token in key for token in ("이기우", "설채현")
        )
