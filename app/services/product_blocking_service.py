from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Iterable

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.db.models import DimCompany, DimProduct, FactProductObservation
from app.normalizers.product_name_normalizer import (
    build_product_family_tokens,
    is_generic_product_family_signature,
    normalize_product_family_signature,
    version_signature,
)


WILDCARD_PRODUCT_TYPES = {None, "", "UNKNOWN", "OTHER"}
SOFT_COMPATIBLE_PRODUCT_TYPES = {
    frozenset(("CHILD_ADULT_CHILD", "HEALTH_COMPREHENSIVE")),
    frozenset(("CHILD_ADULT_CHILD", "ACCIDENT_DRIVER")),
    frozenset(("CHILD_ADULT_CHILD", "SPECIFIC_DISEASE")),
    frozenset(("CHILD_ADULT_CHILD", "OTHER")),
    frozenset(("CHILD_ADULT_CHILD", "UNKNOWN")),
    frozenset(("SIMPLIFIED_IMPAIRED", "HEALTH_COMPREHENSIVE")),
    frozenset(("SIMPLIFIED_IMPAIRED", "CANCER")),
    frozenset(("SIMPLIFIED_IMPAIRED", "SPECIFIC_DISEASE")),
    frozenset(("SIMPLIFIED_IMPAIRED", "DEMENTIA_CARE")),
    frozenset(("SIMPLIFIED_IMPAIRED", "MEDICAL_INDEMNITY")),
    frozenset(("VARIABLE_UL", "DEATH_WHOLELIFE")),
    frozenset(("VARIABLE_UL", "ANNUITY_SAVINGS")),
    frozenset(("ANNUITY_SAVINGS", "DEATH_WHOLELIFE")),
    frozenset(("HEALTH_COMPREHENSIVE", "SPECIFIC_DISEASE")),
    frozenset(("HEALTH_COMPREHENSIVE", "CANCER")),
    frozenset(("PROPERTY_EXPENSE", "OTHER")),
    frozenset(("PROPERTY_EXPENSE", "UNKNOWN")),
    frozenset(("PET", "OTHER")),
    frozenset(("PET", "UNKNOWN")),
    frozenset(("TRAVEL_LEISURE", "OTHER")),
    frozenset(("TRAVEL_LEISURE", "UNKNOWN")),
}
INCOMPATIBLE_PRODUCT_TYPES = {
    frozenset(("AUTO", "DENTAL")),
    frozenset(("AUTO", "ANNUITY_SAVINGS")),
    frozenset(("AUTO", "DEATH_WHOLELIFE")),
    frozenset(("DENTAL", "ANNUITY_SAVINGS")),
}

CONTEXT_STOPWORDS = {
    "보험",
    "보험상품",
    "상품",
    "고객",
    "대상",
    "전용",
    "특화",
    "위한",
    "이용",
    "출시",
    "신상품",
    "보장",
    "보험료",
    "무배당",
    "갱신형",
    "비갱신",
    "플랜",
    "가입",
    "제공",
    "관련",
    "서비스",
    "혜택",
    "다이렉트",
    "뉴스",
    "금융",
    "최근",
    "확대",
    "판매",
    "개시",
    "선보였다",
    "내놨다",
    "대상으로",
    "고객인",
    "고객을",
    "위해",
    "한다",
    "했다",
    "위험",
    "article",
    "articles",
    "candidate",
    "cluster",
    "company",
    "count",
    "coverage",
    "date",
    "description",
    "id",
    "launch",
    "name",
    "product",
    "pub",
    "snippet",
    "snippets",
    "target",
    "text",
    "title",
    "type",
    "health",
    "comprehensive",
    "child",
    "adult",
    "death",
    "wholelife",
    "annuity",
    "savings",
    "property",
    "expense",
}

PARTNER_ALIASES = {
    "lg": "LG",
    "lgu": "LG유플러스",
    "lgu+": "LG유플러스",
    "lg u+": "LG유플러스",
    "lg유플러스": "LG유플러스",
    "엘지유플러스": "LG유플러스",
    "유플러스": "LG유플러스",
    "u+": "LG유플러스",
}

WEAK_CANDIDATE_TYPES = {"weak_mention", "pronoun_or_context_reference"}
REJECTED_CANDIDATE_TYPES = {"rejected"}


@dataclass
class ProductBlockCandidate:
    product_id: int
    name: str
    core_key: str | None
    company_id: int | None
    partner_company_name: str | None
    product_type_code: str | None
    release_year_month: str | None
    candidate_types: set[str] = field(default_factory=set)
    observation_ids: set[int] = field(default_factory=set)
    article_titles: list[str] = field(default_factory=list)
    article_descriptions: list[str] = field(default_factory=list)
    source_urls: list[str] = field(default_factory=list)
    observation_contexts: list[str] = field(default_factory=list)
    context_text: str = ""
    context_signature: str = ""
    high_info_tokens: set[str] = field(default_factory=set)
    inferred_partner_name: str | None = None
    alias_names: list[str] = field(default_factory=list)
    family_signature: str = ""
    family_tokens: set[str] = field(default_factory=set)
    version_signature: set[str] = field(default_factory=set)


@dataclass
class ProductBlock:
    block_key: str
    candidates: list[ProductBlockCandidate]
    reason: str
    company_id: int | None = None
    partner_company_name: str | None = None
    release_month_window: str | None = None
    product_type_codes: list[str] = field(default_factory=list)
    candidate_product_ids: list[int] = field(default_factory=list)
    observation_ids: list[int] = field(default_factory=list)


class ProductBlockingService:
    """Build broad, conservative-review blocks for product entity resolution.

    Blocking should be wider than auto-merge. It intentionally groups plausible
    same-product candidates by name and article context even when company or
    partner metadata is incomplete.
    """

    def build_blocks(self, db: Session, *, target: str = "all_provisional", limit: int = 500) -> list[ProductBlock]:
        candidates = self._load_candidates(db, target=target, limit=limit)
        if len(candidates) <= 1:
            return []

        parent = {candidate.product_id: candidate.product_id for candidate in candidates}

        def find(product_id: int) -> int:
            while parent[product_id] != product_id:
                parent[product_id] = parent[parent[product_id]]
                product_id = parent[product_id]
            return product_id

        def union(left: int, right: int) -> None:
            root_left = find(left)
            root_right = find(right)
            if root_left != root_right:
                parent[root_right] = root_left

        for index, left in enumerate(candidates):
            for right in candidates[index + 1 :]:
                if self._same_block(left, right):
                    union(left.product_id, right.product_id)

        grouped: dict[int, list[ProductBlockCandidate]] = defaultdict(list)
        for candidate in candidates:
            grouped[find(candidate.product_id)].append(candidate)

        blocks: list[ProductBlock] = []
        for group in grouped.values():
            if len(group) <= 1:
                continue
            blocks.append(self._make_block(group))
        return sorted(blocks, key=lambda block: (-len(block.candidates), block.block_key))

    def _load_candidates(self, db: Session, *, target: str, limit: int) -> list[ProductBlockCandidate]:
        query = db.query(DimProduct).filter(DimProduct.product_status != "merged")
        if target in {"new_since_last_job", "all_provisional"}:
            query = query.filter(DimProduct.product_status.in_(["provisional", "review", "active"]))
        query = query.order_by(DimProduct.product_id.desc())
        if limit and limit > 0:
            query = query.limit(limit)
        products = list(query.all())
        if not products:
            return []

        product_ids = [int(product.product_id) for product in products]
        company_alias_map = self._load_company_aliases(db, products)
        observation_map = self._load_observations(db, product_ids)
        article_map = self._load_article_context(db, product_ids)
        alias_map = self._load_aliases(db, product_ids)
        partner_map = self._load_partners(db, product_ids)

        candidates: list[ProductBlockCandidate] = []
        for product in products:
            pid = int(product.product_id)
            observations = observation_map.get(pid, [])
            articles = article_map.get(pid, [])
            aliases = alias_map.get(pid, [])
            partners = partner_map.get(pid, [])

            candidate_types = {str(row["candidate_type"]) for row in observations if row.get("candidate_type")}
            observation_ids = {int(row["observation_id"]) for row in observations if row.get("observation_id") is not None}
            article_titles = self._unique(
                [
                    *(row.get("article_title") or "" for row in observations),
                    *(row.get("title") or "" for row in articles),
                ]
            )
            article_descriptions = self._unique(
                [
                    *(row.get("article_description") or "" for row in observations),
                    *(row.get("description") or "" for row in articles),
                ]
            )
            source_urls = self._unique(
                [
                    *(row.get("source_url") or "" for row in observations),
                    *(row.get("source_url") or "" for row in articles),
                ]
            )
            observation_contexts = self._unique(row.get("observation_context_text") or "" for row in observations)
            alias_names = self._unique(
                [
                    *(row.get("raw_product_name") or "" for row in aliases),
                    *(row.get("normalized_product_name_candidate") or "" for row in aliases),
                    *(row.get("raw_product_name") or "" for row in observations),
                    *(row.get("normalized_product_name_candidate") or "" for row in observations),
                ]
            )
            partner_name = product.partner_company_name or self._first_non_empty(row.get("partner_company_name") for row in observations) or self._first_non_empty(partners)
            company_aliases = company_alias_map.get(product.company_id, [])
            product_family_names = [
                product.raw_product_name,
                product.normalized_product_name,
                product.product_core_key,
            ]
            alias_observation_family_names = [
                *alias_names,
            ]
            family_names = [*product_family_names, *alias_observation_family_names]
            context_names = [
                *article_titles,
                *article_descriptions,
                *observation_contexts,
            ]
            family_signature = self._best_family_signature(product_family_names, company_aliases)
            if not family_signature:
                family_signature = self._best_family_signature(family_names, company_aliases)
            family_tokens = self._family_tokens_for_names(product_family_names, company_aliases)
            for family_name in alias_observation_family_names:
                alias_signature = normalize_product_family_signature(family_name, company_aliases)
                if self._family_signature_compatible(family_signature, alias_signature):
                    family_tokens.update(build_product_family_tokens(family_name, company_aliases))
            product_versions = set()
            for family_name in product_family_names:
                product_versions.update(version_signature(family_name))
            if not product_versions:
                for family_name in alias_observation_family_names:
                    product_versions.update(version_signature(family_name))
            context_text = self.build_context_text(
                ProductBlockCandidate(
                    product_id=pid,
                    name=product.normalized_product_name or product.raw_product_name,
                    core_key=product.product_core_key,
                    company_id=product.company_id,
                    partner_company_name=partner_name,
                    product_type_code=product.primary_product_type_code,
                    release_year_month=product.release_year_month,
                    candidate_types=candidate_types,
                    observation_ids=observation_ids,
                    article_titles=article_titles,
                    article_descriptions=article_descriptions,
                    source_urls=source_urls,
                    observation_contexts=observation_contexts,
                    alias_names=alias_names,
                    family_signature=family_signature,
                    family_tokens=family_tokens,
                    version_signature=product_versions,
                )
            )
            if context_names:
                context_text = "\n".join([context_text, *[item for item in context_names if item]])
            tokens = self.extract_high_info_tokens(context_text)
            candidates.append(
                ProductBlockCandidate(
                    product_id=pid,
                    name=product.normalized_product_name or product.raw_product_name,
                    core_key=product.product_core_key,
                    company_id=product.company_id,
                    partner_company_name=partner_name,
                    product_type_code=product.primary_product_type_code,
                    release_year_month=product.release_year_month,
                    candidate_types=candidate_types,
                    observation_ids=observation_ids,
                    article_titles=article_titles,
                    article_descriptions=article_descriptions,
                    source_urls=source_urls,
                    observation_contexts=observation_contexts,
                    context_text=context_text,
                    context_signature=" ".join(sorted(tokens)),
                    high_info_tokens=tokens,
                    inferred_partner_name=partner_name or self.inferred_partner_name(context_text),
                    alias_names=alias_names,
                    family_signature=family_signature,
                    family_tokens=family_tokens,
                    version_signature=product_versions,
                )
            )
        return [candidate for candidate in candidates if not candidate.candidate_types.intersection(REJECTED_CANDIDATE_TYPES)]

    def _load_company_aliases(self, db: Session, products: list[DimProduct]) -> dict[int | None, list[str]]:
        company_ids = sorted({product.company_id for product in products if product.company_id is not None})
        if not company_ids:
            return {}
        rows = db.query(DimCompany).filter(DimCompany.company_id.in_(company_ids)).all()
        result: dict[int | None, list[str]] = {}
        for row in rows:
            aliases = [row.company_name_normalized or "", row.company_name_raw or ""]
            aliases.extend(item.strip() for item in (row.alias or "").split("|") if item.strip())
            result[row.company_id] = [item for item in dict.fromkeys(aliases) if item]
        return result

    def _load_observations(self, db: Session, product_ids: list[int]) -> dict[int, list[dict[str, object]]]:
        rows = (
            db.query(FactProductObservation)
            .filter(FactProductObservation.product_id.in_(product_ids))
            .all()
        )
        result: dict[int, list[dict[str, object]]] = defaultdict(list)
        for row in rows:
            if row.product_id is None:
                continue
            result[int(row.product_id)].append(
                {
                    "observation_id": row.observation_id,
                    "article_id": row.article_id,
                    "raw_product_name": row.raw_product_name,
                    "normalized_product_name_candidate": row.normalized_product_name_candidate,
                    "partner_company_name": row.partner_company_name,
                    "candidate_type": row.candidate_type,
                    "article_title": row.article_title,
                    "article_description": row.article_description,
                    "source_url": row.source_url,
                    "observation_context_text": row.observation_context_text,
                }
            )
        return result

    def _load_article_context(self, db: Session, product_ids: list[int]) -> dict[int, list[dict[str, str | None]]]:
        if not product_ids:
            return {}
        rows = db.execute(
            text(
                """
                SELECT pa.product_id, a.title, a.description, COALESCE(a.original_url, a.url) AS source_url
                FROM fact_product_article pa
                JOIN fact_article a ON a.article_id = pa.article_id
                WHERE pa.product_id IN :product_ids
                """
            ).bindparams(bindparam("product_ids", expanding=True)),
            {"product_ids": product_ids},
        ).mappings()
        result: dict[int, list[dict[str, str | None]]] = defaultdict(list)
        for row in rows:
            result[int(row["product_id"])].append(
                {"title": row["title"], "description": row["description"], "source_url": row["source_url"]}
            )
        return result

    def _load_aliases(self, db: Session, product_ids: list[int]) -> dict[int, list[dict[str, str | None]]]:
        if not product_ids:
            return {}
        rows = db.execute(
            text(
                """
                SELECT product_id, raw_product_name, normalized_product_name_candidate
                FROM dim_product_alias
                WHERE product_id IN :product_ids
                """
            ).bindparams(bindparam("product_ids", expanding=True)),
            {"product_ids": product_ids},
        ).mappings()
        result: dict[int, list[dict[str, str | None]]] = defaultdict(list)
        for row in rows:
            result[int(row["product_id"])].append(
                {
                    "raw_product_name": row["raw_product_name"],
                    "normalized_product_name_candidate": row["normalized_product_name_candidate"],
                }
            )
        return result

    def _load_partners(self, db: Session, product_ids: list[int]) -> dict[int, list[str]]:
        if not product_ids:
            return {}
        rows = db.execute(
            text(
                """
                SELECT pp.product_id, pc.partner_name_normalized
                FROM fact_product_partner pp
                JOIN dim_partner_company pc ON pc.partner_id = pp.partner_id
                WHERE pp.product_id IN :product_ids
                """
            ).bindparams(bindparam("product_ids", expanding=True)),
            {"product_ids": product_ids},
        ).mappings()
        result: dict[int, list[str]] = defaultdict(list)
        for row in rows:
            if row["partner_name_normalized"]:
                result[int(row["product_id"])].append(str(row["partner_name_normalized"]))
        return result

    def _same_block(self, left: ProductBlockCandidate, right: ProductBlockCandidate) -> bool:
        if left.company_id and right.company_id and left.company_id != right.company_id:
            return False
        if not self.product_type_compatible_soft(left.product_type_code, right.product_type_code):
            return False
        if self._month_distance_too_far(left.release_year_month, right.release_year_month, max_months=18):
            return False
        if self._version_conflicts(left.name, right.name):
            return False
        if left.version_signature and right.version_signature and left.version_signature != right.version_signature:
            return False
        if left.core_key and right.core_key and left.core_key == right.core_key:
            return True
        if left.observation_ids.intersection(right.observation_ids):
            return True
        if self._same_company_family_block(left, right):
            return True
        if self._same_company_short_generic_alias_block(left, right):
            return True

        name_score = self.name_similarity(left.name, right.name)
        context_score = self.context_similarity(left, right)
        left_partner = self._candidate_partner(left)
        right_partner = self._candidate_partner(right)
        same_partner = bool(left_partner and right_partner and left_partner == right_partner)
        close_month = not self._month_distance_too_far(left.release_year_month, right.release_year_month, max_months=3)

        if left.company_id and left.company_id == right.company_id and close_month:
            return name_score >= 0.74 or context_score >= 0.45
        if same_partner:
            return name_score >= 0.64 or context_score >= 0.42
        return self.should_context_block(left, right, name_score=name_score, context_score=context_score)

    def _same_company_family_block(self, left: ProductBlockCandidate, right: ProductBlockCandidate) -> bool:
        if not left.company_id or left.company_id != right.company_id:
            return False
        if self._month_distance_too_far(left.release_year_month, right.release_year_month, max_months=3):
            return False
        if self._specific_family_conflicts(left, right):
            return False
        if left.family_signature and right.family_signature and left.family_signature == right.family_signature:
            if not is_generic_product_family_signature(left.family_signature):
                return True
        if self._same_company_refund_family(left, right):
            return True
        overlap = self.family_token_overlap(left, right)
        shared_family_tokens = left.family_tokens.intersection(right.family_tokens)
        informative_shared = {
            token
            for token in shared_family_tokens
            if token not in {"insurance", "health", "annuity", "savings", "product", "보험", "상품", "건강", "연금"}
        }
        if overlap >= 0.60 and informative_shared:
            return True
        if overlap >= 0.70 and (self.name_similarity(left.name, right.name) >= 0.55 or self.context_similarity(left, right) >= 0.35):
            return True
        return False

    def _same_company_short_generic_alias_block(self, left: ProductBlockCandidate, right: ProductBlockCandidate) -> bool:
        if not left.company_id or left.company_id != right.company_id:
            return False
        if self._month_distance_too_far(left.release_year_month, right.release_year_month, max_months=3):
            return False
        left_compact = self._compact(left.name)
        right_compact = self._compact(right.name)
        if not left_compact or not right_compact or left_compact == right_compact:
            return False
        shorter = min(left_compact, right_compact, key=len)
        longer = max(left_compact, right_compact, key=len)
        if len(shorter) < 3 or len(shorter) > 6 or not shorter.endswith("보험"):
            return False
        if shorter not in longer:
            return False
        return len(longer) - len(shorter) >= 2

    def _same_company_refund_family(self, left: ProductBlockCandidate, right: ProductBlockCandidate) -> bool:
        if self._specific_family_conflicts(left, right):
            return False
        left_text = self._compact(" ".join([left.name, *left.alias_names]))
        right_text = self._compact(" ".join([right.name, *right.alias_names]))
        if "환급" not in left_text or "환급" not in right_text:
            return False
        conflict_terms = ("전신마취", "마취수술", "수술보험")
        if any(term in left_text for term in conflict_terms) or any(term in right_text for term in conflict_terms):
            return False
        return True

    @staticmethod
    def _specific_family_tokens(tokens: set[str]) -> set[str]:
        generic = {"보험", "상품", "건강", "종합", "연금", "환급", "won", "우리won", "납입", "납입특약", "특약보험료", "보험료"}
        return {token for token in tokens if token not in generic}

    def _specific_family_conflicts(self, left: ProductBlockCandidate, right: ProductBlockCandidate) -> bool:
        left_specific = self._specific_family_tokens(left.family_tokens)
        right_specific = self._specific_family_tokens(right.family_tokens)
        if self._token_sets_have_containment(left_specific, right_specific):
            return False
        return bool(left_specific and right_specific and not left_specific.intersection(right_specific))

    @staticmethod
    def _token_sets_have_containment(left_tokens: set[str], right_tokens: set[str]) -> bool:
        if not left_tokens or not right_tokens:
            return False
        for left in left_tokens:
            left_compact = "".join(ch for ch in left.casefold() if ch.isalnum())
            if not left_compact:
                continue
            for right in right_tokens:
                right_compact = "".join(ch for ch in right.casefold() if ch.isalnum())
                if not right_compact:
                    continue
                if left_compact == right_compact:
                    return True
                if len(left_compact) >= 3 and len(right_compact) >= 3 and (left_compact in right_compact or right_compact in left_compact):
                    return True
        return False

    def should_context_block(
        self,
        left: ProductBlockCandidate,
        right: ProductBlockCandidate,
        *,
        name_score: float | None = None,
        context_score: float | None = None,
    ) -> bool:
        if left.company_id and right.company_id and left.company_id != right.company_id:
            return False
        if not self.product_type_compatible_soft(left.product_type_code, right.product_type_code):
            return False
        if self._month_distance_too_far(left.release_year_month, right.release_year_month, max_months=18):
            return False
        if self._version_conflicts(left.name, right.name):
            return False
        if left.version_signature and right.version_signature and left.version_signature != right.version_signature:
            return False
        name_score = self.name_similarity(left.name, right.name) if name_score is None else name_score
        context_score = self.context_similarity(left, right) if context_score is None else context_score
        shared_tokens = left.high_info_tokens.intersection(right.high_info_tokens)
        if len(shared_tokens) >= 2 and context_score >= 0.38:
            return True
        if context_score >= 0.45:
            return True
        return name_score >= 0.74 and context_score >= 0.38

    def product_type_compatible_soft(self, left: str | None, right: str | None) -> bool:
        left_code = (left or "").strip() or None
        right_code = (right or "").strip() or None
        if left_code == right_code:
            return True
        if left_code in WILDCARD_PRODUCT_TYPES or right_code in WILDCARD_PRODUCT_TYPES:
            return True
        pair = frozenset((left_code, right_code))
        if pair in INCOMPATIBLE_PRODUCT_TYPES:
            return False
        return pair in SOFT_COMPATIBLE_PRODUCT_TYPES

    def family_token_overlap(self, left: ProductBlockCandidate, right: ProductBlockCandidate) -> float:
        left_tokens = left.family_tokens
        right_tokens = right.family_tokens
        if not left_tokens or not right_tokens:
            return 0.0
        denominator = min(len(left_tokens), len(right_tokens))
        return len(left_tokens.intersection(right_tokens)) / max(1, denominator)

    def build_context_text(self, candidate: ProductBlockCandidate) -> str:
        values = [
            candidate.name,
            candidate.core_key or "",
            candidate.partner_company_name or "",
            candidate.product_type_code or "",
            candidate.release_year_month or "",
            candidate.family_signature or "",
            " ".join(sorted(candidate.family_tokens)),
            *candidate.alias_names,
            *candidate.article_titles,
            *candidate.article_descriptions,
            *candidate.observation_contexts,
        ]
        return "\n".join(value for value in values if value)

    def extract_high_info_tokens(self, text_value: str | None) -> set[str]:
        text_value = (text_value or "").casefold()
        raw_tokens = re.findall(r"[0-9A-Za-z가-힣+]+", text_value)
        tokens: set[str] = set()
        for token in raw_tokens:
            normalized = re.sub(r"(보험상품|보험|상품)$", "", token.strip())
            if len(normalized) < 2 or normalized in CONTEXT_STOPWORDS:
                continue
            if normalized.isdigit():
                continue
            tokens.add(normalized)
        return tokens

    def context_similarity(self, left: ProductBlockCandidate, right: ProductBlockCandidate) -> float:
        left_tokens = left.high_info_tokens or self.extract_high_info_tokens(left.context_text)
        right_tokens = right.high_info_tokens or self.extract_high_info_tokens(right.context_text)
        if not left_tokens or not right_tokens:
            token_score = 0.0
        else:
            intersection = len(left_tokens.intersection(right_tokens))
            union = len(left_tokens.union(right_tokens))
            token_score = intersection / union if union else 0.0
        name_score = self.name_similarity(left.name, right.name)
        partner_bonus = 0.12 if self._candidate_partner(left) and self._candidate_partner(left) == self._candidate_partner(right) else 0.0
        month_bonus = 0.08 if not self._month_distance_too_far(left.release_year_month, right.release_year_month, max_months=3) else 0.0
        type_bonus = 0.06 if self.product_type_compatible_soft(left.product_type_code, right.product_type_code) else 0.0
        return min(1.0, token_score * 0.55 + name_score * 0.25 + partner_bonus + month_bonus + type_bonus)

    def inferred_partner_name(self, text_value: str | None) -> str | None:
        folded = (text_value or "").casefold()
        compact = self._compact(folded)
        for alias, canonical in PARTNER_ALIASES.items():
            if self._compact(alias) in compact:
                return canonical
        match = re.search(r"([0-9A-Za-z가-힣+]{2,24}(?:은행|카드|캐피탈|페이|pay|텔레콤|통신|플러스|유플러스|마트|쇼핑|증권))", folded)
        if match:
            return match.group(1)
        return None

    def name_similarity(self, left: str | None, right: str | None) -> float:
        left_compact = self._compact(left)
        right_compact = self._compact(right)
        if not left_compact or not right_compact:
            return 0.0
        if left_compact == right_compact:
            return 1.0
        if left_compact in right_compact or right_compact in left_compact:
            shorter = min(len(left_compact), len(right_compact))
            longer = max(len(left_compact), len(right_compact))
            return max(0.82, shorter / longer)
        left_tokens = self.extract_high_info_tokens(left)
        right_tokens = self.extract_high_info_tokens(right)
        token_score = 0.0
        if left_tokens and right_tokens:
            token_score = len(left_tokens.intersection(right_tokens)) / len(left_tokens.union(right_tokens))
        seq_score = SequenceMatcher(None, left_compact, right_compact).ratio()
        return max(seq_score, token_score)

    def _make_block(self, candidates: list[ProductBlockCandidate]) -> ProductBlock:
        company_ids = sorted({candidate.company_id for candidate in candidates if candidate.company_id is not None})
        partners = sorted({self._candidate_partner(candidate) for candidate in candidates if self._candidate_partner(candidate)})
        months = sorted({candidate.release_year_month for candidate in candidates if candidate.release_year_month})
        product_types = sorted({candidate.product_type_code for candidate in candidates if candidate.product_type_code})
        observation_ids = sorted({obs for candidate in candidates for obs in candidate.observation_ids})
        shared_tokens = set.intersection(*(candidate.high_info_tokens for candidate in candidates if candidate.high_info_tokens)) if any(candidate.high_info_tokens for candidate in candidates) else set()
        block_key = "|".join(
            [
                f"company:{company_ids[0]}" if len(company_ids) == 1 else "company:unknown-or-mixed",
                f"partner:{partners[0]}" if partners else "partner:unknown",
                f"type:{','.join(product_types[:3]) or 'unknown'}",
                f"month:{months[0] if months else 'unknown'}",
                f"ids:{','.join(str(candidate.product_id) for candidate in sorted(candidates, key=lambda item: item.product_id)[:5])}",
            ]
        )
        return ProductBlock(
            block_key=block_key,
            candidates=sorted(candidates, key=lambda candidate: candidate.product_id),
            reason=self._block_reason(candidates, shared_tokens),
            company_id=company_ids[0] if len(company_ids) == 1 else None,
            partner_company_name=partners[0] if partners else None,
            release_month_window=f"{months[0]}~{months[-1]}" if months else None,
            product_type_codes=product_types,
            candidate_product_ids=[candidate.product_id for candidate in sorted(candidates, key=lambda item: item.product_id)],
            observation_ids=observation_ids,
        )

    def _block_reason(self, candidates: list[ProductBlockCandidate], shared_tokens: set[str]) -> str:
        payload = {
            "reason": "context_block",
            "candidate_count": len(candidates),
            "candidate_names": [candidate.name for candidate in candidates],
            "candidate_product_ids": [candidate.product_id for candidate in candidates],
            "shared_high_info_tokens": sorted(shared_tokens)[:30],
            "family_signatures": sorted({candidate.family_signature for candidate in candidates if candidate.family_signature}),
            "family_tokens": sorted({token for candidate in candidates for token in candidate.family_tokens})[:40],
            "partner_candidates": sorted({self._candidate_partner(candidate) for candidate in candidates if self._candidate_partner(candidate)}),
            "context_scores": [
                {
                    "left": left.product_id,
                    "right": right.product_id,
                    "name_similarity": round(self.name_similarity(left.name, right.name), 4),
                    "context_similarity": round(self.context_similarity(left, right), 4),
                }
                for index, left in enumerate(candidates)
                for right in candidates[index + 1 :]
            ][:20],
        }
        return json.dumps(payload, ensure_ascii=False)

    def _candidate_partner(self, candidate: ProductBlockCandidate) -> str | None:
        return candidate.partner_company_name or candidate.inferred_partner_name

    @staticmethod
    def _version_signature(value: str | None) -> set[str]:
        return version_signature(value)

    def _version_conflicts(self, left: str | None, right: str | None) -> bool:
        left_versions = self._version_signature(left)
        right_versions = self._version_signature(right)
        return bool(left_versions and right_versions and left_versions != right_versions)

    def _best_family_signature(self, names: Iterable[str | None], company_aliases: list[str]) -> str:
        candidates: list[tuple[str, str]] = []
        for name in names:
            signature = normalize_product_family_signature(name, company_aliases)
            if signature and not is_generic_product_family_signature(signature):
                candidates.append((signature, name or ""))
        if not candidates:
            return ""
        return sorted(
            candidates,
            key=lambda item: (self._signature_quality_score(item[0], item[1]), item[0]),
            reverse=True,
        )[0][0]

    @staticmethod
    def _signature_quality_score(signature: str, source_name: str | None = None) -> float:
        base = signature.split("|v:", 1)[0]
        source = (source_name or "").casefold()
        score = 0.0
        if source:
            score += 4.0
        if re.search(r"(보험|특약|서비스|제도|담보)\s*$", source_name or ""):
            score += 2.0
        if "|v:" in signature:
            score += 2.0
        if 4 <= len(base) <= 18:
            score += 2.0
        if len(base) > 24:
            score -= 5.0
        if re.search(r"\d+(?:일|월|개월|만원|원|위)", base):
            score -= 5.0
        noisy_terms = {"보장", "출시", "신상품", "보험료", "고객", "눈길", "러시", "다양한", "암", "치매"}
        if any(term in base for term in noisy_terms):
            score -= 3.0
        return score

    @staticmethod
    def _family_signature_compatible(primary_signature: str, alias_signature: str) -> bool:
        if not alias_signature or is_generic_product_family_signature(alias_signature):
            return False
        if not primary_signature:
            return True
        primary_base = primary_signature.split("|v:", 1)[0]
        alias_base = alias_signature.split("|v:", 1)[0]
        if primary_base == alias_base:
            return True
        primary_tokens = build_product_family_tokens(primary_base)
        alias_tokens = build_product_family_tokens(alias_base)
        specific = {"건강환급", "전신마취수술", "톤틴", "시그니처", "여성", "mri", "전이암", "전통시장", "날씨피해"}
        primary_specific = primary_tokens.intersection(specific)
        alias_specific = alias_tokens.intersection(specific)
        if primary_specific and alias_specific and not primary_specific.intersection(alias_specific):
            return False
        return alias_base in primary_base or primary_base in alias_base

    def _family_tokens_for_names(self, names: Iterable[str | None], company_aliases: list[str]) -> set[str]:
        tokens: set[str] = set()
        for name in names:
            tokens.update(build_product_family_tokens(name, company_aliases))
        return tokens

    @staticmethod
    def _month_distance_too_far(left: str | None, right: str | None, *, max_months: int) -> bool:
        if not left or not right or len(left) < 7 or len(right) < 7:
            return False
        try:
            left_year, left_month = int(left[:4]), int(left[5:7])
            right_year, right_month = int(right[:4]), int(right[5:7])
        except ValueError:
            return False
        distance = abs((left_year * 12 + left_month) - (right_year * 12 + right_month))
        return distance > max_months

    @staticmethod
    def _compact(value: str | None) -> str:
        return re.sub(r"[^0-9A-Za-z가-힣+]", "", value or "").casefold()

    @staticmethod
    def _unique(values: Iterable[str | None]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            value = (value or "").strip()
            if not value or value in seen:
                continue
            result.append(value)
            seen.add(value)
        return result

    @staticmethod
    def _first_non_empty(values: Iterable[str | None]) -> str | None:
        for value in values:
            if value:
                return str(value)
        return None
