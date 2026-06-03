from app.db import repository
from app.db.models import FactLLMCostLog
from app.services.llm_cost_service import LLMCostService


def test_cost_log_records_estimated_cost_and_batch_discount(db_session):
    service = LLMCostService()
    realtime = repository.create_llm_run(
        db_session,
        task_type="extract",
        provider="gemini",
        model_name="default",
        input_hash="x",
        output_json="{}",
        token_input=1000,
        token_output=1000,
        batch_yn=False,
    )
    batch = repository.create_llm_run(
        db_session,
        task_type="extract",
        provider="gemini",
        model_name="default",
        input_hash="y",
        output_json="{}",
        token_input=1000,
        token_output=1000,
        batch_yn=True,
    )

    realtime_cost = service.record_run(db_session, realtime).estimated_cost_usd
    batch_cost = service.record_run(db_session, batch).estimated_cost_usd

    assert db_session.query(FactLLMCostLog).count() == 2
    assert batch_cost < realtime_cost


def test_cost_summary_reports_cache_hit_rate(db_session):
    run = repository.create_llm_run(
        db_session,
        task_type="extract",
        provider="gemini",
        model_name="default",
        input_hash="x",
        output_json="{}",
        token_input=100,
        token_output=100,
        cached_yn=True,
    )
    LLMCostService().record_run(db_session, run)

    summary = LLMCostService().summary(db_session)

    assert summary["cache_hit_rate"] == 1
    assert summary["total_estimated_cost_usd"] >= 0
