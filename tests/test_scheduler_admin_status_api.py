from fastapi.testclient import TestClient

from app.api.main import app
from app.db.database import get_db
from app.services.admin_auth_service import clear_admin_sessions


def test_scheduler_admin_status_api_requires_admin(monkeypatch, db_session):
    clear_admin_sessions()
    monkeypatch.setenv("ADMIN_BATCH_PASSWORD", "secret")

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    try:
        unauthorized = client.get("/api/admin/scheduled-refresh/status")
        token = client.post("/api/admin/auth", json={"password": "secret"}).json()["token"]
        authorized = client.get(
            "/api/admin/scheduled-refresh/status",
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        app.dependency_overrides.clear()

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
    assert "enabled" in authorized.json()
    assert "next_run_at" in authorized.json()
