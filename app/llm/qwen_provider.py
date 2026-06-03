from __future__ import annotations

import json
import os
import time
from typing import Any

import httpx

from app.llm.base import LLMProvider, LLMResponse
from app.llm.prompts import ADJUDICATOR_PROMPT, EXTRACTOR_PROMPT, VERIFIER_PROMPT


class QwenProvider(LLMProvider):
    provider_name = "qwen"

    def __init__(self, model_name: str | None = None, api_key: str | None = None, base_url: str | None = None) -> None:
        self.model_name = model_name or os.getenv("QWEN_EXTRACT_MODEL") or "qwen-plus"
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        self.base_url = (base_url or os.getenv("QWEN_BASE_URL") or "https://dashscope-intl.aliyuncs.com/compatible-mode/v1").rstrip("/")

    def _ensure_configured(self) -> None:
        if not self.api_key:
            raise RuntimeError("DASHSCOPE_API_KEY is required")

    @staticmethod
    def _json_from_text(text: str) -> dict[str, Any]:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            cleaned = cleaned.removeprefix("json").strip()
        return json.loads(cleaned)

    def _chat_json(self, prompt: str, task_type: str) -> LLMResponse:
        self._ensure_configured()
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": "JSON only."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        started = time.perf_counter()
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=payload,
            timeout=60,
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:500]
            raise RuntimeError(f"Qwen API request failed: status={exc.response.status_code}, body={body}") from exc
        data = response.json()
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage") or {}
        return LLMResponse(
            provider=self.provider_name,
            model_name=self.model_name,
            task_type=task_type,
            output_json=self._json_from_text(text),
            raw_text=text,
            token_input=usage.get("prompt_tokens"),
            token_output=usage.get("completion_tokens"),
            latency_ms=latency_ms,
        )

    def extract_product_info(self, input_text: str, schema: dict | None, prompt_version: str) -> LLMResponse:
        return self._chat_json(f"{EXTRACTOR_PROMPT}\n\n원문:\n{input_text}", "extract")

    def verify_extraction(self, input_text: str, extracted_json: dict, schema: dict | None, prompt_version: str) -> LLMResponse:
        prompt = f"{VERIFIER_PROMPT}\n\n원문:\n{input_text}\n\n추출 JSON:\n{json.dumps(extracted_json, ensure_ascii=False)}"
        return self._chat_json(prompt, "verify")

    def adjudicate_conflict(self, input_text: str, extraction_a: dict, extraction_b: dict, verification_result: dict) -> LLMResponse:
        prompt = (
            f"{ADJUDICATOR_PROMPT}\n\n원문:\n{input_text}\n\nA:\n{json.dumps(extraction_a, ensure_ascii=False)}"
            f"\n\nB:\n{json.dumps(extraction_b, ensure_ascii=False)}\n\n검증:\n{json.dumps(verification_result, ensure_ascii=False)}"
        )
        return self._chat_json(prompt, "adjudicate")
