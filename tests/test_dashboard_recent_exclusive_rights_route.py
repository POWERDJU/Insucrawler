from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.main import app
from app.db.database import get_db
from app.db.models import FactArticle
from app.services.exclusive_right_service import ExclusiveRightService
from datetime import datetime


def test_recent_exclusive_rights_route_returns_empty_items_instead_of_404(db_session):
    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).get("/api/dashboard/recent-exclusive-rights")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"] == []
    assert payload["months_back"] == 12
    assert "fallback_used" in payload


def test_dashboard_js_fetches_recent_exclusive_rights_route():
    script = open("app/static/dashboard.js", encoding="utf-8").read()

    assert "/api/dashboard/recent-exclusive-rights" in script
    assert "loadRecentExclusiveRights" in script


def test_recent_exclusive_rights_response_omits_debug_fields(db_session):
    article = FactArticle(
        source_api="test",
        title="삼성생명 배타적사용권",
        description="삼성생명 배타적사용권",
        url="https://example.com/recent-exclusive",
        original_url="https://example.com/recent-exclusive-original",
        pub_date=datetime(2026, 5, 1, 9, 0, 0),
        content_hash="recent-exclusive-simplified",
    )
    db_session.add(article)
    db_session.commit()
    ExclusiveRightService().create_from_text(
        db_session,
        "삼성생명은 돌봄 로봇 제공 서비스에 대해 6개월 배타적 사용권을 인정받았다.",
        article=article,
    )

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    try:
        payload = TestClient(app).get("/api/dashboard/recent-exclusive-rights").json()
    finally:
        app.dependency_overrides.clear()

    item = payload["items"][0]
    assert "exclusive_right_type" not in item
    assert "exclusive_right_type_code" not in item
    assert "article_count" not in item
    assert "needs_review" not in item
    assert "confidence_total" not in item
