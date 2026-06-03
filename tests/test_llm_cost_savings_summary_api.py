from datetime import datetime

from fastapi.testclient import TestClient

from app.api.main import app
from app.db.database import get_db
from app.db.models import FactArticle, FactContentScreening, FactLLMCostLog, FactLLMRun
from app.services.admin_auth_service import clear_admin_sessions


def auth_client(monkeypatch, db_session):
    clear_admin_sessions()
    monkeypatch.setenv("ADMIN_BATCH_PASSWORD", "secret")

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    token = client.post("/api/admin/auth", json={"password": "secret"}).json()["token"]
    return client, {"Authorization": f"Bearer {token}"}


def seed_cost_savings_rows(db_session):
    article = FactArticle(
        source_api="naver",
        title="삼성화재 건강보험 출시",
        description="보장성 신상품을 선보였다.",
        url="https://example.test/a",
        content_hash="savings-api-hash",
        collected_at=datetime(2026, 1, 10),
    )
    db_session.add(article)
    db_session.flush()
    db_session.add(
        FactContentScreening(
            article_id=article.article_id,
            rule_relevance_score=0.9,
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
        token_input=100,
        token_output=50,
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
            output_tokens=50,
            estimated_cost_usd=0.00001,
            estimate_quality="actual_tokens",
            created_at=datetime(2026, 1, 10),
        )
    )
    db_session.commit()


def test_llm_cost_savings_summary_requires_admin(monkeypatch, db_session):
    client, _ = auth_client(monkeypatch, db_session)
    try:
        response = client.get("/api/admin/llm-cost-savings-summary")
        assert response.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_llm_cost_savings_summary_returns_breakdown(monkeypatch, db_session):
    seed_cost_savings_rows(db_session)
    client, headers = auth_client(monkeypatch, db_session)
    try:
        response = client.get("/api/admin/llm-cost-savings-summary", headers=headers)
        payload = response.json()

        assert response.status_code == 200
        assert "baseline_estimated_cost_usd" in payload
        assert "optimized_actual_cost_usd" in payload
        assert "estimated_savings_usd" in payload
        assert "estimated_savings_rate" in payload
        assert "breakdown" in payload
    finally:
        app.dependency_overrides.clear()
