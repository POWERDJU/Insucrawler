from datetime import datetime

from fastapi.testclient import TestClient

from app.api.main import app
from app.db.database import get_db
from app.db.models import FactArticle, FactLLMQueue
from app.services.admin_auth_service import clear_admin_sessions


def _override_db_session(db_session):
    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override


def _token(client: TestClient, monkeypatch):
    clear_admin_sessions()
    monkeypatch.setenv("ADMIN_BATCH_PASSWORD", "secret")
    return client.post("/api/admin/auth", json={"password": "secret"}).json()["token"]


def _exclusive_article(db_session):
    article = FactArticle(
        source_api="naver",
        title="한화손해보험 6개월 배타적사용권 획득",
        description="신상품심의위원회가 새로운 위험 담보 독창성을 인정했다.",
        url="https://example.com/admin-exclusive",
        original_url="https://example.com/admin-exclusive",
        pub_date=datetime(2026, 1, 11),
        content_hash="admin-exclusive",
    )
    db_session.add(article)
    db_session.commit()
    return article


def test_admin_extract_pending_exclusive_rights_enqueues_candidate(monkeypatch, db_session):
    _exclusive_article(db_session)
    _override_db_session(db_session)
    client = TestClient(app)
    try:
        token = _token(client, monkeypatch)
        response = client.post(
            "/api/admin/exclusive-rights/extract-pending",
            headers={"Authorization": f"Bearer {token}"},
            json={"limit": 10, "mode": "enqueue_only", "date_from": "2026-01-01", "date_to": "2026-01-31"},
        )

        queue = db_session.query(FactLLMQueue).filter_by(task_type="exclusive_right_extract").one()
        assert response.status_code == 200
        assert response.json()["queued"] == 1
        assert queue.batch_eligible_yn is False
    finally:
        app.dependency_overrides.clear()
