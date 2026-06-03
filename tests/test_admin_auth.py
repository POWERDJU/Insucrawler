from fastapi.testclient import TestClient

from app.api.main import app
from app.db.database import get_db
from app.services.admin_auth_service import clear_admin_sessions


def override_db_session(db_session):
    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override


def test_admin_auth_rejects_bad_password(monkeypatch, db_session):
    clear_admin_sessions()
    monkeypatch.setenv("ADMIN_BATCH_PASSWORD", "secret")
    override_db_session(db_session)
    client = TestClient(app)
    try:
        response = client.post("/api/admin/auth", json={"password": "bad"})
        assert response.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_admin_auth_issues_token_and_admin_api_requires_it(monkeypatch, db_session):
    clear_admin_sessions()
    monkeypatch.setenv("ADMIN_BATCH_PASSWORD", "secret")
    override_db_session(db_session)
    client = TestClient(app)
    try:
        unauthorized = client.get("/api/admin/crawl-jobs")
        token_response = client.post("/api/admin/auth", json={"password": "secret"})
        token = token_response.json()["token"]
        authorized = client.get("/api/admin/crawl-jobs", headers={"Authorization": f"Bearer {token}"})

        assert unauthorized.status_code == 401
        assert token_response.status_code == 200
        assert authorized.status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_admin_auth_rejects_expired_token(monkeypatch, db_session):
    clear_admin_sessions()
    monkeypatch.setenv("ADMIN_BATCH_PASSWORD", "secret")
    monkeypatch.setenv("ADMIN_SESSION_TTL_MINUTES", "0")
    override_db_session(db_session)
    client = TestClient(app)
    try:
        token = client.post("/api/admin/auth", json={"password": "secret"}).json()["token"]
        response = client.get("/api/admin/crawl-jobs", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401
    finally:
        app.dependency_overrides.clear()
