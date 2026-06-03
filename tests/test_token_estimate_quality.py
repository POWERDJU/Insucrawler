from app.db import repository
from app.services.llm_cost_service import LLMCostService


def test_actual_token_usage_sets_actual_quality(db_session):
    run = repository.create_llm_run(
        db_session,
        task_type="extract",
        provider="gemini",
        model_name="default",
        input_hash="hash-only",
        output_json="{}",
        token_input=100,
        token_output=50,
    )

    cost = LLMCostService().record_run(db_session, run, input_text="실제 입력")

    assert cost.estimate_quality == "actual_tokens"
    assert run.estimate_quality == "actual_tokens"


def test_partial_token_usage_sets_mixed_quality(db_session):
    run = repository.create_llm_run(
        db_session,
        task_type="extract",
        provider="gemini",
        model_name="default",
        input_hash="hash-only",
        output_json="출력",
        token_input=100,
    )

    cost = LLMCostService().record_run(db_session, run, input_text="실제 입력")

    assert cost.estimate_quality == "mixed"


def test_missing_token_usage_uses_input_text_not_input_hash(db_session):
    run = repository.create_llm_run(
        db_session,
        task_type="extract",
        provider="gemini",
        model_name="default",
        input_hash="x" * 64,
        output_json="{}",
    )

    cost = LLMCostService().record_run(db_session, run, input_text="가" * 250)

    assert cost.estimate_quality == "rough"
    assert cost.input_tokens >= 100
    assert run.input_chars == 250
