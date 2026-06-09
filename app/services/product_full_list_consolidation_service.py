from __future__ import annotations

import csv
import json
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import DimCompany, DimProduct, FactArticle, FactProductArticle
from app.normalizers.product_name_normalizer import is_generic_product_family_signature, version_signature
from app.services.product_blocking_service import ProductBlockCandidate, ProductBlockingService
from app.services.product_canonicalization_service import ProductCanonicalizationService
from app.services.product_duplicate_guard_service import ProductDuplicateGuardService
from app.services.product_llm_consolidation_service import ProductLLMConsolidationService, TASK_TYPE


DEFAULT_PLAN_PATH = Path("data/exports/product_full_list_llm_merge_plan.csv")


class ProductFullListConsolidationService:
    """Company-level product list consolidation.

    This is intentionally separate from article extraction. It reviews compact
    catalog rows for one company at a time, asks an optional LLM for a merge
    plan, then applies only groups that pass deterministic validation.
    """

    def __init__(
        self,
        *,
        blocking_service: ProductBlockingService | None = None,
        llm_service: ProductLLMConsolidationService | None = None,
    ) -> None:
        self.blocking_service = blocking_service or ProductBlockingService()
        self.llm_service = llm_service or ProductLLMConsolidationService(blocking_service=self.blocking_service)
        self.merge_service = ProductCanonicalizationService()
        self.duplicate_guard = ProductDuplicateGuardService(blocking_service=self.blocking_service)

    def build_company_product_groups(
        self,
        db: Session,
        *,
        target: str = "all",
        company_name: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        candidates = self.blocking_service._load_candidates(db, target="all", limit=int(limit or 0))
        candidates = [candidate for candidate in candidates if self._candidate_in_target(db, candidate, target)]
        return self._build_groups_from_candidates(db, candidates, company_name=company_name)

    def build_product_id_groups(
        self,
        db: Session,
        product_ids: list[int] | set[int],
        *,
        company_name: str | None = None,
    ) -> list[dict[str, Any]]:
        selected_ids = {int(product_id) for product_id in product_ids}
        if not selected_ids:
            return []
        candidates = self.blocking_service._load_candidates(db, target="all", limit=0)
        candidates = [candidate for candidate in candidates if candidate.product_id in selected_ids]
        return self._build_groups_from_candidates(db, candidates, company_name=company_name)

    def _build_groups_from_candidates(
        self,
        db: Session,
        candidates: list[ProductBlockCandidate],
        *,
        company_name: str | None = None,
    ) -> list[dict[str, Any]]:
        if company_name:
            candidates = [candidate for candidate in candidates if self._company_name(db, candidate.company_id) == company_name]

        grouped: dict[str, list[ProductBlockCandidate]] = defaultdict(list)
        for candidate in candidates:
            product = db.get(DimProduct, candidate.product_id)
            if not product or (product.product_status or "active") == "merged":
                continue
            if product.company_id is not None:
                group_key = f"company:{product.company_id}"
            else:
                partner = candidate.partner_company_name or candidate.inferred_partner_name or "unknown"
                source = (candidate.source_urls[0] if candidate.source_urls else "unknown")[:120]
                group_key = f"unknown:{partner}:{source}"
            grouped[group_key].append(candidate)

        groups: list[dict[str, Any]] = []
        for group_key, group_candidates in grouped.items():
            if len(group_candidates) <= 1:
                continue
            for chunk_index, chunk in enumerate(self._chunk_candidates(group_candidates), start=1):
                if len(chunk) <= 1:
                    continue
                company_ids = sorted({candidate.company_id for candidate in chunk if candidate.company_id is not None})
                groups.append(
                    {
                        "group_key": f"{group_key}:chunk:{chunk_index}",
                        "company_id": company_ids[0] if len(company_ids) == 1 else None,
                        "company_name": self._company_name(db, company_ids[0]) if len(company_ids) == 1 else None,
                        "candidates": chunk,
                    }
                )
        return groups

    def product_ids_for_article_scope(
        self,
        db: Session,
        *,
        crawl_job_id: int | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[int]:
        query = (
            db.query(DimProduct.product_id)
            .join(FactProductArticle, FactProductArticle.product_id == DimProduct.product_id)
            .join(FactArticle, FactArticle.article_id == FactProductArticle.article_id)
            .filter(
                DimProduct.product_status.in_(["active", "provisional", "review"]),
                func.coalesce(FactProductArticle.extraction_status, "saved").notin_(["excluded_multi_company", "excluded_article_eligibility"]),
            )
        )
        if crawl_job_id is not None:
            query = query.filter(FactArticle.crawl_job_id == crawl_job_id)
        if date_from:
            query = query.filter(func.date(FactArticle.pub_date) >= date_from)
        if date_to:
            query = query.filter(func.date(FactArticle.pub_date) <= date_to)
        return [int(row[0]) for row in query.distinct().order_by(DimProduct.product_id).all()]

    def build_compact_company_payload(self, db: Session, group: dict[str, Any]) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        for candidate in group["candidates"]:
            product = db.get(DimProduct, candidate.product_id)
            if not product:
                continue
            rows.append(
                {
                    "product_id": product.product_id,
                    "company_id": product.company_id,
                    "company_name": group.get("company_name") or product.company_name_raw,
                    "product_name": product.normalized_product_name,
                    "raw_product_name": product.raw_product_name,
                    "aliases": candidate.alias_names[:12],
                    "release_year_month": product.release_year_month,
                    "product_type": product.primary_product_type_code,
                    "article_titles": candidate.article_titles[:6],
                    "family_signature": candidate.family_signature,
                    "family_tokens": sorted(candidate.family_tokens),
                    "version_signature": sorted(candidate.version_signature),
                    "status": product.product_status,
                }
            )
        return {
            "task": "product_list_consolidation",
            "company_id": group.get("company_id"),
            "company_name": group.get("company_name"),
            "rules": {
                "same_company_only": True,
                "merge_same_product_variants": True,
                "do_not_merge_different_products": True,
                "do_not_merge_conflicting_versions": True,
                "return_merge_plan_only": True,
                "alias_cleanup_for_different_family": True,
            },
            "products": rows,
        }

    def run_llm_company_product_review(self, db: Session, group: dict[str, Any]) -> tuple[dict[str, Any], Any]:
        payload = self.build_compact_company_payload(db, group)
        prompt = self._prompt(payload)
        return self.llm_service._run_llm_with_cache(db, prompt, TASK_TYPE)

    def validate_product_merge_plan(self, db: Session, group: dict[str, Any], plan: dict[str, Any]) -> list[dict[str, Any]]:
        candidate_map = {candidate.product_id: candidate for candidate in group["candidates"]}
        rows: list[dict[str, Any]] = []
        for merge_group in plan.get("merge_groups") or []:
            rows.append(self.validate_product_llm_merge_group(db, group, candidate_map, merge_group))
        for cleanup in plan.get("alias_cleanup") or []:
            rows.append(self.validate_alias_cleanup(db, group, candidate_map, cleanup))
        for review in plan.get("review_items") or []:
            rows.append(
                {
                    "item_type": "review",
                    "group_key": group["group_key"],
                    "canonical_id": None,
                    "canonical_name": "",
                    "merge_ids": json.dumps(review.get("ids") or [], ensure_ascii=False),
                    "alias_name": "",
                    "confidence": 0.0,
                    "validator_status": "review",
                    "action": "review",
                    "reason": review.get("reason") or "LLM marked review",
                    "review_reason": review.get("reason") or "LLM marked review",
                }
            )
        return rows

    def validate_product_llm_merge_group(
        self,
        db: Session,
        group: dict[str, Any],
        candidate_map: dict[int, ProductBlockCandidate],
        merge_group: dict[str, Any],
    ) -> dict[str, Any]:
        canonical_id = self._int_or_none(merge_group.get("canonical_id"))
        merge_ids = [item for item in (self._int_or_none(value) for value in merge_group.get("merge_ids") or []) if item]
        if canonical_id in merge_ids:
            merge_ids = [item for item in merge_ids if item != canonical_id]
        confidence = self._confidence_float(merge_group.get("confidence"))
        canonical_name = str(merge_group.get("canonical_name") or "")
        hard_reasons: list[str] = []
        soft_reasons: list[str] = []

        if canonical_id not in candidate_map:
            hard_reasons.append("canonical_id outside company payload")
        if any(item not in candidate_map for item in merge_ids):
            hard_reasons.append("merge_ids outside company payload")
        if confidence < 0.85:
            hard_reasons.append("confidence below 0.85")
        if not merge_ids:
            hard_reasons.append("no merge_ids")
        if self.llm_service._is_generic_canonical_name(canonical_name):
            hard_reasons.append("generic canonical name")

        products = [db.get(DimProduct, item) for item in [canonical_id, *merge_ids] if item]
        products = [product for product in products if product is not None]
        known_companies = {product.company_id for product in products if product.company_id is not None}
        if len(known_companies) > 1:
            hard_reasons.append("known company differs")

        canonical_candidate = candidate_map.get(canonical_id) if canonical_id else None
        for merge_id in merge_ids:
            merge_candidate = candidate_map.get(merge_id)
            if not canonical_candidate or not merge_candidate:
                continue
            if not self.blocking_service.product_type_compatible_soft(canonical_candidate.product_type_code, merge_candidate.product_type_code):
                soft_reasons.append(f"product type conflict: {merge_id}")
            if self.blocking_service._specific_family_conflicts(canonical_candidate, merge_candidate):
                soft_reasons.append(f"specific family conflict: {merge_id}")
            if canonical_candidate.version_signature and merge_candidate.version_signature and canonical_candidate.version_signature != merge_candidate.version_signature:
                hard_reasons.append(f"version conflict: {merge_id}")
            canonical_versions = version_signature(canonical_name)
            if canonical_versions and merge_candidate.version_signature and canonical_versions != merge_candidate.version_signature:
                hard_reasons.append(f"canonical version conflict: {merge_id}")
            if self.blocking_service._month_distance_too_far(canonical_candidate.release_year_month, merge_candidate.release_year_month, max_months=6):
                hard_reasons.append(f"release month too far: {merge_id}")
            if not self._has_family_overlap(canonical_candidate, merge_candidate, canonical_name):
                soft_reasons.append(f"insufficient family token overlap: {merge_id}")
            if self._has_product_class_conflict(canonical_candidate, merge_candidate, canonical_name):
                hard_reasons.append(f"product class conflict: {merge_id}")

        broad_allowed = (
            not hard_reasons
            and bool(soft_reasons)
            and confidence >= 0.9
            and canonical_candidate is not None
            and all(
                self._has_broad_context_anchor(canonical_candidate, candidate_map[merge_id], canonical_name, str(merge_group.get("reason") or ""))
                for merge_id in merge_ids
                if merge_id in candidate_map
            )
        )
        reasons = hard_reasons if hard_reasons else ([] if not soft_reasons or broad_allowed else soft_reasons)
        status = "valid" if not reasons else "review"
        return {
            "item_type": "merge_group",
            "group_key": group["group_key"],
            "canonical_id": canonical_id,
            "canonical_name": canonical_name,
            "merge_ids": json.dumps(merge_ids, ensure_ascii=False),
            "alias_name": "",
            "confidence": confidence,
            "validator_status": status,
            "action": "auto_apply" if status == "valid" else "review",
            "reason": merge_group.get("reason") or "",
            "review_reason": "; ".join(dict.fromkeys(soft_reasons if broad_allowed else reasons)),
        }

    def validate_alias_cleanup(
        self,
        db: Session,
        group: dict[str, Any],
        candidate_map: dict[int, ProductBlockCandidate],
        cleanup: dict[str, Any],
    ) -> dict[str, Any]:
        product_id = self._int_or_none(cleanup.get("product_id"))
        alias_name = str(cleanup.get("alias_name") or "")
        product = db.get(DimProduct, product_id) if product_id else None
        reasons: list[str] = []
        if product_id not in candidate_map or not product:
            reasons.append("product_id outside company payload")
        elif self.duplicate_guard.alias_is_compatible(product, alias_name):
            reasons.append("alias still compatible with canonical product")
        if not alias_name:
            reasons.append("missing alias_name")
        status = "valid" if not reasons else "review"
        return {
            "item_type": "alias_cleanup",
            "group_key": group["group_key"],
            "canonical_id": product_id,
            "canonical_name": product.normalized_product_name if product else "",
            "merge_ids": "[]",
            "alias_name": alias_name,
            "confidence": self._confidence_float(cleanup.get("confidence")),
            "validator_status": status,
            "action": "alias_cleanup_review" if status == "valid" else "review",
            "reason": cleanup.get("reason") or "",
            "review_reason": "; ".join(dict.fromkeys(reasons)),
        }

    def apply_product_merge_plan(self, db: Session, rows: list[dict[str, Any]], *, dry_run: bool) -> dict[str, int]:
        applied = 0
        review = 0
        alias_cleanup = 0
        if dry_run:
            return {
                "applied": 0,
                "review": sum(1 for row in rows if row.get("action") not in {"auto_apply", "alias_cleanup_review"}),
                "alias_cleanup": sum(1 for row in rows if row.get("action") == "alias_cleanup_review"),
            }
        for row in rows:
            if row.get("action") == "alias_cleanup_review":
                alias_cleanup += 1
                continue
            if row.get("action") != "auto_apply":
                review += 1
                continue
            canonical = db.get(DimProduct, row.get("canonical_id"))
            if not canonical:
                review += 1
                continue
            for duplicate_id in self._json_int_list(row.get("merge_ids")):
                duplicate = db.get(DimProduct, duplicate_id)
                if not duplicate or duplicate.product_id == canonical.product_id or duplicate.product_status == "merged":
                    continue
                self.merge_service.merge_products(
                    db,
                    canonical,
                    duplicate,
                    decision_source="ai_company_full_list_judge",
                    confidence=float(row.get("confidence") or 0),
                    reason=row.get("reason") or "LLM company full-list merge plan passed deterministic validation.",
                    evidence_article_ids=[],
                )
                applied += 1
        db.flush()
        return {"applied": applied, "review": review, "alias_cleanup": alias_cleanup}

    def run_full_list_consolidation(
        self,
        db: Session,
        *,
        mode: str = "dry_run",
        target: str = "all",
        company_name: str | None = None,
        limit: int | None = None,
        max_companies: int | None = None,
        max_blocks: int | None = None,
        plan_file: str | Path = DEFAULT_PLAN_PATH,
    ) -> dict[str, Any]:
        if mode not in {"dry_run", "apply"}:
            raise ValueError("mode must be dry_run or apply")
        if not self._enabled():
            return {
                "status": "disabled",
                "company_group_count": 0,
                "llm_call_count": 0,
                "auto_apply_count": 0,
                "review_count": 0,
                "alias_cleanup_count": 0,
                "estimated_cost_usd": 0.0,
                "plan_file": str(plan_file),
            }
        company_limit = max_companies if max_companies is not None else int(os.getenv("PRODUCT_LLM_CONSOLIDATION_MAX_COMPANIES_PER_JOB", "50"))
        block_limit = max_blocks if max_blocks is not None else int(os.getenv("PRODUCT_LLM_CONSOLIDATION_MAX_CALLS_PER_JOB", "30"))
        groups = self.build_company_product_groups(db, target=target, company_name=company_name, limit=limit)
        if company_limit:
            groups = groups[:company_limit]

        max_cost = float(os.getenv("PRODUCT_LLM_CONSOLIDATION_MAX_COST_USD_PER_JOB", "3.0"))
        rows: list[dict[str, Any]] = []
        llm_call_count = 0
        estimated_cost = 0.0
        for group in groups:
            if llm_call_count >= block_limit or estimated_cost >= max_cost:
                break
            plan, run = self.run_llm_company_product_review(db, group)
            llm_call_count += 0 if run.cached_yn else 1
            estimated_cost += float(run.estimated_cost_usd or 0)
            rows.extend(self.validate_product_merge_plan(db, group, plan))
        self._write_plan_csv(rows, Path(plan_file))
        apply_summary = self.apply_product_merge_plan(db, rows, dry_run=(mode == "dry_run"))
        db.commit()
        return {
            "status": "completed",
            "company_group_count": len(groups),
            "llm_call_count": llm_call_count,
            "auto_apply_count": apply_summary["applied"] if mode == "apply" else sum(1 for row in rows if row.get("action") == "auto_apply"),
            "review_count": sum(1 for row in rows if row.get("action") == "review"),
            "alias_cleanup_count": apply_summary["alias_cleanup"],
            "estimated_cost_usd": round(estimated_cost, 8),
            "plan_file": str(plan_file),
        }

    def run_product_id_consolidation(
        self,
        db: Session,
        product_ids: list[int] | set[int],
        *,
        mode: str = "dry_run",
        company_name: str | None = None,
        max_companies: int | None = None,
        max_blocks: int | None = None,
        plan_file: str | Path = DEFAULT_PLAN_PATH,
        force_enabled: bool = False,
    ) -> dict[str, Any]:
        if mode not in {"dry_run", "apply"}:
            raise ValueError("mode must be dry_run or apply")
        product_ids = sorted({int(product_id) for product_id in product_ids})
        if not product_ids:
            return {
                "status": "completed",
                "product_id_count": 0,
                "company_group_count": 0,
                "llm_call_count": 0,
                "auto_apply_count": 0,
                "review_count": 0,
                "alias_cleanup_count": 0,
                "estimated_cost_usd": 0.0,
                "plan_file": str(plan_file),
            }
        if not force_enabled and not self._enabled():
            return {
                "status": "disabled",
                "product_id_count": len(product_ids),
                "company_group_count": 0,
                "llm_call_count": 0,
                "auto_apply_count": 0,
                "review_count": 0,
                "alias_cleanup_count": 0,
                "estimated_cost_usd": 0.0,
                "plan_file": str(plan_file),
            }
        company_limit = max_companies if max_companies is not None else int(os.getenv("PRODUCT_LLM_CONSOLIDATION_MAX_COMPANIES_PER_JOB", "50"))
        block_limit = max_blocks if max_blocks is not None else int(os.getenv("PRODUCT_LLM_CONSOLIDATION_MAX_CALLS_PER_JOB", "30"))
        groups = self.build_product_id_groups(db, product_ids, company_name=company_name)
        if company_limit:
            groups = groups[:company_limit]

        max_cost = float(os.getenv("PRODUCT_LLM_CONSOLIDATION_MAX_COST_USD_PER_JOB", "3.0"))
        rows: list[dict[str, Any]] = []
        llm_call_count = 0
        estimated_cost = 0.0
        for group in groups:
            if llm_call_count >= block_limit or estimated_cost >= max_cost:
                break
            plan, run = self.run_llm_company_product_review(db, group)
            llm_call_count += 0 if run.cached_yn else 1
            estimated_cost += float(run.estimated_cost_usd or 0)
            rows.extend(self.validate_product_merge_plan(db, group, plan))
        self._write_plan_csv(rows, Path(plan_file))
        apply_summary = self.apply_product_merge_plan(db, rows, dry_run=(mode == "dry_run"))
        db.commit()
        return {
            "status": "completed",
            "product_id_count": len(product_ids),
            "company_group_count": len(groups),
            "llm_call_count": llm_call_count,
            "auto_apply_count": apply_summary["applied"] if mode == "apply" else sum(1 for row in rows if row.get("action") == "auto_apply"),
            "review_count": sum(1 for row in rows if row.get("action") == "review"),
            "alias_cleanup_count": apply_summary["alias_cleanup"],
            "estimated_cost_usd": round(estimated_cost, 8),
            "plan_file": str(plan_file),
        }

    def run_article_scope_consolidation(
        self,
        db: Session,
        *,
        mode: str = "dry_run",
        crawl_job_id: int | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        company_name: str | None = None,
        max_companies: int | None = None,
        max_blocks: int | None = None,
        plan_file: str | Path = DEFAULT_PLAN_PATH,
        force_enabled: bool = False,
    ) -> dict[str, Any]:
        product_ids = self.product_ids_for_article_scope(db, crawl_job_id=crawl_job_id, date_from=date_from, date_to=date_to)
        return self.run_product_id_consolidation(
            db,
            product_ids,
            mode=mode,
            company_name=company_name,
            max_companies=max_companies,
            max_blocks=max_blocks,
            plan_file=plan_file,
            force_enabled=force_enabled,
        )

    def _chunk_candidates(self, candidates: list[ProductBlockCandidate]) -> list[list[ProductBlockCandidate]]:
        max_products = int(os.getenv("PRODUCT_LLM_CONSOLIDATION_MAX_PRODUCTS_PER_PROMPT", "60"))
        ordered = sorted(candidates, key=lambda candidate: (candidate.family_signature or "", sorted(candidate.family_tokens), candidate.product_id))
        chunks: list[list[ProductBlockCandidate]] = []
        current: list[ProductBlockCandidate] = []
        for candidate in ordered:
            if current and len(current) >= max_products:
                chunks.append(current)
                current = []
            current.append(candidate)
        if current:
            chunks.append(current)
        return chunks

    def _candidate_in_target(self, db: Session, candidate: ProductBlockCandidate, target: str) -> bool:
        product = db.get(DimProduct, candidate.product_id)
        if not product:
            return False
        if target in {"all", "selected"}:
            return True
        if target in {"all_provisional", "new_since_last_job", "candidates"}:
            return (product.product_status or "active") in {"active", "provisional", "review"}
        return True

    def _has_family_overlap(self, canonical: ProductBlockCandidate, duplicate: ProductBlockCandidate, canonical_name: str) -> bool:
        if canonical.family_signature and duplicate.family_signature and canonical.family_signature == duplicate.family_signature:
            return not is_generic_product_family_signature(canonical.family_signature)
        overlap = self.blocking_service.family_token_overlap(canonical, duplicate)
        if overlap >= 0.45:
            return True
        canonical_name_tokens = set()
        if canonical_name:
            canonical_name_tokens.update(canonical.family_tokens)
            canonical_name_tokens.update(duplicate.family_tokens)
        return bool(canonical.family_tokens.intersection(duplicate.family_tokens)) and overlap >= 0.34

    def _has_broad_context_anchor(
        self,
        canonical: ProductBlockCandidate,
        duplicate: ProductBlockCandidate,
        canonical_name: str,
        reason: str,
    ) -> bool:
        if self._has_product_class_conflict(canonical, duplicate, canonical_name):
            return False
        shared_tokens = self._distinctive_shared_tokens(canonical, duplicate)
        if shared_tokens:
            return True
        compact_values = [
            self._compact_anchor_text(canonical.name),
            self._compact_anchor_text(duplicate.name),
            self._compact_anchor_text(canonical_name),
            self._compact_anchor_text(" ".join(canonical.alias_names[:8])),
            self._compact_anchor_text(" ".join(duplicate.alias_names[:8])),
            self._compact_anchor_text(" ".join(canonical.article_titles[:4])),
            self._compact_anchor_text(" ".join(duplicate.article_titles[:4])),
            self._compact_anchor_text(reason),
        ]
        compact = " ".join(compact_values)
        anchor_groups = (
            ("보행자사고", "변호사", "법률자문", "자문", "한문철"),
            ("5n5", "nh5n5", "5굿플러스", "굿플러스"),
            ("7배", "더행복한", "체증", "종신"),
            ("ai", "건강코칭", "헬스케어", "탑재", "결합"),
        )
        for group in anchor_groups:
            hits = {token for token in group if token in compact}
            if len(hits) >= 2:
                return True
        return False

    def _distinctive_shared_tokens(self, canonical: ProductBlockCandidate, duplicate: ProductBlockCandidate) -> set[str]:
        stop = {"보험", "상품", "건강", "특약", "보장", "서비스", "신상품", "ai"}
        left = {self._compact_anchor_text(token) for token in canonical.family_tokens if token}
        right = {self._compact_anchor_text(token) for token in duplicate.family_tokens if token}
        shared = {token for token in left.intersection(right) if token and token not in stop and len(token) >= 2}
        if shared:
            return shared
        left_text = self._compact_anchor_text(" ".join([canonical.name, *canonical.alias_names[:8], *canonical.article_titles[:4]]))
        right_text = self._compact_anchor_text(" ".join([duplicate.name, *duplicate.alias_names[:8], *duplicate.article_titles[:4]]))
        return {token for token in left.union(right) if token and token not in stop and len(token) >= 3 and token in left_text and token in right_text}

    def _has_product_class_conflict(self, canonical: ProductBlockCandidate, duplicate: ProductBlockCandidate, canonical_name: str) -> bool:
        primary_left = self._product_class_tokens(" ".join([canonical.name, canonical_name]))
        primary_right = self._product_class_tokens(duplicate.name)
        if primary_left and primary_right and primary_left.isdisjoint(primary_right):
            return True
        left_classes = self._product_class_tokens(" ".join([canonical.name, canonical_name, *canonical.alias_names[:6]]))
        right_classes = self._product_class_tokens(" ".join([duplicate.name, *duplicate.alias_names[:6]]))
        return bool(left_classes and right_classes and left_classes.isdisjoint(right_classes))

    @staticmethod
    def _product_class_tokens(value: str) -> set[str]:
        compact = re.sub(r"[^0-9A-Za-z가-힣]+", "", value or "").casefold()
        classes: set[str] = set()
        if "암" in compact:
            classes.add("cancer")
        if "정기" in compact:
            classes.add("term")
        if "종신" in compact or "wholelife" in compact:
            classes.add("whole_life")
        if "연금" in compact:
            classes.add("annuity")
        if "펫" in compact or "반려견" in compact or "반려동물" in compact:
            classes.add("pet")
        if "골프" in compact:
            classes.add("golf")
        if "여행" in compact:
            classes.add("travel")
        if "드론" in compact:
            classes.add("drone")
        return classes

    @staticmethod
    def _compact_anchor_text(value: str | None) -> str:
        return re.sub(r"[^0-9A-Za-z가-힣]+", "", value or "").casefold()

    @staticmethod
    def _prompt(payload: dict[str, Any]) -> str:
        return (
            "You are reviewing a compact product catalog for one insurer. "
            "Return JSON only. Identify rows that are the same insurance product even when news articles use shortened names. "
            "Do not merge different products from the same article. Do not merge across different known insurers. "
            "Do not merge conflicting versions. Do not choose generic canonical names such as 건강보험, 연금보험, 환급보험, 신상품, or 상품. "
            "Use article_titles, aliases, release_year_month, product_type, family_signature, family_tokens, and version_signature as compact evidence. "
            "Merge spacing, typo-like, romanized/English, subtitle, abbreviation, and article-context naming variants when they clearly refer to one "
            "same insurer product. Do not merge separate products merely because they appear in one bundle/news roundup, share broad categories, "
            "or mention a common platform, report, rider type, discount, service, or generic benefit. Prefer the most complete official Korean "
            "product name as canonical_name. Explain merge reasons in Korean when possible. "
            "Use merge_groups with canonical_id, canonical_name, merge_ids, confidence, reason. "
            "Use alias_cleanup when an alias clearly belongs to a different product family. "
            "Use review_items when unsure. Do not invent products or facts.\n\n"
            + json.dumps(payload, ensure_ascii=False)
        )

    @staticmethod
    def _enabled() -> bool:
        return os.getenv("PRODUCT_LLM_CONSOLIDATION_ENABLED", "false").lower() in {"1", "true", "yes", "y"}

    @staticmethod
    def _company_name(db: Session, company_id: int | None) -> str | None:
        if company_id is None:
            return None
        company = db.get(DimCompany, company_id)
        return company.company_name_normalized if company else None

    @staticmethod
    def _int_or_none(value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _confidence_float(value: Any) -> float:
        if isinstance(value, str):
            normalized = value.strip().lower()
            label_map = {
                "very_high": 0.95,
                "very high": 0.95,
                "high": 0.9,
                "medium": 0.7,
                "low": 0.4,
                "review": 0.0,
            }
            if normalized in label_map:
                return label_map[normalized]
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _json_int_list(value: Any) -> list[int]:
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                return []
        return [int(item) for item in value or [] if str(item).isdigit()]

    @staticmethod
    def _write_plan_csv(rows: list[dict[str, Any]], path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = [
            "item_type",
            "group_key",
            "canonical_id",
            "canonical_name",
            "merge_ids",
            "alias_name",
            "confidence",
            "validator_status",
            "action",
            "reason",
            "review_reason",
        ]
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({field: row.get(field, "") for field in fieldnames})
