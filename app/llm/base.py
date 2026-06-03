from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class LLMResponse:
    provider: str
    model_name: str
    task_type: str
    output_json: dict[str, Any]
    raw_text: str
    token_input: int | None = None
    token_output: int | None = None
    latency_ms: int | None = None
    cost_estimate: float | None = None


class LLMProvider(ABC):
    provider_name: str

    @abstractmethod
    def extract_product_info(self, input_text: str, schema: dict | None, prompt_version: str) -> LLMResponse:
        raise NotImplementedError

    @abstractmethod
    def verify_extraction(self, input_text: str, extracted_json: dict, schema: dict | None, prompt_version: str) -> LLMResponse:
        raise NotImplementedError

    @abstractmethod
    def adjudicate_conflict(self, input_text: str, extraction_a: dict, extraction_b: dict, verification_result: dict) -> LLMResponse:
        raise NotImplementedError
