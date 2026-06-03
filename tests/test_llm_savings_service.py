from datetime import datetime

from app.db.models import FactArticle, FactContentScreening, FactLLMCostLog, FactLLMRun
from app.services.llm_savings_service import LLMSavingsService


def add_article(db, article_id: int, title: str = "건강보험 출시") -> FactArticle:
    item = FactArticle(
        article_id=article_id,
        source_api="naver",
        title=title,
        description="보험사가 신상품을 출시했다.",
        url=f"https://example.test/{article_id}",
        content_hash=f"hash-{article_id}",
        collected_at=datetime(2026, 1, 10),
    )
    db.add(item)
    db.flush()
    return item


def test_savings_summary_calculates_rate(db_session):
    for idx in range(1, 4):
        add_article(db_session, idx)
        db_session.add(
            FactContentScreening(
                article_id=idx,
                rule_relevance_score=0.8,
                is_candidate=True,
                llm_required_yn=True,
                llm_priority="high",
                created_at=datetime(2026, 1, 10),
            )
        )
    run = FactLLMRun(
        task_type="extract",
        provider="gemini",
        model_name="default",
        input_hash="do-not-use-for-token-estimate",
        output_json="{}",
        token_input=100,
        token_output=100,
        created_at=datetime(2026, 1, 10),
    )
    db_session.add(run)
    db_session.flush()
    db_session.add(
        FactLLMCostLog(
            llm_run_id=run.llm_run_id,
            provider="gemini",
            model_name="default",
            task_type="extract",
            input_tokens=100,
            output_tokens=100,
            estimated_cost_usd=0.00005,
            estimate_quality="actual_tokens",
            created_at=datetime(2026, 1, 10),
        )
    )
    db_session.commit()

    summary = LLMSavingsService().get_savings_summary(db_session, date_from="2026-01-01", date_to="2026-01-31")

    assert summary["baseline_estimated_cost_usd"] > summary["optimized_actual_cost_usd"]
    assert summary["estimated_savings_rate"] == round(1 - summary["optimized_actual_cost_usd"] / summary["baseline_estimated_cost_usd"], 6)


def test_savings_summary_handles_zero_baseline(db_session):
    summary = LLMSavingsService().get_savings_summary(db_session)

    assert summary["baseline_estimated_cost_usd"] == 0
    assert summary["estimated_savings_rate"] == 0
