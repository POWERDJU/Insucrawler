from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.db.models import (
    DimProduct,
    FactProductConsolidationBlock,
    FactProductConsolidationJob,
    FactProductMergeDecision,
    FactProductObservation,
)
from app.services.product_blocking_service import ProductBlock, ProductBlockCandidate, ProductBlockingService
from app.services.product_canonicalization_service import ProductCanonicalizationService
from app.services.product_duplicate_guard_service import ProductDuplicateGuardService
from app.normalizers.product_name_normalizer import is_generic_product_family_signature
from app.utils.dates import utcnow


AUTO_MERGE_MODES = {"rule_only_apply", "apply_with_llm_gray_blocks"}
WEAK_CANDIDATE_TYPES = {"weak_mention", "pronoun_or_context_reference"}
CANONICAL_CANDIDATE_TYPES = {"official_name", "launch_name", "descriptive_alias", "partner_brand_phrase"}


@dataclass
class RuleDecision:
    duplicate_product_id: int
    decision_source: str
    confidence: float
    reason: str


class ProductConsolidationService:
    def __init__(self, blocking_service: ProductBlockingService | None = None) -> None:
        self.blocking_service = blocking_service or ProductBlockingService()
        self.duplicate_guard = ProductDuplicateGuardService(blocking_service=self.blocking_service)
        self.merge_service = ProductCanonicalizationService()

    def run(
        self,
        db: Session,
        *,
        mode: str = "dry_run",
        target: str = "all_provisional",
        limit: int = 500,
        trigger_type: str = "manual",
        use_llm_for_gray_blocks: bool = False,
    ) -> dict[str, Any]:
        job = FactProductConsolidationJob(
            status="running",
            trigger_type=trigger_type,
            mode=mode,
            started_at=utcnow(),
        )
        db.add(job)
        db.flush()
        try:
            broad_blocks = self.blocking_service.build_blocks(db, target=target, limit=limit)
            blocks = self._duplicate_component_blocks(broad_blocks)
            job.block_count = len(blocks)
            job.observation_count = db.query(FactProductObservation).count()
            job.provisional_product_count = (
                db.query(DimProduct)
                .filter(DimProduct.product_status.in_(["provisional", "review"]))
                .count()
            )
            job.target_new_product_count = min(limit, db.query(DimProduct).filter(DimProduct.product_status != "merged").count())
            auto_merge_count = 0
            review_count = 0
            for block in blocks:
                block_row = self._create_block_row(db, job, block)
                canonical = self._select_canonical(db, block)
                decisions = self._rule_decisions(block, canonical)
                if decisions:
                    if mode in AUTO_MERGE_MODES:
                        for decision in decisions:
                            duplicate = db.get(DimProduct, decision.duplicate_product_id)
                            if duplicate and duplicate.product_status != "merged" and duplicate.product_id != canonical.product_id:
                                self.merge_service.merge_products(
                                    db,
                                    canonical,
                                    duplicate,
                                    decision_source=decision.decision_source,
                                    confidence=decision.confidence,
                                    reason=decision.reason,
                                    evidence_article_ids=self._block_article_ids(db, block),
                                )
                                auto_merge_count += 1
                        block_row.status = "auto_merged"
                    else:
                        auto_merge_count += len(decisions)
                        block_row.status = "pending"
                else:
                    if mode == "apply_with_llm_gray_blocks" and use_llm_for_gray_blocks and self._llm_enabled():
                        # The block-level judge hook is intentionally budget gated; current default is off.
                        block_row.status = "review"
                        review_count += 1
                    elif len(block.candidates) > 1:
                        block_row.status = "review"
                        review_count += 1
                    else:
                        block_row.status = "no_merge"
                db.flush()
            job.auto_merge_count = auto_merge_count
            job.manual_review_count = review_count
            job.status = "completed"
            job.finished_at = utcnow()
            db.commit()
            return self.get_job_detail(db, job.consolidation_job_id)
        except Exception as exc:
            job.status = "failed"
            job.error_message = str(exc)
            job.finished_at = utcnow()
            db.commit()
            raise

    def _duplicate_component_blocks(self, blocks: list[ProductBlock]) -> list[ProductBlock]:
        """Split broad context blocks into safer same-product components.

        ProductBlockingService deliberately creates wide blocks so borderline
        candidates are reviewable. Auto-merge must be narrower: each block is
        decomposed by the duplicate guard's conservative pair score before rule
        decisions run. This prevents one broad company/context block from
        choosing a bad canonical while still allowing obvious duplicate families
        to be merged without LLM calls.
        """
        component_blocks: list[ProductBlock] = []
        for block in blocks:
            components = self.duplicate_guard._duplicate_components(block.candidates)
            multi_components = [component for component in components if len(component) > 1]
            for index, component in enumerate(multi_components, start=1):
                component_block = self.blocking_service._make_block(component)
                component_block.block_key = f"{component_block.block_key}|component:{index}"
                component_block.reason = self._component_block_reason(block, component_block)
                component_blocks.append(component_block)
        return sorted(component_blocks, key=lambda item: (-len(item.candidates), item.block_key))

    @staticmethod
    def _component_block_reason(parent: ProductBlock, component: ProductBlock) -> str:
        try:
            parent_reason = json.loads(parent.reason or "{}")
        except (TypeError, json.JSONDecodeError):
            parent_reason = {"reason": parent.reason}
        try:
            component_reason = json.loads(component.reason or "{}")
        except (TypeError, json.JSONDecodeError):
            component_reason = {"reason": component.reason}
        return json.dumps(
            {
                "reason": "duplicate_component_block",
                "parent_block_key": parent.block_key,
                "component": component_reason,
                "parent_summary": {
                    "candidate_count": parent_reason.get("candidate_count"),
                    "candidate_product_ids": parent_reason.get("candidate_product_ids"),
                    "family_signatures": parent_reason.get("family_signatures"),
                },
            },
            ensure_ascii=False,
        )

    def manual_merge(self, db: Session, *, canonical_product_id: int, duplicate_product_ids: list[int], reason: str | None = None) -> dict[str, Any]:
        canonical = db.get(DimProduct, canonical_product_id)
        if not canonical:
            raise ValueError("Canonical product not found")
        decisions: list[FactProductMergeDecision] = []
        for duplicate_id in duplicate_product_ids:
            duplicate = db.get(DimProduct, duplicate_id)
            if not duplicate or duplicate.product_id == canonical.product_id or duplicate.product_status == "merged":
                continue
            decisions.append(
                self.merge_service.merge_products(
                    db,
                    canonical,
                    duplicate,
                    decision_source="manual",
                    confidence=1.0,
                    reason=reason or "manual review",
                    evidence_article_ids=[],
                    needs_review=False,
                )
            )
        db.commit()
        return {"merged_count": len(decisions), "canonical_product_id": canonical.product_id}

    def reject_merge(self, db: Session, *, block_id: int, reason: str | None = None) -> dict[str, Any]:
        block = db.get(FactProductConsolidationBlock, block_id)
        if not block:
            raise ValueError("Consolidation block not found")
        block.status = "no_merge"
        block.block_reason = "\n".join(filter(None, [block.block_reason, f"reject_reason: {reason or ''}"]))
        db.commit()
        return {"block_id": block.block_id, "status": block.status}

    def list_jobs(self, db: Session, limit: int = 50) -> list[dict[str, Any]]:
        jobs = db.query(FactProductConsolidationJob).order_by(FactProductConsolidationJob.consolidation_job_id.desc()).limit(limit).all()
        return [self._job_dict(job) for job in jobs]

    def get_job_detail(self, db: Session, job_id: int) -> dict[str, Any]:
        job = db.get(FactProductConsolidationJob, job_id)
        if not job:
            raise ValueError("Product consolidation job not found")
        blocks = (
            db.query(FactProductConsolidationBlock)
            .filter(FactProductConsolidationBlock.consolidation_job_id == job_id)
            .order_by(FactProductConsolidationBlock.block_id)
            .all()
        )
        payload = self._job_dict(job)
        payload["blocks"] = [self._block_dict(block) for block in blocks]
        return payload

    def cost_summary(self, db: Session) -> dict[str, Any]:
        observation_count = db.query(FactProductObservation).count()
        block_count = db.query(FactProductConsolidationBlock).count()
        deterministic_count = (
            db.query(FactProductMergeDecision)
            .filter(FactProductMergeDecision.decision_source.like("deterministic_%"))
            .count()
        )
        llm_count = (
            db.query(FactProductMergeDecision)
            .filter(FactProductMergeDecision.decision_source == "ai_block_judge")
            .count()
        )
        review_count = db.query(FactProductConsolidationBlock).filter(FactProductConsolidationBlock.status == "review").count()
        avoided = max(0, observation_count * max(0, observation_count - 1) // 2 - block_count)
        reduction_rate = avoided / max(1, observation_count * max(0, observation_count - 1) // 2)
        return {
            "observation_count": observation_count,
            "block_count": block_count,
            "deterministic_auto_merge_count": deterministic_count,
            "llm_call_count": llm_count,
            "llm_cache_hit_count": 0,
            "review_count": review_count,
            "estimated_pairwise_comparison_avoided": avoided,
            "estimated_call_reduction_rate": round(reduction_rate, 6),
        }

    def maybe_create_threshold_job(self, db: Session) -> bool:
        threshold = int(os.getenv("PRODUCT_CONSOLIDATION_BATCH_SIZE", "100"))
        pending = (
            db.query(FactProductObservation)
            .outerjoin(DimProduct, DimProduct.product_id == FactProductObservation.product_id)
            .filter((FactProductObservation.product_id.is_(None)) | (DimProduct.consolidation_status != "done"))
            .count()
        )
        if pending < threshold:
            return False
        self.run(
            db,
            mode=os.getenv("PRODUCT_CONSOLIDATION_AUTO_MODE", "rule_only_apply"),
            target="new_since_last_job",
            limit=threshold,
            trigger_type="threshold",
            use_llm_for_gray_blocks=False,
        )
        return True

    def _create_block_row(self, db: Session, job: FactProductConsolidationJob, block: ProductBlock) -> FactProductConsolidationBlock:
        block_row = FactProductConsolidationBlock(
            consolidation_job_id=job.consolidation_job_id,
            block_key=block.block_key,
            company_id=block.company_id,
            partner_company_name=block.partner_company_name,
            release_month_window=block.release_month_window,
            product_type_codes_json=json.dumps(block.product_type_codes, ensure_ascii=False),
            candidate_product_ids_json=json.dumps(block.candidate_product_ids, ensure_ascii=False),
            observation_ids_json=json.dumps(block.observation_ids, ensure_ascii=False),
            block_reason=block.reason,
            status="pending",
        )
        db.add(block_row)
        db.flush()
        return block_row

    def _select_canonical(self, db: Session, block: ProductBlock) -> DimProduct:
        non_empty_core_keys = {candidate.core_key for candidate in block.candidates if candidate.core_key}
        if len(non_empty_core_keys) == 1:
            product_ids = sorted(candidate.product_id for candidate in block.candidates)
            product = db.get(DimProduct, product_ids[0])
            if product is not None:
                return product
        shared_context_tokens = self._shared_context_tokens(block)
        ranked: list[tuple[tuple[float, float, int, int, int, int], DimProduct]] = []
        for candidate in block.candidates:
            product = db.get(DimProduct, candidate.product_id)
            if product is not None:
                ranked.append((self._canonical_candidate_score(product, candidate, shared_context_tokens), product))
        return sorted(ranked, key=lambda item: item[0], reverse=True)[0][1]

    @staticmethod
    def _canonical_score(product: DimProduct) -> tuple[float, float, int]:
        status_score = 2 if product.product_status == "active" else 1
        confidence = float(product.confidence_total or 0)
        length_score = min(len(product.normalized_product_name or ""), 80) / 100
        return (status_score + confidence, -float(product.product_id or 0), int(length_score * 100))

    def _canonical_candidate_score(self, product: DimProduct, candidate: ProductBlockCandidate, shared_context_tokens: set[str] | None = None) -> tuple[float, float, int, int, int, int, int, int]:
        type_score = 0.0
        if "official_name" in candidate.candidate_types:
            type_score += 3.5
        if "launch_name" in candidate.candidate_types:
            type_score += 1.5
        if candidate.candidate_types.intersection({"descriptive_alias", "partner_brand_phrase"}):
            type_score += 1.0
        if candidate.candidate_types.issubset(WEAK_CANDIDATE_TYPES) and candidate.candidate_types:
            type_score -= 3.0
        status_score = 2.0 if product.product_status == "active" else 1.0
        confidence = float(product.confidence_total or 0)
        name = product.normalized_product_name or product.raw_product_name or ""
        specificity = min(len(name), 80)
        name_tokens = self._name_tokens(name)
        shared_name_score = len(name_tokens.intersection(shared_context_tokens or set()))
        family_specificity = len(candidate.family_tokens)
        brand_score = self._canonical_brand_score(name, candidate)
        descriptive_penalty = self._canonical_descriptive_penalty(name)
        formal_suffix_score = 1 if name.endswith(("보험", "특약", "서비스", "담보", "제도")) else 0
        primary_score = type_score + status_score + brand_score + formal_suffix_score - descriptive_penalty
        return (
            primary_score,
            confidence,
            family_specificity,
            shared_name_score,
            specificity,
            len(candidate.high_info_tokens),
            len(name_tokens),
            -int(product.product_id or 0),
        )

    @staticmethod
    def _canonical_brand_score(name: str, candidate: ProductBlockCandidate) -> float:
        compact_name = "".join(ch for ch in name.casefold() if ch.isalnum())
        score = 0.0
        if any("a" <= ch <= "z" for ch in compact_name):
            score += 0.5
        brand_like_tokens = {
            token
            for token in candidate.family_tokens
            if any("a" <= ch <= "z" for ch in token.casefold()) or any(ch.isdigit() for ch in token)
        }
        if brand_like_tokens:
            score += 0.5
        if brand_like_tokens and any(token.casefold() in compact_name for token in brand_like_tokens):
            score += 1.0
        return score

    @staticmethod
    def _canonical_descriptive_penalty(name: str) -> float:
        descriptive_terms = ("해주는", "지급", "납입", "대상", "전용", "고객", "위한", "상품")
        return 1.0 if any(term in name for term in descriptive_terms) else 0.0

    def _rule_decisions(self, block: ProductBlock, canonical: DimProduct) -> list[RuleDecision]:
        decisions: list[RuleDecision] = []
        for candidate in block.candidates:
            if candidate.product_id == canonical.product_id:
                continue
            source, confidence, reason = self._merge_rule(block, canonical, candidate)
            if source:
                decisions.append(RuleDecision(candidate.product_id, source, confidence, reason))
        return decisions

    def _coherent_shared_context_block(self, block: ProductBlock) -> bool:
        if len(block.candidates) < 4:
            return False
        company_ids = {candidate.company_id for candidate in block.candidates if candidate.company_id is not None}
        if len(company_ids) > 1:
            return False
        partners = {
            candidate.partner_company_name or candidate.inferred_partner_name
            for candidate in block.candidates
            if candidate.partner_company_name or candidate.inferred_partner_name
        }
        if not partners:
            return False
        months = {candidate.release_year_month for candidate in block.candidates if candidate.release_year_month}
        if len(months) > 1:
            return False
        for index, left in enumerate(block.candidates):
            for right in block.candidates[index + 1 :]:
                if not self.blocking_service.product_type_compatible_soft(left.product_type_code, right.product_type_code):
                    return False
                if self.blocking_service._version_conflicts(left.name, right.name):
                    return False
        shared_tokens = self._shared_context_tokens(block)
        if not shared_tokens:
            return False
        partner_compact = {self.blocking_service._compact(partner) for partner in partners}
        meaningful_tokens = [
            token for token in shared_tokens
            if len(token) >= 3 and all(self.blocking_service._compact(token) not in partner for partner in partner_compact)
        ]
        return bool(meaningful_tokens)

    def _shared_context_tokens(self, block: ProductBlock) -> set[str]:
        token_sets = [candidate.high_info_tokens for candidate in block.candidates if candidate.high_info_tokens]
        if not token_sets:
            return set()
        return set.intersection(*token_sets)

    def _name_tokens(self, name: str | None) -> set[str]:
        return self.blocking_service.extract_high_info_tokens(name or "")

    def _merge_rule(self, block: ProductBlock, canonical: DimProduct, duplicate: ProductBlockCandidate) -> tuple[str | None, float, str]:
        canonical_candidate = next(item for item in block.candidates if item.product_id == canonical.product_id)
        if canonical.company_id and duplicate.company_id and canonical.company_id != duplicate.company_id:
            return None, 0.0, "known company differs"
        if not self.blocking_service.product_type_compatible_soft(canonical.primary_product_type_code, duplicate.product_type_code):
            return None, 0.0, "product type differs"
        if self.blocking_service._version_conflicts(canonical.normalized_product_name or canonical.raw_product_name, duplicate.name):
            return None, 0.0, "version differs"
        if canonical_candidate.version_signature and duplicate.version_signature and canonical_candidate.version_signature != duplicate.version_signature:
            return None, 0.0, "version differs"
        if self.duplicate_guard._versionless_ambiguous_pair(canonical_candidate, duplicate, block.candidates):
            return None, 0.0, "versionless alias is ambiguous across product versions"
        if canonical.product_core_key and duplicate.core_key and canonical.product_core_key == duplicate.core_key:
            return "deterministic_core_key", 0.98, "same company and product_core_key"

        similarity = self.blocking_service.name_similarity(canonical.normalized_product_name, duplicate.name)
        context_similarity = self.blocking_service.context_similarity(canonical_candidate, duplicate)
        family_overlap = self.blocking_service.family_token_overlap(canonical_candidate, duplicate)
        shared_tokens = canonical_candidate.high_info_tokens.intersection(duplicate.high_info_tokens)
        specific_shared_tokens = self.duplicate_guard._specific_shared_tokens(canonical_candidate, duplicate)
        close_month_1 = not self.blocking_service._month_distance_too_far(canonical.release_year_month, duplicate.release_year_month, max_months=1)
        close_month_3 = not self.blocking_service._month_distance_too_far(canonical.release_year_month, duplicate.release_year_month, max_months=3)
        close_month_6 = not self.blocking_service._month_distance_too_far(canonical.release_year_month, duplicate.release_year_month, max_months=6)
        canonical_partner = canonical_candidate.partner_company_name or canonical_candidate.inferred_partner_name
        duplicate_partner = duplicate.partner_company_name or duplicate.inferred_partner_name
        same_partner = bool(canonical_partner and duplicate_partner and canonical_partner == duplicate_partner)
        same_company = bool(canonical_candidate.company_id and canonical_candidate.company_id == duplicate.company_id)

        if same_company and close_month_6 and self._clean_identity_match(canonical_candidate, duplicate):
            return (
                "deterministic_same_company_clean_identity",
                0.97,
                "same company/version and same product identity after legal prefix/suffix cleanup",
            )

        if same_company and close_month_3 and self._official_absorbs_generic_description(canonical_candidate, duplicate, specific_shared_tokens):
            return (
                "deterministic_same_company_official_absorbs_description",
                0.91,
                "official product name absorbs same-context generic/descriptive alias",
            )

        if self.blocking_service._specific_family_conflicts(canonical_candidate, duplicate):
            return None, 0.0, "specific product family differs"

        if same_company and close_month_3 and self.blocking_service._birth_benefit_component_match(canonical_candidate, duplicate):
            return (
                "deterministic_same_company_birth_benefit_component",
                0.93,
                "same company close-month birth/pregnancy benefit component family",
            )

        if same_company and close_month_3 and self._optional_modifier_identity(canonical_candidate, duplicate):
            return (
                "deterministic_same_company_optional_modifier_identity",
                0.97,
                "same company/version and same product identity after optional mid-token normalization",
            )

        if same_company and close_month_3 and canonical_candidate.family_signature and canonical_candidate.family_signature == duplicate.family_signature:
            if not is_generic_product_family_signature(canonical_candidate.family_signature):
                if self._has_family_context_overlap(canonical_candidate, duplicate):
                    return (
                        "deterministic_same_company_family_signature",
                        0.96,
                        f"same company and product family signature {canonical_candidate.family_signature}",
                    )

        if same_company and close_month_3 and family_overlap >= 0.70 and similarity >= 0.75:
            return (
                "deterministic_same_company_family_tokens",
                min(0.94, max(family_overlap, similarity)),
                f"same company family token overlap {family_overlap:.2f} and name similarity {similarity:.2f}",
            )

        if same_company and close_month_3 and family_overlap >= 0.45 and similarity >= 0.74 and len(specific_shared_tokens) >= 2:
            return (
                "deterministic_same_company_specific_family_similarity",
                min(0.94, max(family_overlap, similarity)),
                f"same company specific product tokens {sorted(specific_shared_tokens)[:8]} and name similarity {similarity:.2f}",
            )

        if (
            same_company
            and close_month_3
            and family_overlap >= 0.55
            and similarity >= 0.78
            and any(len(token) >= 4 for token in specific_shared_tokens)
        ):
            return (
                "deterministic_same_company_long_specific_token_similarity",
                min(0.93, max(family_overlap, similarity)),
                f"same company long product token {sorted(specific_shared_tokens)[:8]} and name similarity {similarity:.2f}",
            )

        if (
            same_company
            and close_month_3
            and specific_shared_tokens
            and any(len(token) >= 4 for token in specific_shared_tokens)
            and context_similarity >= 0.36
            and (family_overlap >= 0.45 or similarity >= 0.55)
        ):
            return (
                "deterministic_same_company_contextual_specific_alias",
                min(0.91, max(context_similarity, family_overlap, similarity, 0.86)),
                f"same company contextual product alias with shared tokens {sorted(specific_shared_tokens)[:8]}",
            )

        if same_company and close_month_3 and self.blocking_service._same_company_refund_family(canonical_candidate, duplicate):
            return (
                "deterministic_same_company_refund_family",
                0.92,
                "same company close-month refund product family without conflicting specific family tokens",
            )

        if same_company and close_month_3 and self._alias_family_overlap(canonical_candidate, duplicate):
            return (
                "deterministic_same_company_alias_overlap",
                0.95,
                "same company alias/observation family signature overlap",
            )

        if same_company and close_month_3 and self._generic_short_alias_of_specific_product(canonical_candidate, duplicate):
            return (
                "deterministic_same_company_generic_alias_containment",
                max(0.90, min(0.95, max(similarity, context_similarity, family_overlap))),
                "same company close-month product where a short generic alias is contained in a more specific product name",
            )

        if same_company and close_month_3 and family_overlap >= 0.70 and canonical.product_status == "active":
            return (
                "deterministic_same_company_active_provisional_merge",
                min(0.93, max(family_overlap, context_similarity)),
                f"provisional/active same company family overlap {family_overlap:.2f}",
            )

        if duplicate.candidate_types and duplicate.candidate_types.issubset(WEAK_CANDIDATE_TYPES) and (context_similarity >= 0.60 or len(shared_tokens) >= 1):
            return "deterministic_weak_mention_alias", 0.9, f"weak mention attached to stronger canonical product in same context ({context_similarity:.2f})"
        if close_month_3 and len(specific_shared_tokens) >= 2 and context_similarity >= 0.80 and similarity >= 0.70:
            return "deterministic_context_high_similarity", min(0.95, context_similarity), f"context similarity {context_similarity:.2f} and name similarity {similarity:.2f}"
        if close_month_3 and len(specific_shared_tokens) >= 2 and similarity >= 0.58 and context_similarity >= 0.55:
            return "deterministic_context_containment", min(0.93, max(context_similarity, similarity)), f"shared product tokens {sorted(specific_shared_tokens)[:8]}"
        if canonical_candidate.company_id is None and duplicate.company_id is None and same_partner and context_similarity >= 0.85 and similarity >= 0.65:
            return "deterministic_unknown_partner_context", min(0.94, context_similarity), f"same inferred partner and context similarity {context_similarity:.2f}"

        same_type = self.blocking_service.product_type_compatible_soft(canonical.primary_product_type_code, duplicate.product_type_code)
        close_month = not self.blocking_service._month_distance_too_far(canonical.release_year_month, duplicate.release_year_month, max_months=1)
        if same_type and close_month and similarity >= 0.92:
            return "deterministic_high_similarity", min(0.97, similarity), f"high name similarity {similarity:.2f}"
        if same_type and similarity >= 0.9:
            return "deterministic_containment", min(0.95, similarity), f"name containment/similarity {similarity:.2f}"
        if canonical_candidate.company_id is None and duplicate.company_id is None and same_partner and similarity >= 0.86:
            return "deterministic_partner_context", min(0.94, similarity), f"same partner context and name similarity {similarity:.2f}"
        return None, 0.0, "gray block"

    def _generic_short_alias_of_specific_product(self, canonical: ProductBlockCandidate, duplicate: ProductBlockCandidate) -> bool:
        canonical_specific = self.blocking_service._specific_family_tokens(canonical.family_tokens)
        duplicate_specific = self.blocking_service._specific_family_tokens(duplicate.family_tokens)
        if not canonical_specific and not duplicate_specific:
            return False
        if canonical_specific and duplicate_specific and not self.blocking_service._token_sets_have_containment(canonical_specific, duplicate_specific):
            return False
        canonical_compact = self.blocking_service._compact(canonical.name)
        duplicate_compact = self.blocking_service._compact(duplicate.name)
        if not canonical_compact or not duplicate_compact:
            return False
        if len(canonical_compact) == len(duplicate_compact) and canonical_compact != duplicate_compact:
            return False
        shorter = min(canonical_compact, duplicate_compact, key=len)
        longer = max(canonical_compact, duplicate_compact, key=len)
        if len(shorter) < 3 or shorter not in longer:
            return False
        generic_terms = {"보험", "상품", "건강보험", "펫보험", "종신보험", "연금보험"}
        return shorter in generic_terms or bool(canonical.family_tokens.intersection(duplicate.family_tokens))

    def _clean_identity_match(self, left: ProductBlockCandidate, right: ProductBlockCandidate) -> bool:
        left_keys = self._clean_identity_keys(left.name)
        right_keys = self._clean_identity_keys(right.name)
        shared = left_keys.intersection(right_keys)
        return any(len(key) >= 5 for key in shared)

    def _official_absorbs_generic_description(
        self,
        canonical: ProductBlockCandidate,
        duplicate: ProductBlockCandidate,
        specific_shared_tokens: set[str],
    ) -> bool:
        if "official_name" not in canonical.candidate_types:
            return False
        if "official_name" in duplicate.candidate_types:
            return False
        if not specific_shared_tokens:
            return False
        canonical_compact = self.blocking_service._compact(canonical.name)
        duplicate_compact = self.blocking_service._compact(duplicate.name)
        if not canonical_compact or not duplicate_compact:
            return False
        if len(duplicate_compact) < 4:
            return False
        if duplicate_compact in canonical_compact:
            return True
        if canonical_compact in duplicate_compact:
            extra = duplicate_compact.replace(canonical_compact, "", 1)
            return self._description_extra_is_safe(extra)

        canonical_specific = self.blocking_service._specific_family_tokens(canonical.family_tokens)
        duplicate_specific = self.blocking_service._specific_family_tokens(duplicate.family_tokens)
        if not canonical_specific or not duplicate_specific:
            return False
        if not (canonical_specific.intersection(duplicate_specific) or specific_shared_tokens):
            return False
        extra_tokens = duplicate_specific - canonical_specific
        if not extra_tokens:
            return True
        return all(self._description_token_is_safe(token) for token in extra_tokens)

    @staticmethod
    def _description_extra_is_safe(value: str) -> bool:
        if not value:
            return True
        unsafe_markers = {"365", "연간", "직거래", "원팀", "선물하기", "취소", "위약금", "자동차", "원데이"}
        if any(marker in value for marker in unsafe_markers):
            return False
        safe_markers = {
            "최대",
            "까지",
            "보장",
            "보장하는",
            "고령층",
            "강화",
            "강화한",
            "치매",
            "치료",
            "장기",
            "요양",
            "동시에",
            "통합",
            "형",
            "무배당",
            "무",
        }
        reduced = value
        for marker in sorted(safe_markers, key=len, reverse=True):
            reduced = reduced.replace(marker, "")
        reduced = "".join(ch for ch in reduced if not ch.isdigit())
        return len(reduced) <= 2

    @staticmethod
    def _description_token_is_safe(token: str) -> bool:
        compact = "".join(ch for ch in (token or "").casefold() if ch.isalnum())
        if not compact:
            return True
        unsafe = {"365", "연간", "직거래", "원팀", "선물하기", "취소", "위약금", "자동차", "원데이"}
        if any(marker in compact for marker in unsafe):
            return False
        safe = {
            "최대",
            "100세까지",
            "고령층",
            "강화한",
            "강화",
            "치매",
            "치료와",
            "치료",
            "요양을",
            "요양",
            "동시에",
            "하는간병",
            "보장",
            "보장하는",
            "통합",
        }
        return compact in safe or any(marker in compact for marker in safe)

    @staticmethod
    def _clean_identity_keys(name: str | None) -> set[str]:
        value = "".join(ch for ch in (name or "").casefold() if ch.isalnum())
        if not value:
            return set()
        if value.startswith("the"):
            value = "더" + value[3:]
        value = value.replace("건상생활", "건강생활")
        value = value.replace("건상", "건강")

        def strip_noise(text_value: str) -> str:
            for prefix in ("무배당", "무"):
                if text_value.startswith(prefix) and len(text_value) - len(prefix) >= 5:
                    text_value = text_value[len(prefix) :]
                    break
            changed = True
            suffixes = (
                "해약환급금미지급형",
                "해약환급금일부지급형",
                "해약환급금",
                "미지급형",
                "일부지급형",
                "비갱신형",
                "갱신형",
                "개정",
                "상품",
            )
            while changed:
                changed = False
                for suffix in suffixes:
                    if text_value.endswith(suffix) and len(text_value) - len(suffix) >= 5:
                        text_value = text_value[: -len(suffix)]
                        changed = True
                        break
            return text_value

        keys = {strip_noise(value)}
        for key in list(keys):
            if len(key) >= 6 and key[0].isascii() and key[0].isalpha():
                keys.add(key[1:])
        return {key for key in keys if len(key) >= 5}

    def _optional_modifier_identity(self, left: ProductBlockCandidate, right: ProductBlockCandidate) -> bool:
        if not left.version_signature or not right.version_signature or left.version_signature != right.version_signature:
            return False
        shared_family_tokens = left.family_tokens.intersection(right.family_tokens)
        if len(shared_family_tokens) < 2:
            return False
        left_compact = self._optional_modifier_compact(left.name)
        right_compact = self._optional_modifier_compact(right.name)
        if not left_compact or not right_compact:
            return False
        return left_compact == right_compact or left_compact in right_compact or right_compact in left_compact

    @staticmethod
    def _optional_modifier_compact(name: str | None) -> str:
        value = "".join(ch for ch in (name or "").casefold() if ch.isalnum() or ch == ".")
        for token in ("건강", "종합", "보험", "무배당"):
            value = value.replace(token, "")
        return value

    @staticmethod
    def _has_family_context_overlap(left: ProductBlockCandidate, right: ProductBlockCandidate) -> bool:
        if left.alias_names and right.alias_names:
            left_aliases = {item.casefold().replace(" ", "") for item in left.alias_names}
            right_aliases = {item.casefold().replace(" ", "") for item in right.alias_names}
            if left_aliases.intersection(right_aliases):
                return True
        if left.family_tokens.intersection(right.family_tokens):
            return True
        return bool(left.high_info_tokens.intersection(right.high_info_tokens))

    @staticmethod
    def _alias_family_overlap(left: ProductBlockCandidate, right: ProductBlockCandidate) -> bool:
        if not left.family_signature or not right.family_signature:
            return False
        if is_generic_product_family_signature(left.family_signature) or is_generic_product_family_signature(right.family_signature):
            return False
        return left.family_signature == right.family_signature

    def _block_article_ids(self, db: Session, block: ProductBlock) -> list[int]:
        if not block.observation_ids:
            return []
        rows = (
            db.query(FactProductObservation.article_id)
            .filter(FactProductObservation.observation_id.in_(block.observation_ids), FactProductObservation.article_id.isnot(None))
            .distinct()
            .all()
        )
        return [int(row[0]) for row in rows if row[0] is not None]

    @staticmethod
    def _llm_enabled() -> bool:
        return os.getenv("PRODUCT_CONSOLIDATION_LLM_ENABLED", "false").strip().lower() in {"1", "true", "yes", "y", "on"}

    @staticmethod
    def _job_dict(job: FactProductConsolidationJob) -> dict[str, Any]:
        return {
            "consolidation_job_id": job.consolidation_job_id,
            "status": job.status,
            "trigger_type": job.trigger_type,
            "mode": job.mode,
            "target_new_product_count": job.target_new_product_count,
            "observation_count": job.observation_count,
            "provisional_product_count": job.provisional_product_count,
            "block_count": job.block_count,
            "auto_merge_count": job.auto_merge_count,
            "llm_review_count": job.llm_review_count,
            "manual_review_count": job.manual_review_count,
            "llm_call_count": job.llm_call_count,
            "estimated_cost_usd": job.estimated_cost_usd,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "finished_at": job.finished_at.isoformat() if job.finished_at else None,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "error_message": job.error_message,
        }

    @staticmethod
    def _block_dict(block: FactProductConsolidationBlock) -> dict[str, Any]:
        return {
            "block_id": block.block_id,
            "block_key": block.block_key,
            "company_id": block.company_id,
            "partner_company_name": block.partner_company_name,
            "release_month_window": block.release_month_window,
            "product_type_codes": json.loads(block.product_type_codes_json or "[]"),
            "candidate_product_ids": json.loads(block.candidate_product_ids_json or "[]"),
            "observation_ids": json.loads(block.observation_ids_json or "[]"),
            "block_reason": block.block_reason,
            "status": block.status,
        }
