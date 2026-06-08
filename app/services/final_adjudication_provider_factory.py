from __future__ import annotations

import os
from typing import Any

from app.llm.gemini_provider import GeminiProvider
from app.llm.qwen_provider import QwenProvider


TRUE_VALUES = {"1", "true", "yes", "y", "on"}


def _env_value(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    if value is None:
        return None
    return value.strip().strip('"').strip("'")


def final_adjudication_llm_enabled() -> bool:
    return (_env_value("ENABLE_FINAL_ADJUDICATION_LLM") or "").lower() in TRUE_VALUES


def build_final_adjudication_provider() -> Any | None:
    """Return an opt-in live LLM provider for compact final adjudication."""

    if not final_adjudication_llm_enabled():
        return None
    provider_name = (_env_value("FINAL_ADJUDICATION_PROVIDER", "qwen") or "qwen").lower()
    model_name = _env_value("FINAL_ADJUDICATION_MODEL")
    if provider_name == "qwen":
        return QwenProvider(model_name=model_name or _env_value("QWEN_FINAL_ADJUDICATION_MODEL"))
    if provider_name == "gemini":
        return GeminiProvider(model_name=model_name or _env_value("GEMINI_FINAL_ADJUDICATION_MODEL"))
    raise ValueError(f"Unsupported FINAL_ADJUDICATION_PROVIDER: {provider_name}")
