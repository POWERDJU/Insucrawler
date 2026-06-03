from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import FactExclusiveUseRight, FactLLMRun
from app.llm.base import LLMProvider, LLMResponse
from app.llm.router import LLMRouter
from app.services.exclusive_right_consolidation_service import (
    ExclusiveRightBlock,
    ExclusiveRightBlockingService,
    ExclusiveRightConsolidationService,
)
from app.services.exclusive_right_local_context import is_generic_or_weak_subject
from app.normalizers.exclusive_right_subject_normalizer import build_exclusive_subject_tokens, is_allowed_canonical_exclusive_subject
from app.services.llm_cache_service import LLMCacheService
from app.services.llm_cost_service import LLMCostService
from app.utils.dates import utcnow
from app.utils.hashing import sha256_text
from app.utils.text import normalize_search_key


TASK_TYPE = "exclusive_right_list_consolidation"
PROMPT_VERSION = "exclusive-right-list-consolidation-v1"
SCHEMA_VERSION = "merge-plan-v1"
DEFAULT_PLAN_PATH = Path("data/exports/exclusive_right_llm_merge_plan.csv")


class ExclusiveRightLLMConsolidationService:
    """Optional block-level LLM merge-plan reviewer for exclusive-use-right events."""

    def __init__(
        self,
        *,
        blocking_service: ExclusiveRightBlockingService | None = None,
        router: LLMRouter | None = None,
        providers: dict[str, LLMProvider] | None = None,
    ) -> None:
        self.blocking_service = blocking_service or ExclusiveRightBlockingService()
        self.consolidation_service = ExclusiveRightConsolidationService(self.blocking_service)
        self.router = router or LLMRouter(providers=providers)
        self.cache_service = LLMCacheService()
        self.cost_service = LLMCostService()

    def build_exclusive_merge_blocks(
        self,
        db: Session,
        target: str = "all",
        limit: int | None = None,
    ) -> list[ExclusiveRightBlock]:
        blocks = self.blocking_service.build_blocks(db)
        if limit and limit > 0:
            allowed_ids = {
                item.exclusive_right_id
                for item in db.query(FactExclusiveUseRight)
                .filter(FactExclusiveUseRight.event_status != "merged")
                .order_by(FactExclusiveUseRight.exclusive_right_id.desc())
                .limit(limit)
                .all()
            }
            blocks = [
                ExclusiveRightBlock([item for item in block.candidates if item.exclusive_right_id in allowed_ids], block.reason)
                for block in blocks
            ]
            blocks = [block for block in blocks if len(block.candidates) > 1]
        return blocks

    def build_compact_exclusive_block_payload(self, block: ExclusiveRightBlock) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        for item in block.candidates[: int(os.getenv("LLM_CONSOLIDATION_MAX_BLOCK_SIZE", "50"))]:
            rows.append(
                {
                    "exclusive_right_id": item.exclusive_right_id,
                    "company_id": item.company_id,
                    "company_name": item.company_name_normalized,
                    "subject_name": item.subject_name,
                    "aliases": self._json_load(item.alias_names_json)[:10],
                    "exclusivity_months": item.exclusivity_months,
                    "acquired_year_month": item.acquired_year_month,
                    "feature_summary": item.feature_summary,
                    "evidence_text": item.evidence_text,
                    "article_title": item.primary_article_title,
                    "article_url": item.primary_article_url,
                    "status": item.event_status,
                }
            )
        return {
            "task": "exclusive_right_block_consolidation",
            "rules": {
                "same_company_only": True,
                "same_period_only": True,
                "reject_weak_subject_canonical": True,
                "evidence_required": True,
            },
            "block_reason": block.reason,
            "candidates": rows,
        }

    def run_llm_exclusive_block_judge(self, db: Session, block: ExclusiveRightBlock) -> tuple[dict[str, Any], FactLLMRun]:
        payload = self.build_compact_exclusive_block_payload(block)
        prompt = self._exclusive_prompt(payload)
        return self._run_llm_with_cache(db, prompt, TASK_TYPE)

    def validate_llm_exclusive_merge_plan(self, db: Session, block: ExclusiveRightBlock, plan: dict[str, Any]) -> list[dict[str, Any]]:
        block_ids = {item.exclusive_right_id for item in block.candidates}
        items = {item.exclusive_right_id: item for item in block.candidates}
        rows: list[dict[str, Any]] = []
        for group in plan.get("merge_groups") or []:
            canonical_id = self._int_or_none(group.get("canonical_id"))
            merge_ids = [item for item in (self._int_or_none(value) for value in group.get("merge_ids") or []) if item]
            confidence = float(group.get("confidence") or 0)
            canonical_name = str(group.get("canonical_subject_name") or group.get("canonical_name") or "")
            reasons: list[str] = []
            if not canonical_id or canonical_id not in block_ids:
                reasons.append("canonical_id is outside block")
            if any(item not in block_ids for item in merge_ids):
                reasons.append("merge_ids contain ids outside block")
            if canonical_id in merge_ids:
                merge_ids = [item for item in merge_ids if item != canonical_id]
            if confidence < 0.85:
                reasons.append("confidence below 0.85")
            candidates = [items[item] for item in [canonical_id, *merge_ids] if item in items]
            company_ids = {item.company_id for item in candidates if item.company_id is not None}
            months = {item.exclusivity_months for item in candidates if item.exclusivity_months is not None}
            if len(company_ids) > 1:
                reasons.append("known company differs")
            if len(months) > 1:
                reasons.append("exclusivity period differs")
            if self._month_conflict(candidates):
                reasons.append("acquired month too far")
            if self._is_weak_subject(canonical_name):
                reasons.append("weak canonical subject")
            if not self._subject_supported_by_evidence(canonical_name, candidates):
                reasons.append("canonical subject not supported by evidence or aliases")
            status = "valid" if not reasons and merge_ids else "review"
            rows.append(
                {
                    "block_id": block.reason,
                    "candidate_ids": sorted(block_ids),
                    "candidate_names": [item.subject_name for item in block.candidates],
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
        for item in plan.get("reject_items") or []:
            reject_id = self._int_or_none(item.get("id"))
            reasons = []
            if not reject_id or reject_id not in block_ids:
                reasons.append("reject id outside block")
            rows.append(
                {
                    "block_id": block.reason,
                    "candidate_ids": sorted(block_ids),
                    "candidate_names": [candidate.subject_name for candidate in block.candidates],
                    "canonical_id": reject_id,
                    "canonical_name": "",
                    "merge_ids": [],
                    "confidence": float(item.get("confidence") or 0.9),
                    "reason": item.get("reason") or "",
                    "validator_status": "valid_reject" if not reasons else "review",
                    "action": "reject" if not reasons else "review",
                    "review_reason": "; ".join(reasons),
                }
            )
        for item in plan.get("review_items") or []:
            ids = [value for value in (self._int_or_none(value) for value in item.get("ids") or []) if value]
            rows.append(
                {
                    "block_id": block.reason,
                    "candidate_ids": sorted(block_ids),
                    "candidate_names": [candidate.subject_name for candidate in block.candidates],
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
        return rows

    def apply_exclusive_merge_plan(self, db: Session, rows: list[dict[str, Any]], dry_run: bool = True) -> dict[str, int]:
        applied = 0
        rejected = 0
        review = 0
        if dry_run:
            return {
                "applied": 0,
                "rejected": 0,
                "review": sum(1 for row in rows if row.get("action") not in {"auto_apply", "reject"}),
            }
        for row in rows:
            if row.get("action") == "reject":
                item = db.get(FactExclusiveUseRight, row.get("canonical_id"))
                if item:
                    item.event_status = "rejected"
                    item.needs_review = True
                    rejected += 1
                continue
            if row.get("action") != "auto_apply":
                review += 1
                continue
            canonical = db.get(FactExclusiveUseRight, row.get("canonical_id"))
            if not canonical:
                review += 1
                continue
            if row.get("canonical_name") and row["canonical_name"] != canonical.subject_name:
                aliases = set(self._json_load(canonical.alias_names_json))
                aliases.add(canonical.subject_name)
                canonical.subject_name = row["canonical_name"]
                aliases.add(row["canonical_name"])
                canonical.alias_names_json = json.dumps(sorted(aliases), ensure_ascii=False)
            for duplicate_id in row.get("merge_ids") or []:
                duplicate = db.get(FactExclusiveUseRight, duplicate_id)
                if not duplicate or duplicate.exclusive_right_id == canonical.exclusive_right_id or duplicate.event_status == "merged":
                    continue
                self.consolidation_service._merge(db, canonical, duplicate, decision_source="ai_list_level_block_judge")
                applied += 1
        db.flush()
        return {"applied": applied, "rejected": rejected, "review": review}

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
                "reject_count": 0,
                "estimated_cost_usd": 0.0,
                "plan_file": str(plan_file),
                "status": "disabled",
            }
        blocks = self.build_exclusive_merge_blocks(db, target=target, limit=limit)[:max_blocks]
        all_rows: list[dict[str, Any]] = []
        llm_call_count = 0
        estimated_cost = 0.0
        max_calls = int(os.getenv("LLM_CONSOLIDATION_MAX_CALLS_PER_JOB", "20"))
        max_cost = float(os.getenv("LLM_CONSOLIDATION_MAX_COST_USD_PER_JOB", "2.0"))
        for block in blocks:
            if llm_call_count >= max_calls or estimated_cost >= max_cost:
                break
            plan, run = self.run_llm_exclusive_block_judge(db, block)
            llm_call_count += 0 if run.cached_yn else 1
            estimated_cost += float(run.estimated_cost_usd or 0)
            all_rows.extend(self.validate_llm_exclusive_merge_plan(db, block, plan))
        self._write_plan_csv(all_rows, Path(plan_file))
        apply_summary = self.apply_exclusive_merge_plan(db, all_rows, dry_run=(mode == "dry_run"))
        db.commit()
        return {
            "job_id": None,
            "block_count": len(blocks),
            "llm_call_count": llm_call_count,
            "auto_apply_count": apply_summary["applied"] if mode == "apply" else sum(1 for row in all_rows if row.get("action") == "auto_apply"),
            "review_count": sum(1 for row in all_rows if row.get("action") == "review"),
            "reject_count": apply_summary["rejected"] if mode == "apply" else sum(1 for row in all_rows if row.get("action") == "reject"),
            "estimated_cost_usd": round(estimated_cost, 8),
            "plan_file": str(plan_file),
        }

    def _run_llm_with_cache(self, db: Session, prompt: str, task_type: str) -> tuple[dict[str, Any], FactLLMRun]:
        provider_name = os.getenv("LLM_CONSOLIDATION_PROVIDER", "gemini")
        model_name = os.getenv("LLM_CONSOLIDATION_MODEL", "gemini-2.5-flash")
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
        run = self._record_run(db, prompt, response.output_json, response.provider, response.model_name, task_type, cached_yn=False, response=response)
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
    def _exclusive_prompt(payload: dict[str, Any]) -> str:
        return (
            "You are judging whether exclusive-use-right event rows are the same event. "
            "Return JSON only with merge_groups, reject_items, and review_items. "
            "Merge only same insurer, same/near acquired month, and same exclusivity period. "
            "Never use weak Korean references such as 해당 상품, 이번 상품, 신상품 as canonical_subject_name. "
            "Reject obvious false-attribution rows when the evidence belongs to another subject. "
            "Use only the compact candidate rows below; do not invent facts.\n\n"
            + json.dumps(payload, ensure_ascii=False)
        )

    @staticmethod
    def _month_conflict(candidates: list[FactExclusiveUseRight]) -> bool:
        months = [item.acquired_year_month for item in candidates if item.acquired_year_month]
        if len(set(months)) <= 1:
            return False
        parsed = []
        for month in months:
            try:
                year, value = [int(part) for part in month.split("-", 1)]
                parsed.append(year * 12 + value)
            except ValueError:
                return True
        return max(parsed) - min(parsed) > 1

    @staticmethod
    def _is_weak_subject(name: str | None) -> bool:
        return is_generic_or_weak_subject(name) or not is_allowed_canonical_exclusive_subject(name)

    def _subject_supported_by_evidence(self, subject_name: str, candidates: list[FactExclusiveUseRight]) -> bool:
        subject_key = normalize_search_key(subject_name)
        if not subject_key:
            return False
        tokens = {token for token in build_exclusive_subject_tokens(subject_name) if len(token) >= 2}
        for item in candidates:
            evidence = " ".join(
                part
                for part in [
                    item.subject_name,
                    item.feature_summary,
                    item.evidence_summary,
                    item.evidence_text,
                    item.primary_article_title,
                    " ".join(self._json_load(item.alias_names_json)),
                ]
                if part
            )
            evidence_key = normalize_search_key(evidence)
            if subject_key and subject_key in evidence_key:
                return True
            evidence_tokens = build_exclusive_subject_tokens(evidence)
            if tokens and len(tokens & evidence_tokens) >= min(2, len(tokens)):
                return True
        return False

    @staticmethod
    def _tokens(text: str | None) -> set[str]:
        import re

        return {normalize_search_key(match) for match in re.findall(r"[가-힣A-Za-z0-9]{2,}", text or "")}

    @staticmethod
    def _int_or_none(value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _json_load(value: str | None) -> list[str]:
        if not value:
            return []
        try:
            payload = json.loads(value)
            return [str(item) for item in payload if item]
        except json.JSONDecodeError:
            return []

    @staticmethod
    def _enabled() -> bool:
        return os.getenv("EXCLUSIVE_RIGHT_LLM_CONSOLIDATION_ENABLED", "false").lower() in {"1", "true", "yes", "y"}

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
