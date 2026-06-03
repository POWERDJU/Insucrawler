from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import DimCompany, DimProduct, FactLLMRun
from app.llm.base import LLMProvider, LLMResponse
from app.llm.router import LLMRouter
from app.normalizers.product_name_normalizer import is_generic_product_family_signature, version_signature
from app.services.llm_cache_service import LLMCacheService
from app.services.llm_cost_service import LLMCostService
from app.services.product_blocking_service import ProductBlock, ProductBlockCandidate, ProductBlockingService
from app.services.product_canonicalization_service import ProductCanonicalizationService
from app.utils.dates import utcnow
from app.utils.hashing import sha256_text


TASK_TYPE = "product_list_consolidation"
PROMPT_VERSION = "product-list-consolidation-v1"
SCHEMA_VERSION = "merge-plan-v1"
DEFAULT_PLAN_PATH = Path("data/exports/product_llm_merge_plan.csv")
WEAK_CANONICAL_NAMES = {
    "신상품",
    "해당상품",
    "해당 상품",
    "이번상품",
    "이번 상품",
    "보험상품",
    "상품",
    "보험",
    "건강보험",
    "암보험",
    "연금보험",
}


class ProductLLMConsolidationService:
    """Optional block-level LLM merge-plan reviewer for product entity resolution.

    The LLM never mutates the DB directly. It only returns a merge plan, and
    deterministic validation decides whether an item may be applied.
    """

    def __init__(
        self,
        *,
        blocking_service: ProductBlockingService | None = None,
        router: LLMRouter | None = None,
        providers: dict[str, LLMProvider] | None = None,
    ) -> None:
        self.blocking_service = blocking_service or ProductBlockingService()
        self.router = router or LLMRouter(providers=providers)
        self.cache_service = LLMCacheService()
        self.cost_service = LLMCostService()
        self.merge_service = ProductCanonicalizationService()

    def build_product_merge_blocks(self, db: Session, target: str = "all", limit: int | None = None) -> list[ProductBlock]:
        return self.blocking_service.build_blocks(db, target=target, limit=int(limit or 0))

    def build_compact_product_block_payload(self, db: Session, block: ProductBlock) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        for candidate in block.candidates[: int(os.getenv("LLM_CONSOLIDATION_MAX_BLOCK_SIZE", "50"))]:
            product = db.get(DimProduct, candidate.product_id)
            if not product:
                continue
            company_name = None
            if product.company_id:
                company = db.get(DimCompany, product.company_id)
                company_name = company.company_name_normalized if company else None
            rows.append(
                {
                    "product_id": product.product_id,
                    "company_id": product.company_id,
                    "company_name": company_name or product.company_name_raw,
                    "product_name": product.normalized_product_name,
                    "raw_product_name": product.raw_product_name,
                    "aliases": candidate.alias_names[:10],
                    "release_year_month": product.release_year_month,
                    "product_type": product.primary_product_type_code,
                    "article_titles": candidate.article_titles[:5],
                    "article_descriptions": candidate.article_descriptions[:3],
                    "family_signature": candidate.family_signature,
                    "family_tokens": sorted(candidate.family_tokens),
                    "status": product.product_status,
                }
            )
        return {
            "task": "same_product_block_consolidation",
            "rules": {
                "same_company_only": True,
                "no_pairwise_calls": True,
                "reject_different_company": True,
                "reject_version_conflict": True,
                "reject_generic_canonical_name": True,
            },
            "block_key": block.block_key,
            "candidates": rows,
        }

    def run_llm_product_block_judge(self, db: Session, block: ProductBlock) -> tuple[dict[str, Any], FactLLMRun]:
        payload = self.build_compact_product_block_payload(db, block)
        prompt = self._product_prompt(payload)
        return self._run_llm_with_cache(db, prompt, TASK_TYPE)

    def validate_llm_product_merge_plan(self, db: Session, block: ProductBlock, plan: dict[str, Any]) -> list[dict[str, Any]]:
        block_ids = {candidate.product_id for candidate in block.candidates}
        candidates = {candidate.product_id: candidate for candidate in block.candidates}
        results: list[dict[str, Any]] = []
        for group in plan.get("merge_groups") or []:
            canonical_id = self._int_or_none(group.get("canonical_id"))
            merge_ids = [item for item in (self._int_or_none(value) for value in group.get("merge_ids") or []) if item]
            confidence = self._confidence_float(group.get("confidence"))
            reasons: list[str] = []
            if not canonical_id or canonical_id not in block_ids:
                reasons.append("canonical_id is outside block")
            if any(item not in block_ids for item in merge_ids):
                reasons.append("merge_ids contain ids outside block")
            if canonical_id in merge_ids:
                merge_ids = [item for item in merge_ids if item != canonical_id]
            if confidence < 0.85:
                reasons.append("confidence below 0.85")
            products = [db.get(DimProduct, item) for item in [canonical_id, *merge_ids] if item]
            products = [item for item in products if item is not None]
            company_ids = {item.company_id for item in products if item.company_id is not None}
            if len(company_ids) > 1:
                reasons.append("known company differs")
            canonical_name = str(group.get("canonical_name") or (products[0].normalized_product_name if products else ""))
            if self._is_generic_canonical_name(canonical_name):
                reasons.append("generic canonical name")
            canonical_candidate = candidates.get(canonical_id) if canonical_id else None
            for merge_id in merge_ids:
                merge_candidate = candidates.get(merge_id)
                if not canonical_candidate or not merge_candidate:
                    continue
                if not self.blocking_service.product_type_compatible_soft(canonical_candidate.product_type_code, merge_candidate.product_type_code):
                    reasons.append(f"product type conflict: {merge_id}")
                if canonical_candidate.version_signature and merge_candidate.version_signature and canonical_candidate.version_signature != merge_candidate.version_signature:
                    reasons.append(f"version conflict: {merge_id}")
                if version_signature(canonical_name) and merge_candidate.version_signature and version_signature(canonical_name) != merge_candidate.version_signature:
                    reasons.append(f"canonical version conflict: {merge_id}")
                if self.blocking_service._month_distance_too_far(canonical_candidate.release_year_month, merge_candidate.release_year_month, max_months=3):
                    reasons.append(f"release month too far: {merge_id}")
            status = "valid" if not reasons and merge_ids else "review"
            results.append(
                {
                    "block_id": block.block_key,
                    "candidate_ids": sorted(block_ids),
                    "candidate_names": [candidate.name for candidate in block.candidates],
                    "canonical_id": canonical_id,
                    "canonical_name": canonical_name,
                    "merge_ids": merge_ids,
                    "confidence": confidence,
                    "reason": group.get("reason") or "",
                    "validator_status": status,
                    "action": "auto_apply" if status == "valid" else "review",
                    "review_reason": "; ".join(dict.fromkeys(reasons)),
                }
            )
        for item in plan.get("review_items") or []:
            ids = [value for value in (self._int_or_none(value) for value in item.get("ids") or []) if value]
            results.append(
                {
                    "block_id": block.block_key,
                    "candidate_ids": sorted(block_ids),
                    "candidate_names": [candidate.name for candidate in block.candidates],
                    "canonical_id": None,
                    "canonical_name": "",
                    "merge_ids": ids,
                    "confidence": 0.0,
                    "reason": item.get("reason") or "",
                    "validator_status": "review",
                    "action": "review",
                    "review_reason": item.get("reason") or "LLM marked review",
                }
            )
        return results

    def apply_product_merge_plan(self, db: Session, rows: list[dict[str, Any]], dry_run: bool = True) -> dict[str, int]:
        applied = 0
        review = 0
        if dry_run:
            return {"applied": 0, "review": sum(1 for row in rows if row.get("action") != "auto_apply")}
        for row in rows:
            if row.get("action") != "auto_apply":
                review += 1
                continue
            canonical = db.get(DimProduct, row.get("canonical_id"))
            if not canonical:
                review += 1
                continue
            for duplicate_id in row.get("merge_ids") or []:
                duplicate = db.get(DimProduct, duplicate_id)
                if not duplicate or duplicate.product_id == canonical.product_id or duplicate.product_status == "merged":
                    continue
                self.merge_service.merge_products(
                    db,
                    canonical,
                    duplicate,
                    decision_source="ai_list_level_block_judge",
                    confidence=float(row.get("confidence") or 0),
                    reason=row.get("reason") or "LLM list-level merge plan passed deterministic validation.",
                    evidence_article_ids=[],
                )
                applied += 1
        db.flush()
        return {"applied": applied, "review": review}

    def run(
        self,
        db: Session,
        *,
        mode: str = "dry_run",
        target: str = "all",
        limit: int | None = None,
        max_blocks: int = 20,
        plan_file: str | Path = DEFAULT_PLAN_PATH,
    ) -> dict[str, Any]:
        if mode not in {"dry_run", "apply"}:
            raise ValueError("mode must be dry_run or apply")
        if not self._enabled():
            return {
                "job_id": None,
                "block_count": 0,
                "llm_call_count": 0,
                "auto_apply_count": 0,
                "review_count": 0,
                "estimated_cost_usd": 0.0,
                "plan_file": str(plan_file),
                "status": "disabled",
            }
        blocks = self.build_product_merge_blocks(db, target=target, limit=limit)[:max_blocks]
        all_rows: list[dict[str, Any]] = []
        llm_call_count = 0
        estimated_cost = 0.0
        max_calls = int(os.getenv("LLM_CONSOLIDATION_MAX_CALLS_PER_JOB", "20"))
        max_cost = float(os.getenv("LLM_CONSOLIDATION_MAX_COST_USD_PER_JOB", "2.0"))
        for block in blocks:
            if llm_call_count >= max_calls or estimated_cost >= max_cost:
                break
            plan, run = self.run_llm_product_block_judge(db, block)
            llm_call_count += 0 if run.cached_yn else 1
            estimated_cost += float(run.estimated_cost_usd or 0)
            all_rows.extend(self.validate_llm_product_merge_plan(db, block, plan))
        self._write_plan_csv(all_rows, Path(plan_file))
        apply_summary = self.apply_product_merge_plan(db, all_rows, dry_run=(mode == "dry_run"))
        db.commit()
        return {
            "job_id": None,
            "block_count": len(blocks),
            "llm_call_count": llm_call_count,
            "auto_apply_count": apply_summary["applied"] if mode == "apply" else sum(1 for row in all_rows if row.get("action") == "auto_apply"),
            "review_count": sum(1 for row in all_rows if row.get("action") != "auto_apply"),
            "estimated_cost_usd": round(estimated_cost, 8),
            "plan_file": str(plan_file),
        }

    def _run_llm_with_cache(self, db: Session, prompt: str, task_type: str) -> tuple[dict[str, Any], FactLLMRun]:
        provider_name = os.getenv("PRODUCT_LLM_CONSOLIDATION_PROVIDER") or os.getenv("LLM_CONSOLIDATION_PROVIDER", "gemini")
        model_name = os.getenv("PRODUCT_LLM_CONSOLIDATION_MODEL") or os.getenv("LLM_CONSOLIDATION_MODEL", "gemini-2.5-flash")
        provider = self.router._provider(provider_name, None)
        if hasattr(provider, "model_name"):
            provider.model_name = model_name
        cached = self.cache_service.get(
            db,
            input_text=prompt,
            prompt_version=PROMPT_VERSION,
            schema_version=SCHEMA_VERSION,
            provider=provider_name,
            model_name=model_name,
            task_type=task_type,
        )
        if cached is not None:
            run = self._record_run(db, prompt, cached, provider_name, model_name, task_type, cached_yn=True)
            return cached, run
        response = self._call_provider(provider, prompt, task_type)
        self.cache_service.put(
            db,
            input_text=prompt,
            prompt_version=PROMPT_VERSION,
            schema_version=SCHEMA_VERSION,
            provider=response.provider,
            model_name=response.model_name,
            task_type=task_type,
            output_json=response.output_json,
        )
        run = self._record_run(
            db,
            prompt,
            response.output_json,
            response.provider,
            response.model_name,
            task_type,
            cached_yn=False,
            response=response,
        )
        return response.output_json, run

    def _call_provider(self, provider: LLMProvider, prompt: str, task_type: str) -> LLMResponse:
        if hasattr(provider, "judge_consolidation_block"):
            return provider.judge_consolidation_block(prompt, task_type)
        if hasattr(provider, "_generate_json"):
            return provider._generate_json(prompt, task_type, None)
        if hasattr(provider, "_chat_json"):
            return provider._chat_json(prompt, task_type)
        raise RuntimeError("Provider does not support consolidation block judging")

    def _record_run(
        self,
        db: Session,
        prompt: str,
        output_json: dict[str, Any],
        provider: str,
        model_name: str,
        task_type: str,
        *,
        cached_yn: bool,
        response: LLMResponse | None = None,
    ) -> FactLLMRun:
        output_text = json.dumps(output_json, ensure_ascii=False)
        run = FactLLMRun(
            task_type=task_type,
            provider=provider,
            model_name=model_name,
            prompt_version=PROMPT_VERSION,
            schema_version=SCHEMA_VERSION,
            input_hash=sha256_text(prompt),
            output_json=output_text,
            validation_status="cached" if cached_yn else "completed",
            token_input=response.token_input if response else LLMCostService.rough_token_count(prompt),
            token_output=response.token_output if response else LLMCostService.rough_token_count(output_text),
            latency_ms=response.latency_ms if response else None,
            cost_estimate=response.cost_estimate if response else None,
            cached_yn=cached_yn,
            estimated_cost_usd=response.cost_estimate if response else None,
            created_at=utcnow(),
        )
        db.add(run)
        db.flush()
        self.cost_service.record_run(db, run, input_text=prompt, cached_tokens=run.token_input if cached_yn else 0)
        return run

    @staticmethod
    def _product_prompt(payload: dict[str, Any]) -> str:
        return (
            "You are judging whether product catalog rows are the same insurance product. "
            "Return JSON only with merge_groups, review_items, and no_merge_items. "
            "Never merge across different known insurers. Never merge conflicting versions such as 3.0 and 4.0. "
            "Do not choose generic names as canonical names. Use only the compact candidate rows below; do not invent facts.\n\n"
            + json.dumps(payload, ensure_ascii=False)
        )

    @staticmethod
    def _is_generic_canonical_name(name: str | None) -> bool:
        compact = "".join(ch for ch in (name or "").casefold() if ch.isalnum())
        if not compact or compact in {"상품", "보험", "신상품", "해당상품", "이번상품"}:
            return True
        return compact in {"".join(ch for ch in item.casefold() if ch.isalnum()) for item in WEAK_CANONICAL_NAMES} or is_generic_product_family_signature(compact)

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
    def _enabled() -> bool:
        return os.getenv("PRODUCT_LLM_CONSOLIDATION_ENABLED", "false").lower() in {"1", "true", "yes", "y"}

    @staticmethod
    def _write_plan_csv(rows: list[dict[str, Any]], path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = [
            "block_id",
            "candidate_ids",
            "candidate_names",
            "canonical_id",
            "canonical_name",
            "merge_ids",
            "confidence",
            "reason",
            "validator_status",
            "action",
            "review_reason",
        ]
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                output = dict(row)
                for key in ("candidate_ids", "candidate_names", "merge_ids"):
                    output[key] = json.dumps(output.get(key) or [], ensure_ascii=False)
                writer.writerow({field: output.get(field, "") for field in fieldnames})
