from __future__ import annotations

from datetime import datetime
from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app.api.main import app
from app.db.database import get_db
from app.db.models import FactArticle
from app.services.exclusive_right_service import ExclusiveRightService


SIMPLIFIED_HEADERS = [
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


def test_exclusive_right_export_has_simplified_company_columns_in_order(db_session):
    article = FactArticle(
        source_api="test",
        title="한화손해보험 배타적사용권",
        description="한화손해보험 배타적사용권",
        url="https://example.com/export",
        original_url="https://example.com/export-original",
        pub_date=datetime(2026, 5, 1, 9, 0, 0),
        content_hash="exclusive-export",
    )
    db_session.add(article)
    db_session.commit()
    db_session.refresh(article)
    ExclusiveRightService().create_from_text(
        db_session,
        "한화손해보험은 OO보험에 대해 6개월 배타적사용권을 획득했다.",
        article=article,
    )

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).post("/api/exclusive-rights/export", json={"insurance_type": "손해보험"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    workbook = load_workbook(BytesIO(response.content))
    sheet = workbook["배타적사용권"]
    headers = [cell.value for cell in sheet[1]]
    assert headers == SIMPLIFIED_HEADERS
    assert "원문 회사명" not in headers
    assert "구분" not in headers
    assert "subject_type" not in headers
    row = [cell.value for cell in sheet[2]]
    assert row[1] == "손해보험"
    assert row[2] == "한화손해보험"
