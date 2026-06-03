from app.db import repository
from app.services.llm_cost_service import LLMCostService


def test_missing_pricing_is_flagged(tmp_path, db_session):
    pricing = tmp_path / "llm_pricing.yaml"
    pricing.write_text("models: []\n", encoding="utf-8")
    service = LLMCostService(pricing)
    run = repository.create_llm_run(
        db_session,
        task_type="extract",
        provider="unknown-provider",
        model_name="unknown-model",
        input_hash="hash",
        output_json="{}",
        token_input=100,
        token_output=100,
    )

    cost = service.record_run(db_session, run, input_text="입력")

    assert cost.estimate_quality == "missing_price"
    assert run.estimate_quality == "missing_price"
