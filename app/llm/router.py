from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from app.llm.base import LLMProvider, LLMResponse
from app.llm.gemini_provider import GeminiProvider
from app.llm.prompts import PROMPT_VERSION
from app.llm.qwen_provider import QwenProvider
from app.llm.schemas import extraction_json_schema, verification_json_schema


class LLMRouter:
    def __init__(self, policy_path: str | Path = "config/llm_routing_policy.yaml", providers: dict[str, LLMProvider] | None = None) -> None:
        self.policy_path = Path(policy_path)
        self.policy = self._load_policy()
        self.providers = providers or {}

    def _load_policy(self) -> dict[str, Any]:
        if not self.policy_path.exists():
            return {"default_mode": "gemini_extract_qwen_verify", "modes": {}}
        with self.policy_path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def mode(self) -> str:
        return os.getenv("LLM_PIPELINE_MODE") or self.policy.get("default_mode") or "gemini_extract_qwen_verify"

    def route_plan(self, mode: str | None = None) -> dict[str, Any]:
        selected = mode or self.mode()
        modes = self.policy.get("modes") or {}
        if selected not in modes:
            raise ValueError(f"Unsupported LLM_PIPELINE_MODE: {selected}")
        return modes[selected]

    def _provider(self, provider_name: str, model_env: str | None = None) -> LLMProvider:
        model_name = os.getenv(model_env or "") if model_env else None
        key = f"{provider_name}:{model_name or ''}"
        if key in self.providers:
            return self.providers[key]
        if provider_name in self.providers:
            return self.providers[provider_name]
        for provider_key, provider in self.providers.items():
            if provider_key.split(":", 1)[0] == provider_name:
                return provider
        if provider_name == "gemini":
            return GeminiProvider(model_name=model_name)
        if provider_name == "qwen":
            return QwenProvider(model_name=model_name)
        raise ValueError(f"Unsupported provider: {provider_name}")

    @staticmethod
    def qwen_first_requires_verification(extraction: dict[str, Any], confidence_threshold: float = 0.75) -> bool:
        products = extraction.get("products") or []
        for product in products:
            confidence = product.get("confidence") or {}
            if any(float(value or 0) < confidence_threshold for value in confidence.values()):
                return True
            if product.get("sales_metrics"):
                return True
            if any(c.get("max_amount_krw") for c in product.get("major_coverages") or []):
                return True
            if (product.get("identity") or {}).get("release_year_month"):
                return True
            classification = product.get("product_type_classification") or {}
            if classification.get("needs_human_review"):
                return True
        return False

    @staticmethod
    def field_diff(a: dict[str, Any], b: dict[str, Any]) -> list[dict[str, Any]]:
        checks: list[dict[str, Any]] = []
        products_a = a.get("products") or []
        products_b = b.get("products") or []
        max_len = max(len(products_a), len(products_b))
        for idx in range(max_len):
            pa = products_a[idx] if idx < len(products_a) else {}
            pb = products_b[idx] if idx < len(products_b) else {}
            for path in [
                ("identity", "raw_product_name"),
                ("identity", "company_name_candidate"),
                ("identity", "release_year_month"),
                ("product_type_classification", "primary_product_type"),
            ]:
                va = pa.get(path[0], {}).get(path[1]) if isinstance(pa.get(path[0]), dict) else None
                vb = pb.get(path[0], {}).get(path[1]) if isinstance(pb.get(path[0]), dict) else None
                if va != vb:
                    checks.append({"field_path": f"products[{idx}].{path[0]}.{path[1]}", "a": va, "b": vb})
        return checks

    def run_pipeline(self, input_text: str, mode: str | None = None) -> dict[str, LLMResponse | list[dict[str, Any]] | None]:
        selected = mode or self.mode()
        plan = self.route_plan(selected)
        if selected == "parallel_consensus":
            responses = []
            for extractor in plan.get("extractors", []):
                provider = self._provider(extractor["provider"], extractor.get("model_env"))
                responses.append(provider.extract_product_info(input_text, extraction_json_schema(), PROMPT_VERSION))
            diff = self.field_diff(responses[0].output_json if responses else {}, responses[1].output_json if len(responses) > 1 else {})
            return {"extractor": responses[0] if responses else None, "verifier": responses[1] if len(responses) > 1 else None, "diff": diff, "adjudicator": None}
        extractor_conf = plan.get("extractor")
        if not extractor_conf:
            raise ValueError(f"Mode {selected} has no extractor")
        extractor = self._provider(extractor_conf["provider"], extractor_conf.get("model_env"))
        extraction = extractor.extract_product_info(input_text, extraction_json_schema(), PROMPT_VERSION)
        verifier_response = None
        if selected == "qwen_first_cost_saver":
            should_verify = self.qwen_first_requires_verification(extraction.output_json)
        else:
            should_verify = bool(plan.get("verifier"))
        if should_verify and plan.get("verifier"):
            verifier_conf = plan["verifier"]
            verifier = self._provider(verifier_conf["provider"], verifier_conf.get("model_env"))
            verifier_response = verifier.verify_extraction(input_text, extraction.output_json, verification_json_schema(), PROMPT_VERSION)
        return {"extractor": extraction, "verifier": verifier_response, "diff": [], "adjudicator": None}

    def run_extraction_only(self, input_text: str, mode: str | None = None) -> dict[str, LLMResponse | list[dict[str, Any]] | None]:
        selected = mode or self.mode()
        plan = self.route_plan(selected)
        extractor_conf = (plan.get("extractors") or [None])[0] if selected == "parallel_consensus" else plan.get("extractor")
        if not extractor_conf:
            raise ValueError(f"Mode {selected} has no extractor")
        extractor = self._provider(extractor_conf["provider"], extractor_conf.get("model_env"))
        extraction = extractor.extract_product_info(input_text, extraction_json_schema(), PROMPT_VERSION)
        return {"extractor": extraction, "verifier": None, "diff": [], "adjudicator": None}
