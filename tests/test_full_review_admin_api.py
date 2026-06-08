from fastapi.testclient import TestClient

from app.api.main import app
from app.db.database import get_db
from app.services.admin_auth_service import clear_admin_sessions
from app.services.qwen_adjudication_service import QwenAdjudicationService


def test_full_review_admin_api_runs_and_fetches_job(monkeypatch, db_session, tmp_path):
    clear_admin_sessions()
    monkeypatch.setenv("ADMIN_BATCH_PASSWORD", "secret")
    monkeypatch.setenv("ENABLE_FINAL_ADJUDICATION_LLM", "false")

    def fake_init(self, **kwargs):
        self.qwen_service = QwenAdjudicationService()
        self.output_dir = tmp_path
        self.docs_dir = tmp_path

    monkeypatch.setattr("app.services.full_data_review_service.FullDataReviewService.__init__", fake_init)

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    try:
        token = client.post("/api/admin/auth", json={"password": "secret"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post(
            "/api/admin/full-review/qwen",
            headers=headers,
            json={"include_rule_review": False, "max_products": 1, "max_exclusive": 1},
        )
        job_id = response.json()["full_review_job_id"]
        detail = client.get(f"/api/admin/full-review/{job_id}", headers=headers)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert detail.status_code == 200
    assert detail.json()["full_review_job_id"] == job_id
