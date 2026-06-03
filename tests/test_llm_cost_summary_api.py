from fastapi.testclient import TestClient

from app.api.main import app
from app.db.database import get_db
from app.db.models import FactLLMCostLog, FactLLMRun
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


def test_llm_cost_summary_requires_admin(monkeypatch, db_session):
    client, _ = auth_client(monkeypatch, db_session)
    try:
        response = client.get("/api/admin/llm-cost-summary")
        assert response.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_llm_cost_summary_includes_token_totals(monkeypatch, db_session):
    run = FactLLMRun(task_type="extract", provider="gemini", model_name="default", token_input=100, token_output=50)
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
            estimated_cost_usd=0.01,
            estimate_quality="actual_tokens",
        )
    )
    db_session.commit()
    client, headers = auth_client(monkeypatch, db_session)
    try:
        response = client.get("/api/admin/llm-cost-summary", headers=headers)
        payload = response.json()

        assert response.status_code == 200
        assert payload["input_tokens_total"] == 100
        assert payload["output_tokens_total"] == 50
        assert payload["extract_run_count"] == 1
    finally:
        app.dependency_overrides.clear()
