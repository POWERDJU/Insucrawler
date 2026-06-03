from app.llm.gemini_provider import GeminiProvider


def test_gemini_response_schema_guard_rejects_pydantic_refs():
    schema = {"$defs": {"X": {"type": "object"}}, "properties": {"x": {"$ref": "#/$defs/X"}}}
    assert GeminiProvider._can_send_response_schema(schema) is False


def test_gemini_response_schema_guard_allows_simple_schema():
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}}
    assert GeminiProvider._can_send_response_schema(schema) is True
