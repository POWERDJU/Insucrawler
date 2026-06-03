from __future__ import annotations

import json
import os
import time
from typing import Any

import httpx

from app.llm.base import LLMProvider, LLMResponse
from app.llm.prompts import ADJUDICATOR_PROMPT, EXTRACTOR_PROMPT, VERIFIER_PROMPT


class GeminiProvider(LLMProvider):
    provider_name = "gemini"

    def __init__(self, model_name: str | None = None, api_key: str | None = None) -> None:
        self.model_name = model_name or os.getenv("GEMINI_EXTRACT_MODEL") or "gemini-1.5-pro"
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")

    def _ensure_configured(self) -> None:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is required")

    @staticmethod
    def _json_from_text(text: str) -> dict[str, Any]:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            cleaned = cleaned.removeprefix("json").strip()
        return json.loads(cleaned)

    @staticmethod
    def _can_send_response_schema(schema: dict | None) -> bool:
        """Gemini's response_schema supports a subset and rejects Pydantic $defs/$ref graphs."""
        if not schema:
            return False
        encoded = json.dumps(schema)
        return "$defs" not in encoded and "$ref" not in encoded

    def _generate_json(self, prompt: str, task_type: str, schema: dict | None = None) -> LLMResponse:
        self._ensure_configured()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent"
        payload: dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.0,
            },
        }
        if self._can_send_response_schema(schema):
            payload["generationConfig"]["response_schema"] = schema
        started = time.perf_counter()
        response = httpx.post(url, params={"key": self.api_key}, json=payload, timeout=60)
        latency_ms = int((time.perf_counter() - started) * 1000)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:500]
            raise RuntimeError(f"Gemini API request failed: status={exc.response.status_code}, body={body}") from exc
        data = response.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return LLMResponse(
            provider=self.provider_name,
            model_name=self.model_name,
            task_type=task_type,
            output_json=self._json_from_text(text),
            raw_text=text,
            latency_ms=latency_ms,
        )

    def extract_product_info(self, input_text: str, schema: dict | None, prompt_version: str) -> LLMResponse:
        return self._generate_json(f"{EXTRACTOR_PROMPT}\n\n원문:\n{input_text}", "extract", schema)

    def verify_extraction(self, input_text: str, extracted_json: dict, schema: dict | None, prompt_version: str) -> LLMResponse:
        prompt = f"{VERIFIER_PROMPT}\n\n원문:\n{input_text}\n\n추출 JSON:\n{json.dumps(extracted_json, ensure_ascii=False)}"
        return self._generate_json(prompt, "verify", schema)

    def adjudicate_conflict(self, input_text: str, extraction_a: dict, extraction_b: dict, verification_result: dict) -> LLMResponse:
        prompt = (
            f"{ADJUDICATOR_PROMPT}\n\n원문:\n{input_text}\n\nA:\n{json.dumps(extraction_a, ensure_ascii=False)}"
            f"\n\nB:\n{json.dumps(extraction_b, ensure_ascii=False)}\n\n검증:\n{json.dumps(verification_result, ensure_ascii=False)}"
        )
        return self._generate_json(prompt, "adjudicate", None)
