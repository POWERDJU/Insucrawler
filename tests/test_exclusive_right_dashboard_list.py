from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient

from app.api.main import app
from app.db.database import get_db
from app.db.models import FactArticle
from app.services.exclusive_right_service import ExclusiveRightService


def _seed_right(db, *, text: str, title: str, pub_month: str = "2026-05"):
    article = FactArticle(
        source_api="test",
        title=title,
        description=f"{title} 주요 특징",
        url=f"https://example.com/{title}",
        original_url=f"https://example.com/original/{title}",
        pub_date=datetime.fromisoformat(f"{pub_month}-03T09:00:00"),
        content_hash=f"exclusive-list-{title}",
    )
    db.add(article)
    db.commit()
    db.refresh(article)
    right = ExclusiveRightService().create_from_text(db, text, article=article)
    assert right is not None
    return right


def _client(db):
    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


def test_dashboard_html_and_js_include_exclusive_right_list_panel():
    client = TestClient(app)
    html = client.get("/").text
    script = open("app/static/dashboard.js", encoding="utf-8").read()

    assert "exclusiveRightListPanel" in html
    assert "exclusiveRightSearch" in html
    assert "exclusiveRightExcelDownload" in html
    assert "exclusiveRightCompanyNamesAll" in html
    assert "exclusiveRightCompanyNames" in html
    assert 'id="exclusiveRightCompanyName"' not in html
    assert "collectExclusiveRightQuery" in script
    assert "/api/exclusive-rights/export" in script
    assert "company_names" in script


def test_exclusive_right_list_filters_and_article_url(db_session):
    _seed_right(
        db_session,
        text="한화손해보험은 암 신담보에 대해 6개월 배타적사용권을 획득했다.",
        title="한화손해보험 암 신담보 배타적사용권",
    )
    _seed_right(
        db_session,
        text="신한라이프는 연금 특약에 대해 3개월 배타적사용권을 획득했다.",
        title="신한라이프 연금 특약 배타적사용권",
    )
    client = _client(db_session)
    try:
        nonlife = client.get("/api/exclusive-rights", params={"insurance_type": "손해보험"}).json()["items"]
        keyword = client.get("/api/exclusive-rights", params={"keyword": "연금"}).json()["items"]
        month = client.get(
            "/api/exclusive-rights",
            params={"acquired_year_month_from": "2026-05", "acquired_year_month_to": "2026-05"},
        ).json()["items"]
    finally:
        app.dependency_overrides.clear()

    assert len(nonlife) == 1
    assert nonlife[0]["insurance_type"] == "손해보험"
    assert nonlife[0]["primary_article_url"] == "https://example.com/original/한화손해보험 암 신담보 배타적사용권"
    assert len(keyword) == 1
    assert keyword[0]["company_name"] == "신한라이프생명"
    assert len(month) == 2
