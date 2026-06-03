from __future__ import annotations

from app.llm.prompts import EXTRACTOR_PROMPT, VERIFIER_PROMPT


def build_extractor_prompt(input_text: str) -> str:
    return f"{EXTRACTOR_PROMPT}\n\n원문:\n{input_text}"


def build_verifier_prompt(input_text: str, extracted_json: str) -> str:
    return f"{VERIFIER_PROMPT}\n\n원문:\n{input_text}\n\n추출 JSON:\n{extracted_json}"
