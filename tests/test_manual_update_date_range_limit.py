from fastapi.testclient import TestClient

from app.api.main import app
from app.db.database import get_db
from app.services.admin_auth_service import clear_admin_sessions
from app.services.crawl_job_service import CrawlJobService


def _auth_client(monkeypatch, db_session):
    clear_admin_sessions()
    monkeypatch.setenv("ADMIN_BATCH_PASSWORD", "secret")

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    token = client.post("/api/admin/auth", json={"password": "secret"}).json()["token"]
    return client, {"Authorization": f"Bearer {token}"}


def test_manual_update_rejects_range_over_31_inclusive_days(monkeypatch, db_session):
    monkeypatch.setattr(CrawlJobService, "run_job_by_id", lambda self, crawl_job_id: None)
    client, headers = _auth_client(monkeypatch, db_session)
    try:
        response = client.post(
            "/api/admin/crawl-jobs/manual-range",
            headers=headers,
            json={"date_from": "2026-01-01", "date_to": "2026-02-01"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400


def test_manual_update_accepts_31_inclusive_days(monkeypatch, db_session):
    monkeypatch.setattr(CrawlJobService, "generate_queries", lambda self, db, **kwargs: [])
    monkeypatch.setattr(CrawlJobService, "run_job_by_id", lambda self, crawl_job_id: None)
    client, headers = _auth_client(monkeypatch, db_session)
    try:
        response = client.post(
            "/api/admin/crawl-jobs/manual-range",
            headers=headers,
            json={"date_from": "2026-01-01", "date_to": "2026-01-31"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200


def test_manual_update_adjusts_future_date_to_today(monkeypatch, db_session):
    monkeypatch.setattr(CrawlJobService, "generate_queries", lambda self, db, **kwargs: [])
    monkeypatch.setattr(CrawlJobService, "run_job_by_id", lambda self, crawl_job_id: None)
    client, headers = _auth_client(monkeypatch, db_session)
    try:
        response = client.post(
            "/api/admin/crawl-jobs/manual-range",
            headers=headers,
            json={"date_from": "2026-06-01", "date_to": "2099-01-01"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["date_to"] != "2099-01-01"
