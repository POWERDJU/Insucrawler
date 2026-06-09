from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.main import app
from app.db.database import get_db
from tests.test_monthly_new_product_service import seed_monthly_product


def test_monthly_new_products_api_returns_items(db_session):
    seed_monthly_product(db_session, article_url="https://example.com/monthly-product")

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.get("/api/dashboard/monthly-new-products?year_month=2026-05&limit=1")
        assert response.status_code == 200
        payload = response.json()
        assert payload["year_month"] == "2026-05"
        assert payload["random_sample"] is True
        assert len(payload["items"]) == 1
        assert payload["items"][0]["product_name"] == "월간 테스트 건강보험"
        assert payload["items"][0]["article_url"] == "https://example.com/monthly-product"
    finally:
        app.dependency_overrides.clear()


def test_monthly_new_products_api_applies_limit(db_session):
    seed_monthly_product(db_session, name="월간 테스트 건강보험 A", article_url="https://example.com/monthly-a")
    seed_monthly_product(db_session, name="월간 테스트 건강보험 B", article_url="https://example.com/monthly-b")

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.get("/api/dashboard/monthly-new-products?year_month=2026-05&limit=1")
        assert response.status_code == 200
        assert len(response.json()["items"]) == 1
    finally:
        app.dependency_overrides.clear()


def test_dashboard_html_contains_monthly_board():
    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    assert "monthlyNewProductBoard" in response.text
    assert "monthlyBoardCard" in response.text
    assert "monthlyPrev" in response.text
    assert "monthlyNext" in response.text
    assert "이달의 신상품 현황판" in response.text


def test_dashboard_js_contains_monthly_board_behaviour():
    script = open("app/static/dashboard.js", encoding="utf-8").read()

    assert "loadMonthlyNewProducts" in script
    assert "setInterval(nextMonthlyItem, 5000)" in script
    assert "mouseenter" in script
    assert "focusin" in script
    assert "stopMonthlyBoardTimer" in script
    assert "insurance_type" in script
    assert "sample_ts" in script
