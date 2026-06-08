from fastapi.testclient import TestClient

from app.api.main import app
from app.db.database import get_db
from app.services.admin_auth_service import clear_admin_sessions
from app.services.crawl_job_service import CrawlJobService


def test_manual_update_defaults_to_batch_postprocess_qwen(monkeypatch, db_session):
    clear_admin_sessions()
    monkeypatch.setenv("ADMIN_BATCH_PASSWORD", "secret")
    monkeypatch.setattr(CrawlJobService, "generate_queries", lambda self, db, **kwargs: [])
    monkeypatch.setattr(CrawlJobService, "run_job_by_id", lambda self, crawl_job_id: None)

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    try:
        token = client.post("/api/admin/auth", json={"password": "secret"}).json()["token"]
        response = client.post(
            "/api/admin/crawl-jobs/manual-range",
            headers={"Authorization": f"Bearer {token}"},
            json={"date_from": "2026-06-01", "date_to": "2026-06-08"},
        )
        detail = client.get(
            f"/api/admin/crawl-jobs/{response.json()['crawl_job_id']}",
            headers={"Authorization": f"Bearer {token}"},
        ).json()
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert detail["extraction_mode"] == "batch"
    assert detail["include_exclusive_right_pipeline"] is True
    assert detail["pipeline_mode"] == "crawl_parse_postprocess_qwen"
    assert detail["include_qwen_adjudication"] is True
