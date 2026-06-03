from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient

from app.api.main import app
from app.db.database import get_db
from app.db.models import FactArticle
from app.services.admin_auth_service import clear_admin_sessions


def _override_db_session(db_session):
    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override


def _token(client: TestClient, monkeypatch):
    clear_admin_sessions()
    monkeypatch.setenv("ADMIN_BATCH_PASSWORD", "secret")
    return client.post("/api/admin/auth", json={"password": "secret"}).json()["token"]


def _article(db_session):
    article = FactArticle(
        source_api="naver",
        title="한화손해보험 6개월 배타적사용권 획득",
        description="한화손해보험은 신상품심의위원회에서 배타적사용권을 획득했다.",
        url="https://example.com/admin-exclusive-status",
        original_url="https://example.com/admin-exclusive-status",
        pub_date=datetime(2026, 1, 16),
        content_hash="admin-exclusive-status",
    )
    db_session.add(article)
    db_session.commit()


def test_admin_exclusive_right_queue_status_and_consolidate(monkeypatch, db_session):
    _article(db_session)
    _override_db_session(db_session)
    client = TestClient(app)
    try:
        token = _token(client, monkeypatch)
        enqueue_response = client.post(
            "/api/admin/exclusive-rights/extract-pending",
            headers={"Authorization": f"Bearer {token}"},
            json={"limit": 10, "mode": "batch", "date_from": "2026-01-01", "date_to": "2026-01-31"},
        )
        status_response = client.get(
            "/api/admin/exclusive-rights/extract-queue-status?date_from=2026-01-01&date_to=2026-01-31",
            headers={"Authorization": f"Bearer {token}"},
        )
        consolidate_response = client.post(
            "/api/admin/exclusive-rights/consolidate",
            headers={"Authorization": f"Bearer {token}"},
            json={"mode": "dry_run", "date_from": "2026-01-01", "date_to": "2026-01-31"},
        )

        assert enqueue_response.status_code == 200
        assert status_response.status_code == 200
        assert status_response.json()["queued_batch_eligible_count"] == 1
        assert consolidate_response.status_code == 200
        assert consolidate_response.json()["mode"] == "dry_run"
    finally:
        app.dependency_overrides.clear()

