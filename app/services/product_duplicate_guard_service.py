from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy.orm import Session

from app.db.models import DimCompany, DimProduct
from app.normalizers.product_name_normalizer import (
    build_product_family_tokens,
    is_generic_product_family_signature,
    normalize_product_family_signature,
    version_signature,
)
from app.services.product_blocking_service import ProductBlock, ProductBlockCandidate, ProductBlockingService


DEFAULT_DUPLICATE_CHECK_PATH = Path("data/exports/product_duplicate_check.csv")


class ProductDuplicateGuardService:
    """Read-only duplicate risk guard for dashboard/export and admin checks.

    This service never mutates DB state and never calls an LLM. It reuses the
    broad product blocking layer, then reports same-company active/provisional
    product groups that still look like duplicate canonical rows.
    """

    def __init__(self, *, blocking_service: ProductBlockingService | None = None) -> None:
        self.blocking_service = blocking_service or ProductBlockingService()

    def find_duplicate_family_groups(self, db: Session, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        filters = filters or {}
        blocks = self.blocking_service.build_blocks(db, target="all", limit=0)
        groups: list[dict[str, Any]] = []
        for block in blocks:
            candidates = self._filter_candidates(db, block.candidates, filters)
            if len(candidates) <= 1:
                continue
            for component in self._duplicate_components(candidates):
                if len(component) <= 1:
                    continue
                group = self._group_from_candidates(db, block, component)
                if group["risk_score"] >= 0.65:
                    groups.append(group)
        return sorted(groups, key=lambda row: (-row["risk_score"], -row["candidate_count"], row["group_key"]))

    def summarize_duplicate_risk(self, groups: list[dict[str, Any]]) -> dict[str, Any]:
        product_ids = {pid for group in groups for pid in group.get("product_ids", [])}
        high_risk = [group for group in groups if float(group.get("risk_score") or 0) >= 0.80]
        return {
            "duplicate_group_count": len(groups),
            "duplicate_product_count": len(product_ids),
            "high_risk_group_count": len(high_risk),
            "export_warning": bool(groups),
            "groups": groups,
        }

    def export_groups_csv(self, groups: list[dict[str, Any]], path: str | Path = DEFAULT_DUPLICATE_CHECK_PATH) -> Path:
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = [
            "group_key",
            "company_id",
            "company_name",
            "candidate_count",
            "risk_score",
            "product_ids",
            "product_names",
            "release_year_months",
            "product_type_codes",
            "shared_family_tokens",
            "suggested_action",
            "reason",
        ]
        with output_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for group in groups:
                row = dict(group)
                for key in ("product_ids", "product_names", "release_year_months", "product_type_codes", "shared_family_tokens"):
                    row[key] = json.dumps(row.get(key) or [], ensure_ascii=False)
                writer.writerow({field: row.get(field, "") for field in fieldnames})
        return output_path

    def alias_is_compatible(self, product: DimProduct, alias_name: str | None, company_aliases: list[str] | None = None) -> bool:
        alias_tokens = build_product_family_tokens(alias_name, company_aliases)
        alias_signature = normalize_product_family_signature(alias_name, company_aliases)
        if not alias_tokens and not alias_signature:
            return False
        product_names = [product.normalized_product_name, product.raw_product_name, product.product_core_key]
        product_tokens: set[str] = set()
        for name in product_names:
            product_tokens.update(build_product_family_tokens(name, company_aliases))
        product_signature = self._best_signature(product_names, company_aliases)
        if alias_signature and product_signature and alias_signature == product_signature:
            return True
        if not product_tokens or not alias_tokens:
            return True
        product_specific = self._specific_family_tokens(product_tokens)
        alias_specific = self._specific_family_tokens(alias_tokens)
        if product_specific and alias_specific and not product_specific.intersection(alias_specific):
            return False
        overlap = len(product_tokens.intersection(alias_tokens)) / max(1, min(len(product_tokens), len(alias_tokens)))
        if overlap >= 0.45:
            return True
        # Clearly different, information-rich alias families should not be shown
        # as canonical aliases in user-facing Excel output.
        return not (len(alias_tokens) >= 2 and len(product_tokens) >= 2)

    def compatible_alias_names(self, product: DimProduct, alias_names: Iterable[str | None], company_aliases: list[str] | None = None) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for alias_name in alias_names:
            value = (alias_name or "").strip()
            if not value or value in seen:
                continue
            if self.alias_is_compatible(product, value, company_aliases):
                result.append(value)
                seen.add(value)
        return result

    def _filter_candidates(
        self,
        db: Session,
        candidates: list[ProductBlockCandidate],
        filters: dict[str, Any],
    ) -> list[ProductBlockCandidate]:
        company_id = filters.get("company_id")
        company_name = filters.get("company_name")
        allowed_statuses = {"active", "provisional", "review"}
        result: list[ProductBlockCandidate] = []
        for candidate in candidates:
            product = db.get(DimProduct, candidate.product_id)
            if not product or (product.product_status or "active") not in allowed_statuses:
                continue
            if company_id is not None and product.company_id != int(company_id):
                continue
            if company_name and self._company_name(db, product.company_id) != company_name:
                continue
            result.append(candidate)
        return result

    def _duplicate_components(self, candidates: list[ProductBlockCandidate]) -> list[list[ProductBlockCandidate]]:
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
                if self._duplicate_pair_score(left, right) >= 0.65:
                    union(left.product_id, right.product_id)

        grouped: dict[int, list[ProductBlockCandidate]] = defaultdict(list)
        for candidate in candidates:
            grouped[find(candidate.product_id)].append(candidate)
        return list(grouped.values())

    def _duplicate_pair_score(self, left: ProductBlockCandidate, right: ProductBlockCandidate) -> float:
        if left.company_id and right.company_id and left.company_id != right.company_id:
            return 0.0
        if not self.blocking_service.product_type_compatible_soft(left.product_type_code, right.product_type_code):
            return 0.0
        if self.blocking_service._month_distance_too_far(left.release_year_month, right.release_year_month, max_months=6):
            return 0.0
        if self.blocking_service._version_conflicts(left.name, right.name):
            return 0.0
        if left.version_signature and right.version_signature and left.version_signature != right.version_signature:
            return 0.0
        if self._distinct_variant_modifier(left.name, right.name):
            return 0.0
        if left.family_signature and right.family_signature and left.family_signature == right.family_signature:
            if self._usable_duplicate_signature(left.family_signature):
                return 0.96

        name_score = self.blocking_service.name_similarity(left.name, right.name)
        context_score = self.blocking_service.context_similarity(left, right)
        family_overlap = self.blocking_service.family_token_overlap(left, right)
        shared_specific = self._specific_shared_tokens(left, right)
        same_company = bool(left.company_id and left.company_id == right.company_id)
        same_partner = self._same_partner(left, right)
        containment = self._name_containment(left.name, right.name)

        if (
            self._weak_context_alias_pair(left, right)
            and (same_company or same_partner or (not left.company_id and not right.company_id))
            and (containment or name_score >= 0.55 or context_score >= 0.55 or shared_specific)
        ):
            return min(0.88, max(name_score, context_score, 0.82))
        if same_company and self.blocking_service._same_company_refund_family(left, right):
            return min(0.90, max(name_score, context_score, family_overlap, 0.84))
        if self.blocking_service._specific_family_conflicts(left, right) and not containment:
            return 0.0
        if self._short_generic_alias_pair(left, right) and (same_company or same_partner):
            return min(0.90, max(name_score, context_score, 0.82))
        if family_overlap >= 0.70 and shared_specific and (same_company or same_partner):
            return min(0.94, max(family_overlap, name_score, 0.86))
        if family_overlap >= 0.60 and shared_specific and (same_company or same_partner):
            return min(0.92, max(family_overlap, name_score, 0.84))
        if containment and shared_specific and (same_company or same_partner):
            return min(0.92, max(name_score, context_score, 0.82))
        if not left.company_id and not right.company_id and shared_specific:
            if containment and context_score >= 0.38:
                return min(0.88, max(name_score, context_score, 0.82))
            if name_score >= 0.55 and context_score >= 0.55:
                return min(0.88, max(name_score, context_score, 0.82))
        if name_score >= 0.86 and shared_specific and (same_company or same_partner):
            return min(0.90, max(name_score, context_score))
        if context_score >= 0.70 and name_score >= 0.55 and len(shared_specific) >= 2 and (same_company or same_partner):
            return min(0.88, max(context_score, name_score))
        return 0.0

    def _distinct_variant_modifier(self, left_name: str | None, right_name: str | None) -> bool:
        left = self.blocking_service._compact(left_name)
        right = self.blocking_service._compact(right_name)
        if not left or not right or left == right:
            return False
        if left in right:
            extra = right.replace(left, "", 1)
        elif right in left:
            extra = left.replace(right, "", 1)
        else:
            return False
        if not extra:
            return False
        distinct_markers = {
            "365",
            "연간",
            "직거래",
            "원팀",
            "원데이",
            "자동차",
            "선물하기",
            "취소",
            "위약금",
        }
        return any(marker in extra for marker in distinct_markers)

    def _short_generic_alias_pair(self, left: ProductBlockCandidate, right: ProductBlockCandidate) -> bool:
        left_compact = self.blocking_service._compact(left.name)
        right_compact = self.blocking_service._compact(right.name)
        if not left_compact or not right_compact or left_compact == right_compact:
            return False
        shorter = min(left_compact, right_compact, key=len)
        longer = max(left_compact, right_compact, key=len)
        if len(shorter) < 3 or len(shorter) > 6 or not shorter.endswith("보험"):
            return False
        if shorter not in longer:
            return False
        return len(longer) - len(shorter) >= 2

    @staticmethod
    def _weak_context_alias_pair(left: ProductBlockCandidate, right: ProductBlockCandidate) -> bool:
        weak_types = {"weak_mention", "pronoun_or_context_reference"}
        left_weak = bool(left.candidate_types and left.candidate_types.intersection(weak_types))
        right_weak = bool(right.candidate_types and right.candidate_types.intersection(weak_types))
        return left_weak or right_weak

    def _group_from_candidates(self, db: Session, block: ProductBlock, candidates: list[ProductBlockCandidate]) -> dict[str, Any]:
        products = [db.get(DimProduct, candidate.product_id) for candidate in candidates]
        products = [product for product in products if product is not None]
        product_ids = [int(product.product_id) for product in products]
        product_names = [product.normalized_product_name or product.raw_product_name for product in products]
        company_ids = sorted({product.company_id for product in products if product.company_id is not None})
        company_id = company_ids[0] if len(company_ids) == 1 else None
        shared_tokens = set.intersection(*(candidate.family_tokens for candidate in candidates if candidate.family_tokens)) if any(candidate.family_tokens for candidate in candidates) else set()
        max_overlap = 0.0
        for index, left in enumerate(candidates):
            for right in candidates[index + 1 :]:
                max_overlap = max(max_overlap, self._duplicate_pair_score(left, right))
        risk_score = min(1.0, max_overlap)
        return {
            "group_key": block.block_key,
            "company_id": company_id,
            "company_name": self._company_name(db, company_id),
            "candidate_count": len(products),
            "risk_score": round(risk_score, 4),
            "product_ids": product_ids,
            "product_names": product_names,
            "release_year_months": sorted({product.release_year_month for product in products if product.release_year_month}),
            "product_type_codes": sorted({product.primary_product_type_code for product in products if product.primary_product_type_code}),
            "shared_family_tokens": sorted(shared_tokens),
            "suggested_action": "run_full_list_consolidation" if risk_score >= 0.75 else "review",
            "reason": block.reason,
        }

    @staticmethod
    def _best_signature(names: Iterable[str | None], company_aliases: list[str] | None = None) -> str:
        signatures: list[tuple[str, str]] = []
        for name in names:
            signature = normalize_product_family_signature(name, company_aliases)
            if ProductDuplicateGuardService._usable_duplicate_signature(signature):
                signatures.append((signature, name or ""))
        if not signatures:
            return ""
        return sorted(signatures, key=lambda item: (ProductDuplicateGuardService._signature_quality_score(item[0], item[1]), item[0]), reverse=True)[0][0]

    @staticmethod
    def _specific_family_tokens(tokens: set[str]) -> set[str]:
        generic = {"보험", "상품", "건강", "종합", "연금", "환급", "won", "우리won", "납입", "납입특약", "특약보험료", "보험료"}
        return {token for token in tokens if token not in generic}

    def _specific_shared_tokens(self, left: ProductBlockCandidate, right: ProductBlockCandidate) -> set[str]:
        korean_generic = {
            "보험",
            "상품",
            "건강",
            "종합",
            "보장",
            "특약",
            "담보",
            "보험료",
            "무배당",
            "갱신형",
            "해약환급금",
            "고객",
            "대상",
            "전용",
            "위한",
            "가입",
            "플랜",
            "서비스",
            "할인",
            "장기",
            "간편",
            "기간",
            "수술특약",
            "건강보험",
            "종합보험",
            "보험상품",
            "수술",
            "더퍼스트",
            "퍼스트",
            "하나더퍼스트",
            "the",
            "the퍼스트",
            "won",
            "우리won",
        }
        shared = set(left.family_tokens.intersection(right.family_tokens))
        left_name_compact = self.blocking_service._compact(" ".join([left.name, *left.alias_names]))
        right_name_compact = self.blocking_service._compact(" ".join([right.name, *right.alias_names]))
        for token in left.high_info_tokens.intersection(right.high_info_tokens):
            token_compact = self.blocking_service._compact(token)
            if token_compact and token_compact in left_name_compact and token_compact in right_name_compact:
                shared.add(token)
        specific = self._specific_family_tokens(shared)
        return {
            token
            for token in specific
            if token not in korean_generic
            and len(token) >= 2
            and not self._is_context_noise_token(token)
            and self.blocking_service._compact(token) in left_name_compact
            and self.blocking_service._compact(token) in right_name_compact
        }

    @staticmethod
    def _usable_duplicate_signature(signature: str | None) -> bool:
        if not signature or is_generic_product_family_signature(signature):
            return False
        base = signature.split("|v:", 1)[0]
        compact = "".join(ch for ch in base.casefold() if ch.isalnum())
        generic_signatures = {
            "보험",
            "상품",
            "특약",
            "담보",
            "서비스",
            "신규특약",
            "수술특약",
            "암보험",
            "건강보험",
            "간병보험",
            "연금보험",
            "종신보험",
        }
        if compact in generic_signatures:
            return False
        return len(compact) >= 4

    @staticmethod
    def _is_context_noise_token(token: str) -> bool:
        folded = token.casefold()
        noise_terms = {
            "acquired",
            "article",
            "channel",
            "company",
            "coverage",
            "exclusive",
            "feature",
            "health",
            "launch",
            "marketing",
            "period",
            "product",
            "right",
            "snippet",
            "target",
            "text",
            "title",
            "type",
        }
        if folded in noise_terms:
            return True
        return any(term in token for term in ("생명", "손해", "화재", "보험사", "기사", "출시", "배타적", "사용권"))

    @staticmethod
    def _same_partner(left: ProductBlockCandidate, right: ProductBlockCandidate) -> bool:
        left_partner = left.partner_company_name or left.inferred_partner_name
        right_partner = right.partner_company_name or right.inferred_partner_name
        return bool(left_partner and right_partner and left_partner == right_partner)

    def _name_containment(self, left: str | None, right: str | None) -> bool:
        left_compact = self.blocking_service._compact(left)
        right_compact = self.blocking_service._compact(right)
        if not left_compact or not right_compact:
            return False
        if len(left_compact) == len(right_compact):
            return left_compact == right_compact
        shorter = min(left_compact, right_compact, key=len)
        longer = max(left_compact, right_compact, key=len)
        return len(shorter) >= 4 and shorter in longer

    @staticmethod
    def _signature_quality_score(signature: str, source_name: str | None = None) -> float:
        base = signature.split("|v:", 1)[0]
        score = 0.0
        if source_name:
            score += 4.0
        if "|v:" in signature:
            score += 2.0
        if 4 <= len(base) <= 18:
            score += 2.0
        if len(base) > 24:
            score -= 5.0
        if any(term in base for term in ("출시", "신상품", "보험료", "고객", "러시")):
            score -= 3.0
        return score

    @staticmethod
    def _company_name(db: Session, company_id: int | None) -> str | None:
        if company_id is None:
            return None
        company = db.get(DimCompany, company_id)
        return company.company_name_normalized if company else None
