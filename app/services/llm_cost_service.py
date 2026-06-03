from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.orm import Session

from app.db.models import FactLLMCostLog, FactLLMRun


class LLMCostService:
    def __init__(self, pricing_path: str | Path = "config/llm_pricing.yaml") -> None:
        self.pricing_path = Path(pricing_path)
        self.pricing = self._load_pricing()

    def _load_pricing(self) -> list[dict[str, Any]]:
        if not self.pricing_path.exists():
            return []
        with self.pricing_path.open("r", encoding="utf-8") as f:
            return (yaml.safe_load(f) or {}).get("models") or []

    def estimate(
        self,
        *,
        provider: str,
        model_name: str,
        input_tokens: int | None,
        output_tokens: int | None,
        cached_tokens: int = 0,
        batch_yn: bool = False,
    ) -> float:
        estimated, _ = self.estimate_with_quality(
            provider=provider,
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            batch_yn=batch_yn,
        )
        return estimated

    def estimate_with_quality(
        self,
        *,
        provider: str,
        model_name: str,
        input_tokens: int | None,
        output_tokens: int | None,
        cached_tokens: int = 0,
        batch_yn: bool = False,
    ) -> tuple[float, str]:
        input_tokens = int(input_tokens or 0)
        output_tokens = int(output_tokens or 0)
        price = self._price(provider, model_name)
        if not price:
            return 0.0, "missing_price"
        input_cost = input_tokens / 1_000_000 * float(price.get("input_cost_per_1m_tokens", 0))
        output_cost = output_tokens / 1_000_000 * float(price.get("output_cost_per_1m_tokens", 0))
        cached_cost = cached_tokens / 1_000_000 * float(price.get("cached_input_cost_per_1m_tokens", 0))
        total = input_cost + output_cost + cached_cost
        if batch_yn:
            total *= float(price.get("batch_discount_rate", 1.0))
        return round(total, 8), "priced"

    def record_run(
        self,
        db: Session,
        run: FactLLMRun,
        *,
        input_text: str | None = None,
        cached_tokens: int = 0,
        grounded_yn: bool = False,
    ) -> FactLLMCostLog:
        input_tokens, input_quality, input_chars = self._resolve_input_tokens(run, input_text)
        output_tokens, output_quality, output_chars = self._resolve_output_tokens(run)
        estimate_quality = self._combine_token_quality(input_quality, output_quality)
        estimated = run.estimated_cost_usd
        if estimated is None:
            estimated, price_quality = self.estimate_with_quality(
                provider=run.provider,
                model_name=run.model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cached_tokens=cached_tokens,
                batch_yn=bool(run.batch_yn),
            )
            if price_quality == "missing_price":
                estimate_quality = "missing_price"
            run.estimated_cost_usd = estimated
            run.cost_estimate = estimated
        elif not self._price(run.provider, run.model_name):
            estimate_quality = "missing_price"
        run.input_chars = run.input_chars or input_chars
        run.output_chars = run.output_chars or output_chars
        run.estimate_quality = estimate_quality
        run.grounded_yn = grounded_yn
        item = FactLLMCostLog(
            llm_run_id=run.llm_run_id,
            provider=run.provider,
            model_name=run.model_name,
            task_type=run.task_type,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            estimated_cost_usd=float(estimated or 0),
            batch_yn=bool(run.batch_yn),
            grounded_yn=grounded_yn,
            estimate_quality=estimate_quality,
        )
        db.add(item)
        db.flush()
        return item

    def summary(self, db: Session, date_from: str | None = None, date_to: str | None = None) -> dict[str, Any]:
        query = db.query(FactLLMCostLog)
        if date_from:
            query = query.filter(FactLLMCostLog.created_at >= date_from)
        if date_to:
            query = query.filter(FactLLMCostLog.created_at <= date_to)
        rows = query.all()
        total = sum(float(row.estimated_cost_usd or 0) for row in rows)
        by_model_map: dict[tuple[str, str], dict[str, Any]] = {}
        by_task_map: dict[str, dict[str, Any]] = {}
        for row in rows:
            model_key = (row.provider, row.model_name)
            by_model_map.setdefault(model_key, {"estimated_cost_usd": 0.0, "count": 0})
            by_model_map[model_key]["estimated_cost_usd"] += float(row.estimated_cost_usd or 0)
            by_model_map[model_key]["count"] += 1
            task_key = row.task_type
            by_task_map.setdefault(task_key, {"estimated_cost_usd": 0.0, "count": 0})
            by_task_map[task_key]["estimated_cost_usd"] += float(row.estimated_cost_usd or 0)
            by_task_map[task_key]["count"] += 1
        run_query = db.query(FactLLMRun)
        if date_from:
            run_query = run_query.filter(FactLLMRun.created_at >= date_from)
        if date_to:
            run_query = run_query.filter(FactLLMRun.created_at <= date_to)
        runs = run_query.all()
        run_count = len(runs)
        cache_hits = sum(1 for row in runs if row.cached_yn)
        batch_count = sum(1 for row in rows if row.batch_yn)
        return {
            "date_from": date_from,
            "date_to": date_to,
            "total_estimated_cost_usd": round(total, 8),
            "by_model": [
                {"provider": p, "model_name": m, "estimated_cost_usd": round(v["estimated_cost_usd"], 8), "count": v["count"]}
                for (p, m), v in sorted(by_model_map.items())
            ],
            "by_task_type": [
                {"task_type": t, "estimated_cost_usd": round(v["estimated_cost_usd"], 8), "count": v["count"]}
                for t, v in sorted(by_task_map.items())
            ],
            "cache_hit_rate": (cache_hits / run_count) if run_count else 0,
            "batch_request_count": batch_count,
            "input_tokens_total": sum(int(row.input_tokens or 0) for row in rows),
            "output_tokens_total": sum(int(row.output_tokens or 0) for row in rows),
            "cached_tokens_total": sum(int(row.cached_tokens or 0) for row in rows),
            "run_count": run_count,
            "total_run_count": run_count,
            "extract_run_count": sum(1 for row in runs if row.task_type == "extract"),
            "verify_run_count": sum(1 for row in runs if row.task_type == "verify"),
            "adjudicate_run_count": sum(1 for row in runs if row.task_type == "adjudicate"),
            "product_consolidation_run_count": sum(1 for row in runs if row.task_type == "product_consolidation"),
            "cached_run_count": cache_hits,
            "batch_run_count": sum(1 for row in runs if row.batch_yn),
            "grounded_run_count": sum(1 for row in runs if row.grounded_yn),
            "estimate_quality": self._summary_quality([getattr(row, "estimate_quality", None) for row in rows]),
        }

    def _price(self, provider: str, model_name: str) -> dict[str, Any]:
        for item in self.pricing:
            if item.get("provider") == provider and item.get("model_name") == model_name:
                return item
        for item in self.pricing:
            if item.get("provider") == provider and item.get("model_name") == "default":
                return item
        return {}

    @staticmethod
    def rough_token_count(text: str) -> int:
        return LLMCostService.rough_token_count_for_korean(text)

    @staticmethod
    def rough_token_count_for_korean(text: str) -> int:
        chars_per_token = float(os.getenv("KOREAN_TOKEN_CHARS_PER_TOKEN", "2.5") or "2.5")
        return max(1, math.ceil(len(text or "") / chars_per_token))

    def _resolve_input_tokens(self, run: FactLLMRun, input_text: str | None) -> tuple[int, str, int | None]:
        if run.token_input is not None:
            return int(run.token_input), "actual_tokens", run.input_chars
        if input_text is not None:
            return self.rough_token_count_for_korean(input_text), "rough", len(input_text)
        if run.input_chars:
            chars_per_token = float(os.getenv("KOREAN_TOKEN_CHARS_PER_TOKEN", "2.5") or "2.5")
            return max(1, math.ceil(int(run.input_chars) / chars_per_token)), "rough", int(run.input_chars)
        return 0, "rough", run.input_chars

    def _resolve_output_tokens(self, run: FactLLMRun) -> tuple[int, str, int | None]:
        if run.token_output is not None:
            return int(run.token_output), "actual_tokens", run.output_chars
        output_text = run.output_json or ""
        return self.rough_token_count_for_korean(output_text) if output_text else 0, "rough", len(output_text) if output_text else run.output_chars

    @staticmethod
    def _combine_token_quality(input_quality: str, output_quality: str) -> str:
        if input_quality == "actual_tokens" and output_quality == "actual_tokens":
            return "actual_tokens"
        if input_quality == "actual_tokens" or output_quality == "actual_tokens":
            return "mixed"
        return "rough"

    @staticmethod
    def _summary_quality(qualities: list[str | None]) -> str:
        cleaned = [q for q in qualities if q]
        if not cleaned:
            return "rough"
        if "missing_price" in cleaned:
            return "missing_price"
        if all(q == "actual_tokens" for q in cleaned):
            return "actual_tokens"
        if any(q in {"actual_tokens", "mixed"} for q in cleaned):
            return "mixed"
        return "rough"
