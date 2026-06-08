from __future__ import annotations

import os
from typing import Any

from app.services.coverage_dedupe_service import build_coverage_identity_key


class MajorCoverageLLMDedupeService:
    """Optional compact-list LLM dedupe guard.

    The service intentionally does not call a provider by default. It only
    validates externally supplied merge plans so render/export paths never make
    surprise LLM calls.
    """

    task_type = "major_coverage_list_dedupe"

    def enabled(self) -> bool:
        return os.getenv("MAJOR_COVERAGE_LLM_DEDUPE_ENABLED", "false").lower() == "true"

    def compact_input(self, product_id: int, product_name: str | None, coverages: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "task": "major_coverage_dedupe",
            "product_id": product_id,
            "product_name": product_name,
            "coverages": [
                {
                    "coverage_id": item.get("coverage_id"),
                    "coverage_name": item.get("coverage_name_normalized") or item.get("coverage_name_raw"),
                    "risk_area": item.get("risk_area"),
                    "benefit_type": item.get("benefit_type"),
                    "max_amount_krw": item.get("max_amount_krw"),
                    "payment_condition": item.get("condition_text") or item.get("limit_text"),
                    "summary": item.get("coverage_summary"),
                }
                for item in coverages
            ],
        }

    def validate_merge_plan(self, coverages: list[dict[str, Any]], plan: dict[str, Any]) -> dict[str, Any]:
        by_id = {int(item["coverage_id"]): item for item in coverages if item.get("coverage_id") is not None}
        accepted: list[dict[str, Any]] = []
        review_items: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        for group in plan.get("merge_groups") or []:
            canonical_id = group.get("canonical_coverage_id")
            merge_ids = group.get("merge_ids") or []
            confidence = float(group.get("confidence") or 0)
            if canonical_id not in by_id or any(item not in by_id for item in merge_ids):
                rejected.append({**group, "reason": "unknown coverage id"})
                continue
            if confidence < 0.85:
                review_items.append({**group, "reason": "low confidence"})
                continue
            canonical_key = build_coverage_identity_key(by_id[int(canonical_id)])
            incompatible = [
                merge_id
                for merge_id in merge_ids
                if build_coverage_identity_key(by_id[int(merge_id)]) != canonical_key
            ]
            if incompatible:
                review_items.append({**group, "reason": "rule identity conflict", "conflict_ids": incompatible})
                continue
            accepted.append(group)
        return {"accepted_merge_groups": accepted, "review_items": review_items, "rejected_merge_groups": rejected}
