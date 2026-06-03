from __future__ import annotations

from datetime import datetime
from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app.api.main import app
from app.db.database import get_db
from app.db.models import FactArticle
from app.services.exclusive_right_service import ExclusiveRightService


REMOVED_FIELDS = {
    "company_name_raw",
    "company_display_name",
    "exclusive_right_type",
    "exclusive_right_type_code",
    "subject_type",
    "exclusivity_period_text",
    "acquired_year_month_basis",
    "acquired_date_text",
    "article_count",
    "confidence_total",
    "needs_review",
}


def _client(db_session) -> TestClient:
    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


def _seed(db_session):
    article = FactArticle(
        source_api="test",
        title="한화손해보험 배타적사용권",
        description="한화손해보험 배타적사용권",
        url="https://example.com/exclusive",
        original_url="https://example.com/original-exclusive",
        pub_date=datetime(2026, 5, 1, 9, 0, 0),
        content_hash="exclusive-schema-simplified",
    )
    db_session.add(article)
    db_session.commit()
    db_session.refresh(article)
    return ExclusiveRightService().create_from_text(
        db_session,
        "한화손해보험은 암진단비확대특약에 대해 6개월 배타적사용권을 획득했다.",
        article=article,
    )


def test_exclusive_right_api_omits_removed_fields_by_default(db_session):
    right = _seed(db_session)
    client = _client(db_session)
    try:
        item = client.get("/api/exclusive-rights").json()["items"][0]
        detail = client.get(f"/api/exclusive-rights/{right.exclusive_right_id}").json()
    finally:
        app.dependency_overrides.clear()

    assert not (REMOVED_FIELDS & set(item))
    assert not (REMOVED_FIELDS & set(detail))
    assert not (REMOVED_FIELDS & set(detail["observations"][0]))


def test_exclusive_right_export_uses_simplified_columns(db_session):
    _seed(db_session)
    client = _client(db_session)
    try:
        response = client.post("/api/exclusive-rights/export", json={})
    finally:
        app.dependency_overrides.clear()

    workbook = load_workbook(BytesIO(response.content))
    headers = [cell.value for cell in workbook["배타적사용권"][1]]

    assert headers == [
        "배타적사용권 ID",
        "업종",
        "보험회사",
        "상품/특약/제도명",
        "배타적사용권 기간 개월 수",
        "획득년월",
        "주요 특징",
        "대표 기사 제목",
        "대표 기사 URL",
        "alias 목록",
        "근거문장",
    ]
