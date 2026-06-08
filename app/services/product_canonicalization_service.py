from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import repository
from app.db.models import (
    DimProduct,
    FactCoverageEvidence,
    FactProductArticle,
    FactProductMajorCoverage,
    FactProductMergeDecision,
    FactProductNarrativeInsight,
    FactProductObservation,
    FactProductPartner,
    FactProductStructuredFeature,
    FactSalesMetricStructured,
)
from app.normalizers.product_name_normalizer import normalize_product_name, normalize_product_name_core
from app.utils.dates import utcnow


WEAK_NAME_KEYS = {
    "이번보험",
    "해당보험",
    "이보험",
    "이번상품",
    "해당상품",
    "이상품",
    "미니보험",
    "어린이특화보험",
    "보험",
    "상품",
}
PRONOUN_MARKERS = {"이번", "해당", "이 상품", "이 보험", "본 상품", "본 보험"}
DESCRIPTIVE_MARKERS = {"전용", "특화", "대상", "고객", "위한", "이용"}
LAUNCH_MARKERS = {"출시", "신규", "선보", "내놨", "판매 개시"}
PARTNER_NAMES = {
    "LG유플러스": "telecom",
    "엘지유플러스": "telecom",
    "유플러스": "telecom",
    "LG U+": "telecom",
    "LGU+": "telecom",
}
STOP_TOKENS = {
    "보험",
    "상품",
    "고객",
    "대상",
    "전용",
    "특화",
    "위한",
    "이용",
    "최초",
    "이번",
    "해당",
}


@dataclass
class ProductNamePlan:
    index: int
    raw_name: str
    canonical_name: str
    candidate_type: str
    create_product: bool = True
    alias_names: list[str] = field(default_factory=list)
    partner_company_name: str | None = None
    partner_context_summary: str | None = None
    merge_reason: str | None = None


@dataclass
class SameProductJudgement:
    same_product: bool
    confidence: float
    canonical_product_name: str | None = None
    merge_reason: str | None = None
    alias_names: list[str] = field(default_factory=list)
    should_auto_merge: bool = False
    needs_human_review: bool = False
    decision_source: str = "deterministic"


class ProductCanonicalizationService:
    def judge_same_product(self, left: ProductNamePlan, right: ProductNamePlan, ai_judge: Any | None = None) -> SameProductJudgement:
        if self._same_context_product(left, right):
            canonical = self.select_canonical_plan([left, right])
            return SameProductJudgement(
                same_product=True,
                confidence=0.9,
                canonical_product_name=canonical.canonical_name,
                merge_reason="same context and overlapping product-name tokens",
                alias_names=[left.raw_name, right.raw_name],
                should_auto_merge=True,
                needs_human_review=False,
                decision_source="deterministic_context",
            )
        if ai_judge is None:
            return SameProductJudgement(same_product=False, confidence=0.0, needs_human_review=True)
        payload = ai_judge(left, right)
        confidence = float(payload.get("confidence") or 0.0)
        same_product = bool(payload.get("same_product"))
        return SameProductJudgement(
            same_product=same_product,
            confidence=confidence,
            canonical_product_name=payload.get("canonical_product_name"),
            merge_reason=payload.get("merge_reason"),
            alias_names=list(payload.get("alias_names") or [left.raw_name, right.raw_name]),
            should_auto_merge=same_product and confidence >= 0.85,
            needs_human_review=same_product and confidence < 0.85,
            decision_source="ai_same_product_judge",
        )

    def classify_product_name_candidate(self, raw_name: str | None, article_context: str | None = None) -> str:
        name = normalize_product_name(raw_name)
        compact = self._compact(name)
        if not compact:
            return "rejected"
        if compact in WEAK_NAME_KEYS:
            return "weak_mention"
        if any(marker in name for marker in PRONOUN_MARKERS):
            return "pronoun_or_context_reference"
        if self.detect_partner_name(name):
            return "partner_brand_phrase"
        if article_context and any(marker in article_context for marker in LAUNCH_MARKERS) and name in article_context:
            return "launch_name"
        if any(marker in name for marker in DESCRIPTIVE_MARKERS):
            return "descriptive_alias"
        if name.endswith("보험"):
            return "official_name"
        return "weak_mention" if len(compact) < 6 else "descriptive_alias"

    def plan_extraction_products(self, products: list[Any], article_context: str | None = None) -> list[ProductNamePlan]:
        plans: list[ProductNamePlan] = []
        for idx, product in enumerate(products):
            identity = product.identity
            raw_name = identity.raw_product_name or identity.normalized_product_name_candidate
            if not raw_name:
                continue
            candidate_type = self.classify_product_name_candidate(raw_name, article_context)
            partner = self.detect_partner_name(raw_name) or self.detect_partner_name(article_context)
            canonical_name = self.canonical_name_from_raw(raw_name)
            plans.append(
                ProductNamePlan(
                    index=idx,
                    raw_name=raw_name,
                    canonical_name=canonical_name,
                    candidate_type=candidate_type,
                    create_product=candidate_type not in {"weak_mention", "pronoun_or_context_reference", "rejected"},
                    partner_company_name=partner,
                    partner_context_summary=self.partner_context_summary(raw_name, article_context, partner),
                )
            )
        if not plans:
            return plans

        active = [plan for plan in plans if plan.create_product]
        if not active:
            return plans

        groups = self._context_groups(active)
        grouped_indices = set()
        for group in groups:
            if len(group) <= 1:
                continue
            canonical = self.select_canonical_plan(group)
            aliases = [plan.raw_name for plan in group if plan.index != canonical.index]
            aliases.extend(plan.raw_name for plan in plans if not plan.create_product)
            canonical.alias_names = list(dict.fromkeys([*canonical.alias_names, *aliases]))
            canonical.merge_reason = "same article/context product name aliases"
            for plan in group:
                grouped_indices.add(plan.index)
                if plan.index != canonical.index:
                    plan.create_product = False
                    plan.merge_reason = f"merged into candidate index {canonical.index}"

        if len(active) == 1:
            active[0].alias_names = list(dict.fromkeys([*active[0].alias_names, *[plan.raw_name for plan in plans if not plan.create_product]]))

        return plans

    def select_canonical_plan(self, plans: list[ProductNamePlan]) -> ProductNamePlan:
        return sorted(plans, key=lambda plan: self._specificity_score(plan), reverse=True)[0]

    def canonical_name_from_raw(self, raw_name: str | None) -> str:
        name = normalize_product_name(raw_name)
        for partner in sorted(PARTNER_NAMES, key=len, reverse=True):
            name = re.sub(re.escape(partner), " ", name, flags=re.IGNORECASE)
        name = re.sub(r"\s+", " ", name).strip()
        name = re.sub(r"\s+보험$", "보험", name)
        return name or normalize_product_name(raw_name)

    def detect_partner_name(self, text_value: str | None) -> str | None:
        text_value = text_value or ""
        for partner in PARTNER_NAMES:
            if partner in text_value:
                return partner
        return None

    def partner_context_summary(self, raw_name: str | None, article_context: str | None, partner: str | None) -> str | None:
        if not partner:
            return None
        source = article_context or raw_name or ""
        for sentence in re.split(r"(?<=[.!?。])\s+|\n+", source):
            if partner in sentence:
                return sentence.strip()[:500]
        return raw_name

    def merge_same_article_products(self, db: Session, article_id: int) -> list[FactProductMergeDecision]:
        rows = (
            db.query(DimProduct)
            .join(FactProductArticle, FactProductArticle.product_id == DimProduct.product_id)
            .filter(FactProductArticle.article_id == article_id, DimProduct.product_status != "merged")
            .order_by(DimProduct.product_id)
            .all()
        )
        if len(rows) <= 1:
            return []
        plans = [
            ProductNamePlan(
                index=idx,
                raw_name=product.raw_product_name,
                canonical_name=self.canonical_name_from_raw(product.normalized_product_name or product.raw_product_name),
                candidate_type=self.classify_product_name_candidate(product.normalized_product_name or product.raw_product_name),
                create_product=True,
            )
            for idx, product in enumerate(rows)
        ]
        decisions: list[FactProductMergeDecision] = []
        for group in self._context_groups(plans):
            if len(group) <= 1:
                continue
            canonical_plan = self.select_canonical_plan(group)
            canonical = rows[canonical_plan.index]
            for plan in group:
                duplicate = rows[plan.index]
                if duplicate.product_id == canonical.product_id:
                    continue
                decisions.append(
                    self.merge_products(
                        db,
                        canonical,
                        duplicate,
                        decision_source="deterministic_same_article",
                        confidence=0.9,
                        reason="same article context and overlapping product-name tokens",
                        evidence_article_ids=[article_id],
                    )
                )
        return decisions

    def merge_products(
        self,
        db: Session,
        canonical: DimProduct,
        duplicate: DimProduct,
        *,
        decision_source: str,
        confidence: float,
        reason: str,
        evidence_article_ids: list[int] | None = None,
        needs_review: bool = False,
    ) -> FactProductMergeDecision:
        canonical.canonical_product_id = canonical.product_id
        canonical.product_status = "active"
        repository.record_product_alias(
            db,
            canonical,
            duplicate.raw_product_name,
            duplicate.normalized_product_name,
            duplicate.product_core_key,
            article_id=None,
            source_type="merge",
        )
        for alias in db.execute(text("SELECT raw_product_name, normalized_product_name_candidate, product_core_key, article_id, source_type FROM dim_product_alias WHERE product_id = :product_id"), {"product_id": duplicate.product_id}).mappings().all():
            repository.record_product_alias(
                db,
                canonical,
                alias["raw_product_name"],
                alias["normalized_product_name_candidate"],
                alias["product_core_key"],
                article_id=alias["article_id"],
                source_type=alias["source_type"] or "merge",
            )

        for link in db.query(FactProductArticle).filter(FactProductArticle.product_id == duplicate.product_id).all():
            exists = (
                db.query(FactProductArticle)
                .filter(FactProductArticle.product_id == canonical.product_id, FactProductArticle.article_id == link.article_id)
                .first()
            )
            if exists:
                db.delete(link)
            else:
                link.product_id = canonical.product_id

        for model in [
            FactProductStructuredFeature,
            FactProductNarrativeInsight,
            FactProductMajorCoverage,
            FactSalesMetricStructured,
            FactCoverageEvidence,
            FactProductPartner,
            FactProductObservation,
        ]:
            db.query(model).filter(model.product_id == duplicate.product_id).update({"product_id": canonical.product_id}, synchronize_session=False)

        duplicate.product_status = "merged"
        duplicate.merged_into_product_id = canonical.product_id
        duplicate.canonical_product_id = canonical.product_id
        duplicate.last_consolidated_at = utcnow()
        canonical.alias_count = db.query(FactProductObservation).filter(FactProductObservation.product_id == canonical.product_id).count()
        canonical.consolidation_status = "done"
        canonical.last_consolidated_at = utcnow()
        decision = FactProductMergeDecision(
            canonical_product_id=canonical.product_id,
            duplicate_product_id=duplicate.product_id,
            decision_type="auto_merge" if not needs_review else "merge_candidate",
            decision_source=decision_source,
            confidence=confidence,
            reason=reason,
            evidence_article_ids_json=json.dumps(evidence_article_ids or [], ensure_ascii=False),
            alias_names_json=json.dumps([duplicate.raw_product_name, duplicate.normalized_product_name], ensure_ascii=False),
            applied_at=utcnow() if not needs_review else None,
            applied_by="system",
            needs_review=needs_review,
        )
        db.add(decision)
        db.flush()
        return decision

    def _context_groups(self, plans: list[ProductNamePlan]) -> list[list[ProductNamePlan]]:
        if len(plans) <= 1:
            return [plans]
        parent = {plan.index: plan.index for plan in plans}

        def find(idx: int) -> int:
            while parent[idx] != idx:
                parent[idx] = parent[parent[idx]]
                idx = parent[idx]
            return idx

        def union(left: int, right: int) -> None:
            root_left, root_right = find(left), find(right)
            if root_left != root_right:
                parent[root_right] = root_left

        for left_idx, left in enumerate(plans):
            for right in plans[left_idx + 1 :]:
                if self._same_context_product(left, right):
                    union(left.index, right.index)
        grouped: dict[int, list[ProductNamePlan]] = {}
        for plan in plans:
            grouped.setdefault(find(plan.index), []).append(plan)
        return list(grouped.values())

    def _same_context_product(self, left: ProductNamePlan, right: ProductNamePlan) -> bool:
        if left.candidate_type in {"weak_mention", "pronoun_or_context_reference"} or right.candidate_type in {"weak_mention", "pronoun_or_context_reference"}:
            return True
        left_tokens = self._tokens(left.canonical_name)
        right_tokens = self._tokens(right.canonical_name)
        if not left_tokens or not right_tokens:
            return False
        overlap = left_tokens & right_tokens
        if len(overlap) >= 2:
            return True
        if overlap & {"키즈", "미니", "어린이", "펫", "치아"}:
            return True
        denominator = max(1, min(len(left_tokens), len(right_tokens)))
        return len(overlap) / denominator >= 0.5 and bool({"키즈", "미니", "어린이", "펫", "치아", "암"} & overlap)

    def _specificity_score(self, plan: ProductNamePlan) -> float:
        name = plan.canonical_name or plan.raw_name
        compact_len = len(self._compact(name))
        score = min(compact_len, 20) / 10
        if compact_len > 28:
            score -= (compact_len - 28) / 8
        score += {"official_name": 5, "launch_name": 4, "descriptive_alias": 3, "partner_brand_phrase": 2, "weak_mention": -5}.get(plan.candidate_type, 0)
        for marker in ("전용", "특화", "키즈폰", "어린이", "미니", "보장"):
            if marker in name:
                score += 0.8
        return score

    def _tokens(self, value: str | None) -> set[str]:
        normalized = normalize_product_name(value)
        tokens = {token for token in re.split(r"[^0-9A-Za-z가-힣]+", normalized) if len(token) >= 2 and token not in STOP_TOKENS}
        compact = self._compact(normalized)
        expansions = {
            "키즈": "키즈" in compact,
            "폰": "폰" in compact,
            "미니": "미니" in compact,
            "어린이": "어린이" in compact,
            "케어": "케어" in compact,
            "펫": "펫" in compact,
            "치아": "치아" in compact,
            "암": "암" in compact,
        }
        tokens.update(token for token, present in expansions.items() if present)
        return tokens

    @staticmethod
    def _compact(value: str | None) -> str:
        return re.sub(r"[^0-9A-Za-z가-힣]+", "", value or "").casefold()


def product_core_key_for_keyword(value: str | None) -> str:
    return normalize_product_name_core(value, [])
