from app.llm.qwen_provider import QwenProvider
from app.services.final_adjudication_provider_factory import build_final_adjudication_provider


def test_final_adjudication_provider_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ENABLE_FINAL_ADJUDICATION_LLM", raising=False)
    monkeypatch.delenv("FINAL_ADJUDICATION_PROVIDER", raising=False)

    assert build_final_adjudication_provider() is None


def test_final_adjudication_provider_uses_qwen_when_enabled(monkeypatch):
    monkeypatch.setenv("ENABLE_FINAL_ADJUDICATION_LLM", "true")
    monkeypatch.setenv("FINAL_ADJUDICATION_PROVIDER", "qwen")
    monkeypatch.setenv("QWEN_FINAL_ADJUDICATION_MODEL", "qwen-plus")

    provider = build_final_adjudication_provider()

    assert isinstance(provider, QwenProvider)
    assert provider.model_name == "qwen-plus"
