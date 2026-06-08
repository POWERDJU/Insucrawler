from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from app.utils.text import compact_spaces, normalize_search_key


COMPANY_WIDE_METRIC_TERMS = (
    "매출",
    "영업이익",
    "순이익",
    "당기순이익",
    "세전이익",
    "보험영업손익",
    "투자손익",
    "연결 기준",
    "분기 실적",
    "상반기 실적",
    "연간 실적",
    "수익",
)


@dataclass(frozen=True)
class SalesMetricValidationDecision:
    accepted: bool
    reason: str = ""
    needs_review: bool = False


class SalesMetricValidationService:
    """Validate that a sales metric belongs to the product, not the company."""

    def validate(
        self,
        metric: dict[str, Any],
        *,
        product_name: str | None,
        aliases: list[str] | None = None,
        context_text: str | None = None,
    ) -> SalesMetricValidationDecision:
        evidence = compact_spaces(metric.get("evidence_text") or "")
        context = compact_spaces(context_text)
        if not evidence:
            return SalesMetricValidationDecision(False, "missing_sales_metric_evidence", True)

        names = [product_name, *(aliases or [])]
        if not self._has_product_name_near_metric(evidence, context, names):
            if self._looks_company_wide(evidence):
                return SalesMetricValidationDecision(False, "company_wide_metric_without_product_context", True)
            if self._looks_oversized_money_metric(metric):
                return SalesMetricValidationDecision(False, "oversized_money_metric_without_product_context", True)
            return SalesMetricValidationDecision(False, "product_name_not_near_sales_metric", True)

        if self._looks_company_wide(evidence) and not self._has_sales_product_token(evidence):
            return SalesMetricValidationDecision(False, "company_wide_metric", True)
        return SalesMetricValidationDecision(True, "", False)

    @staticmethod
    def _has_product_name_near_metric(evidence: str, context: str, names: list[str | None]) -> bool:
        name_keys = [normalize_search_key(name) for name in names if normalize_search_key(name)]
        if not name_keys:
            return False
        evidence_key = normalize_search_key(evidence)
        if any(name_key in evidence_key for name_key in name_keys):
            return True
        sentences = SalesMetricValidationService._sentences(context)
        evidence_key_short = normalize_search_key(evidence[:80])
        for idx, sentence in enumerate(sentences):
            if evidence_key_short and evidence_key_short in normalize_search_key(sentence):
                nearby = " ".join(sentences[max(0, idx - 1) : idx + 1])
                nearby_key = normalize_search_key(nearby)
                return any(name_key in nearby_key for name_key in name_keys)
        return False

    @staticmethod
    def _looks_company_wide(text: str) -> bool:
        return any(term in text for term in COMPANY_WIDE_METRIC_TERMS)

    @staticmethod
    def _has_sales_product_token(text: str) -> bool:
        compact = re.sub(r"\s+", "", text)
        return any(token in compact for token in ["상품판매", "판매건수", "계약건수", "신계약", "초회보험료", "월초보험료"])

    @staticmethod
    def _looks_oversized_money_metric(metric: dict[str, Any]) -> bool:
        unit = str(metric.get("metric_unit") or "")
        try:
            value = Decimal(str(metric.get("metric_value") or "0"))
        except (InvalidOperation, ValueError):
            return False
        if "억원" in unit and value >= Decimal("1000"):
            return True
        if "원" in unit and value >= Decimal("100000000000"):
            return True
        return False

    @staticmethod
    def _sentences(text: str) -> list[str]:
        return [part.strip() for part in re.split(r"(?<=[.!?。])\s+|다\.\s*|요\.\s*", text or "") if part.strip()]
