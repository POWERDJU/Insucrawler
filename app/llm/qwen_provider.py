from __future__ import annotations

import json
import os
import time
from json import JSONDecodeError
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
        self.timeout_seconds = float(os.getenv("QWEN_HTTP_TIMEOUT_SECONDS") or "180")
        self.max_retries = max(1, int(os.getenv("QWEN_HTTP_MAX_RETRIES") or "3"))

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
        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            started = time.perf_counter()
            try:
                response = httpx.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=payload,
                    timeout=self.timeout_seconds,
                )
                latency_ms = int((time.perf_counter() - started) * 1000)
                response.raise_for_status()
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
            except httpx.HTTPStatusError as exc:
                body = exc.response.text[:500]
                retryable = exc.response.status_code in {408, 409, 425, 429, 500, 502, 503, 504}
                last_error = RuntimeError(f"Qwen API request failed: status={exc.response.status_code}, body={body}")
                if not retryable or attempt >= self.max_retries:
                    raise last_error from exc
            except (httpx.TimeoutException, JSONDecodeError, KeyError, IndexError, TypeError, ValueError) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    raise RuntimeError(f"Qwen API response failed after {attempt} attempt(s): {exc}") from exc
            time.sleep(min(2 ** (attempt - 1), 8))
        raise RuntimeError(f"Qwen API response failed: {last_error}")

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

    def adjudicate_product(self, payload: dict[str, Any]) -> dict[str, Any]:
        prompt = (
            "You are the final compact-context adjudicator for a Korean insurance product extraction.\n"
            "Use only the supplied payload. Return JSON only with these fields:\n"
            "decision, canonical_product_name, company_name, insurance_type, product_type_code, "
            "release_year_month, release_year_month_basis, partner_company_name, partner_role, "
            "article_suitability, correction_summary, reason, evidence_quote, confidence.\n"
            "Allowed decisions: accept, reject, review, reassign_company, alias_only, non_insurance, ineligible_article.\n"
            "Judge whether the product name, release year-month, company attribution, product-combination/partner structure, "
            "and article content are mutually supported. Correct fields when the local article context supports a clear correction. "
            "If the article is genuinely about a specific insurance product but current fields are wrong, prefer decision=accept "
            "with corrected fields when evidence is clear, or decision=review when correction is uncertain. Do not reject a "
            "genuine insurance product solely because the current name, company, release month, or product type is wrong. "
            "Use release_year_month format YYYY-MM and release_year_month_basis such as explicit_in_article or unknown. "
            "Use reject/non_insurance/ineligible_article only when the row should be discarded: non-insurance product/service, "
            "ineligible multi-company or marketing article, unrecoverable sentence fragment, or no supported insurance product. "
            "Reject when the article does not mention or otherwise support the current product at all; do not mark that as review. "
            "Mark review when article is eligible and product-related but evidence is insufficient for a safe correction. "
            "If you reassign a company or correct a field, quote the local evidence.\n\n"
            f"Payload:\n{json.dumps(payload, ensure_ascii=False)}"
        )
        return self._chat_json(prompt, "product_final_adjudication").output_json

    def adjudicate_exclusive_right(self, payload: dict[str, Any]) -> dict[str, Any]:
        prompt = (
            "You are the final compact-context adjudicator for a Korean insurance exclusive-use-right extraction.\n"
            "Use only the supplied payload. Return JSON only with these fields:\n"
            "decision, subject_name, company_name, acquired_year_month, reason, evidence_quote, confidence.\n"
            "Allowed decisions: accept, reject, review, reassign_company, ineligible_article.\n"
            "Accept only when the subject, insurer, acquired month, and evidence quote are supported by the local context. "
            "If the article is genuinely about an exclusive-use-right event but the current subject/company/month is wrong, "
            "prefer decision=accept with corrected fields when evidence is clear, or decision=review when uncertain. "
            "Use reject/ineligible_article only when the row should be discarded: ineligible article, non-exclusive-right story, "
            "unrecoverable weak/generic sentence-fragment subject, or a current subject not supported by the article at all. "
            "Mark review for weak/generic subjects, future acquired months, unsupported company attribution, or partial exclusive-right evidence.\n\n"
            f"Payload:\n{json.dumps(payload, ensure_ascii=False)}"
        )
        return self._chat_json(prompt, "exclusive_right_final_adjudication").output_json
