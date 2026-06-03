from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.main import app
from app.db.database import get_db
from app.db.models import FactExclusiveUseRight
from app.services.company_logo_service import CompanyLogoService
from tests.test_monthly_new_product_service import seed_monthly_product


def _configure_logo_dir(tmp_path, monkeypatch) -> None:
    life_dir = tmp_path / "LOGO" / "LIFE"
    nonlife_dir = tmp_path / "LOGO" / "NONLIFE"
    life_dir.mkdir(parents=True)
    nonlife_dir.mkdir(parents=True)
    (life_dir / "삼성생명.png").write_bytes(b"life-logo")
    monkeypatch.setenv("COMPANY_LOGO_LIFE_DIR", str(life_dir))
    monkeypatch.setenv("COMPANY_LOGO_NONLIFE_DIR", str(nonlife_dir))
    CompanyLogoService().refresh_logo_index()


def test_monthly_new_products_include_company_logo_url(db_session, tmp_path, monkeypatch):
    _configure_logo_dir(tmp_path, monkeypatch)
    seed_monthly_product(
        db_session,
        name="테스트 건강보험",
        company_name="삼성생명",
        insurance_type="생명보험",
        article_title="삼성생명, 테스트 건강보험 출시",
        article_description="삼성생명이 테스트 건강보험을 출시했다.",
    )

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).get("/api/dashboard/monthly-new-products", params={"year_month": "2026-05"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["company_logo_url"].startswith("/api/company-logos/file/life/%EC%82%BC%EC%84%B1%EC%83%9D%EB%AA%85.png?v=")


def test_recent_exclusive_rights_include_company_logo_url(db_session, tmp_path, monkeypatch):
    _configure_logo_dir(tmp_path, monkeypatch)
    db_session.add(
        FactExclusiveUseRight(
            company_name_normalized="삼성생명",
            insurance_type="생명보험",
            subject_name="삼성 치매보험 돌봄 로봇 제공 서비스",
            subject_core_key="삼성치매보험돌봄로봇제공서비스",
            exclusivity_months=6,
            acquired_year_month="2026-05",
            feature_summary="치매보험에 포함된 돌봄 로봇 제공 서비스입니다.",
            primary_article_title="삼성생명, 돌봄 로봇 제공 서비스 배타적사용권 인정",
            primary_article_url="https://example.com/exclusive-logo",
            article_count=1,
            confidence_total=0.9,
            needs_review=False,
            event_status="active",
            alias_names_json='["돌봄 로봇 제공 서비스"]',
            evidence_text="삼성생명은 돌봄 로봇 제공 서비스에 대해 6개월 배타적사용권을 인정받았다.",
        )
    )
    db_session.commit()

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).get("/api/dashboard/recent-exclusive-rights")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["company_logo_url"].startswith("/api/company-logos/file/life/%EC%82%BC%EC%84%B1%EC%83%9D%EB%AA%85.png?v=")
