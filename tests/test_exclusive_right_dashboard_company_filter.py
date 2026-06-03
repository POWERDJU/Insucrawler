from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient

from app.api.main import app
from app.db.database import get_db
from app.db.models import FactArticle
from app.services.exclusive_right_service import ExclusiveRightService


def _seed_right(db_session, text: str, title: str) -> int:
    article = FactArticle(
        source_api="test",
        title=title,
        description=title,
        url=f"https://example.com/{title}",
        original_url=f"https://example.com/original/{title}",
        pub_date=datetime(2026, 5, 1, 9, 0, 0),
        content_hash=f"exclusive-{title}",
    )
    db_session.add(article)
    db_session.commit()
    db_session.refresh(article)
    right = ExclusiveRightService().create_from_text(db_session, text, article=article)
    assert right is not None
    return right.exclusive_right_id


def _client(db_session):
    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


def test_exclusive_right_list_filters_by_insurance_type(db_session):
    _seed_right(db_session, "신한라이프는 생보특약에 대해 3개월 배타적사용권을 획득했다.", "life")
    _seed_right(db_session, "한화손해보험은 손보담보에 대해 6개월 배타적사용권을 획득했다.", "nonlife")
    client = _client(db_session)
    try:
        life = client.get("/api/exclusive-rights", params={"insurance_type": "생명보험"}).json()["items"]
        nonlife = client.get("/api/exclusive-rights", params={"insurance_type": "손해보험"}).json()["items"]
    finally:
        app.dependency_overrides.clear()

    assert [item["insurance_type"] for item in life] == ["생명보험"]
    assert [item["insurance_type"] for item in nonlife] == ["손해보험"]
    assert life[0]["company_name"] == "신한라이프생명"
    assert nonlife[0]["company_name"] == "한화손해보험"


def test_exclusive_right_company_name_alias_filter_and_detail(db_session):
    right_id = _seed_right(db_session, "농협손보가 풍수해보장특약에 대해 6개월 배타적사용권을 획득했다.", "nh")
    client = _client(db_session)
    try:
        listing = client.get("/api/exclusive-rights", params={"company_name": "농협손보"}).json()["items"]
        detail = client.get(f"/api/exclusive-rights/{right_id}").json()
    finally:
        app.dependency_overrides.clear()

    assert len(listing) == 1
    assert listing[0]["company_name_normalized"] == "NH농협손해보험"
    assert detail["company_name_normalized"] == "NH농협손해보험"
    assert detail["observations"][0]["insurance_type"] == "손해보험"
    assert "company_name_raw" not in detail["observations"][0]
    assert "company_matching_confidence" not in detail["observations"][0]


def test_recent_exclusive_rights_dashboard_filters_by_insurance_type(db_session):
    _seed_right(db_session, "신한라이프는 생보특약에 대해 3개월 배타적사용권을 획득했다.", "life-dashboard")
    _seed_right(db_session, "한화손해보험은 손보담보에 대해 6개월 배타적사용권을 획득했다.", "nonlife-dashboard")
    client = _client(db_session)
    try:
        response = client.get("/api/dashboard/recent-exclusive-rights", params={"insurance_type": "생명보험"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["insurance_type"] == "생명보험"
    assert items[0]["company_name"] == "신한라이프생명"
