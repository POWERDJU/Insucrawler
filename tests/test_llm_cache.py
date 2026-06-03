from app.db.models import FactLLMResponseCache
from app.services.llm_cache_service import LLMCacheService


def test_llm_cache_reuses_same_input_hash(db_session):
    service = LLMCacheService()
    kwargs = {
        "input_text": "삼성화재 암보험 출시",
        "prompt_version": "p1",
        "schema_version": "s1",
        "provider": "gemini",
        "model_name": "flash",
        "task_type": "extract",
    }
    service.put(db_session, **kwargs, output_json={"products": []})
    db_session.commit()

    cached = service.get(db_session, **kwargs)

    assert cached == {"products": []}
    row = db_session.query(FactLLMResponseCache).one()
    assert row.hit_count == 1


def test_llm_cache_misses_when_prompt_version_changes(db_session):
    service = LLMCacheService()
    service.put(
        db_session,
        input_text="same",
        prompt_version="p1",
        schema_version="s1",
        provider="gemini",
        model_name="flash",
        task_type="extract",
        output_json={"a": 1},
    )
    db_session.commit()

    assert service.get(
        db_session,
        input_text="same",
        prompt_version="p2",
        schema_version="s1",
        provider="gemini",
        model_name="flash",
        task_type="extract",
    ) is None
