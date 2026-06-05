from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import DimCompany, FactArticle
from app.services.company_attribution_service import CompanyAttributionService
from app.services.product_company_eligibility import is_product_news_eligible_company
from app.utils.text import compact_spaces, normalize_search_key


GENERIC_PRODUCT_NAME_KEYS = {
    "간편건강보험",
    "간편 건강보험",
    "건강보험",
    "암보험",
    "운전자보험",
    "연금보험",
    "종신보험",
    "간편보험",
    "치아보험",
    "눈보험",
    "미니보험",
    "보험",
    "媛꾪렪嫄닿컯蹂댄뿕",
    "媛꾪렪 嫄닿컯蹂댄뿕",
    "嫄닿컯蹂댄뿕",
    "蹂댄뿕",
}

MARKETING_ONLY_KEYWORDS = (
    "TV 광고",
    "TV광고",
    "새 TV광고",
    "신규 TV 광고",
    "신규 TV광고",
    "광고 캠페인",
    "광고 공개",
    "광고 선보",
    "광고를 선보",
    "광고를 공개",
    "브랜드 캠페인",
    "모델",
    "영상 공개",
    "광고 영상",
    "캠페인 전개",
    "유튜브 광고",
    "CF",
    "광고",
    "TV愿묎퀬",
    "TV 愿묎퀬",
    "?좉퇋 TV 愿묎퀬",
    "愿묎퀬",
    "愿묎퀬瑜",
    "愿묎퀬 怨듦컻",
    "?좊낫",
)

LAUNCH_KEYWORDS = (
    "상품 출시",
    "신상품 출시",
    "출시했다",
    "출시한다",
    "판매 개시",
    "신규 출시",
    "개정 출시",
    "판매한다",
    "상품을 내놨",
    "상품을 선보",
    "異쒖떆",
    "?좎긽",
    "?좉퇋 異쒖떆",
    "?먮ℓ 媛쒖떆",
)


@dataclass(frozen=True)
class ProductAttributionGuardResult:
    create_product: bool
    resolved_company_name: str | None
    product_status: str
    needs_review: bool
    reason: str
    local_window: str
    marketing_only: bool
    generic_product_name: bool


class ProductAttributionGuardService:
    """Deterministic guard before product entity creation.

    This prevents query-company leakage and marketing-only articles from
    creating active products. It is intentionally generic and source-scoped:
    articles are not deleted, but weak/unsafe product candidates are kept as
    observations instead of becoming canonical products.
    """

    def __init__(self, attribution_service: CompanyAttributionService | None = None) -> None:
        self.attribution_service = attribution_service or CompanyAttributionService()

    def validate_product_candidate(
        self,
        db: Session,
        *,
        article: FactArticle | None,
        product_name: str | None,
        llm_company_candidate: str | None = None,
        source_text: str | None = None,
        proposed_status: str = "provisional",
    ) -> ProductAttributionGuardResult:
        local_window = self.extract_product_local_window(article=article, product_name=product_name, source_text=source_text)
        full_text = self._article_context(article, source_text=source_text)
        marketing_only = self.is_marketing_only_article(local_window or full_text)
        generic = self.is_generic_product_name(product_name)

        attribution = self.attribution_service.resolve_company_for_context(
            db,
            raw_company_name=llm_company_candidate,
            local_text=local_window,
            article_title=article.title if article else None,
            article_description=article.description if article else None,
            full_text=full_text,
            product_or_subject_name=product_name,
        )
        resolved_company = self._company_by_normalized(db, attribution.company_name_normalized)
        if attribution.company_name_normalized and not is_product_news_eligible_company(resolved_company):
            return ProductAttributionGuardResult(
                create_product=False if generic else True,
                resolved_company_name=None,
                product_status="review_ineligible_company",
                needs_review=True,
                reason=f"resolved company is not eligible for product-news attribution: {attribution.company_name_normalized}",
                local_window=local_window,
                marketing_only=marketing_only,
                generic_product_name=generic,
            )

        if article and bool(article.multi_company_article_yn):
            return ProductAttributionGuardResult(
                create_product=False,
                resolved_company_name=None,
                product_status="rejected_multi_company_source",
                needs_review=True,
                reason="multi-company article is excluded from product extraction",
                local_window=local_window,
                marketing_only=marketing_only,
                generic_product_name=generic,
            )

        if marketing_only and generic:
            return ProductAttributionGuardResult(
                create_product=False,
                resolved_company_name=attribution.company_name_normalized,
                product_status="rejected_marketing_only",
                needs_review=True,
                reason="generic product name in marketing-only article; keep observation only",
                local_window=local_window,
                marketing_only=True,
                generic_product_name=True,
            )

        if not attribution.company_name_normalized or attribution.basis in {"company_candidates", "raw_candidate"}:
            return ProductAttributionGuardResult(
                create_product=False if generic else True,
                resolved_company_name=attribution.company_name_normalized,
                product_status="review_query_company_only" if generic else "review",
                needs_review=True,
                reason=f"no reliable local company evidence; {attribution.reason}",
                local_window=local_window,
                marketing_only=marketing_only,
                generic_product_name=generic,
            )

        if llm_company_candidate and attribution.company_name_normalized:
            raw_match = self.attribution_service.normalizer.normalize(llm_company_candidate)
            if raw_match and raw_match.company_name_normalized and raw_match.company_name_normalized != attribution.company_name_normalized:
                return ProductAttributionGuardResult(
                    create_product=True,
                    resolved_company_name=attribution.company_name_normalized,
                    product_status="review" if proposed_status == "active" else proposed_status,
                    needs_review=True,
                    reason=(
                        "query/LLM company ignored because local product context differs: "
                        f"{raw_match.company_name_normalized} -> {attribution.company_name_normalized}"
                    ),
                    local_window=local_window,
                    marketing_only=marketing_only,
                    generic_product_name=generic,
                )

        return ProductAttributionGuardResult(
            create_product=True,
            resolved_company_name=attribution.company_name_normalized,
            product_status="rejected_marketing_only" if marketing_only and proposed_status == "active" else proposed_status,
            needs_review=bool(attribution.needs_review or marketing_only),
            reason=attribution.reason if not marketing_only else f"{attribution.reason}; marketing-only article",
            local_window=local_window,
            marketing_only=marketing_only,
            generic_product_name=generic,
        )

    def extract_product_local_window(
        self,
        *,
        article: FactArticle | None,
        product_name: str | None,
        source_text: str | None = None,
        sentences_before_after: int = 2,
    ) -> str:
        text_parts = [article.title if article else None, article.description if article else None]
        text_parts.extend(self._snippet_texts_from_llm_input(source_text))
        text_parts.append(source_text)
        text = compact_spaces(" ".join(part for part in text_parts if part))
        if not text:
            return ""
        product_key = normalize_search_key(product_name)
        sentences = self._split_sentences(text)
        if not product_key:
            return " ".join(sentences[:3])[:1500]
        matched_indexes = [
            idx for idx, sentence in enumerate(sentences) if product_key and product_key in normalize_search_key(sentence)
        ]
        if not matched_indexes:
            return " ".join(sentences[:3])[:1500]
        windows: list[str] = []
        for idx in matched_indexes[:3]:
            start = max(0, idx - sentences_before_after)
            end = min(len(sentences), idx + sentences_before_after + 1)
            windows.append(" ".join(sentences[start:end]))
        return compact_spaces(" ".join(dict.fromkeys(windows)))[:2000]

    @staticmethod
    def is_generic_product_name(product_name: str | None) -> bool:
        key = normalize_search_key(product_name)
        if not key:
            return True
        return key in {normalize_search_key(item) for item in GENERIC_PRODUCT_NAME_KEYS}

    @staticmethod
    def is_marketing_only_article(text: str | None) -> bool:
        value = compact_spaces(text)
        if not value:
            return False
        has_marketing = any(keyword in value for keyword in MARKETING_ONLY_KEYWORDS)
        has_launch = any(keyword in value for keyword in LAUNCH_KEYWORDS)
        return has_marketing and not has_launch

    @staticmethod
    def _article_context(article: FactArticle | None, *, source_text: str | None = None) -> str:
        return "\n".join(part for part in [article.title if article else None, article.description if article else None, source_text] if part)

    @staticmethod
    def _company_by_normalized(db: Session, company_name: str | None) -> DimCompany | None:
        if not company_name:
            return None
        return db.query(DimCompany).filter(DimCompany.company_name_normalized == company_name).first()

    @staticmethod
    def _snippet_texts_from_llm_input(source_text: str | None) -> list[str]:
        if not source_text:
            return []
        try:
            payload: Any = json.loads(source_text)
        except (TypeError, json.JSONDecodeError):
            return []
        snippets = payload.get("snippets") if isinstance(payload, dict) else None
        if not isinstance(snippets, dict):
            return []
        texts: list[str] = []
        for values in snippets.values():
            if isinstance(values, list):
                texts.extend(str(item) for item in values if item)
            elif values:
                texts.append(str(values))
        return texts

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        normalized = compact_spaces(text)
        if not normalized:
            return []
        parts = re.split(r"[.!?。]\s+|다\.\s+|다\s+", normalized)
        return [part.strip() for part in parts if part.strip()]
