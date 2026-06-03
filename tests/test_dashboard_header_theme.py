from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.main import app


client = TestClient(app)


def test_dashboard_header_has_clean_brand_title_without_logo_or_subtitle():
    response = client.get("/")

    assert response.status_code == 200
    assert "보험상품 뉴스 자동조사봇" in response.text
    assert "보험상품 뉴스, 배타적사용권, 상품별 보장내용 자동 조사" not in response.text
    assert "한화손해보험" not in response.text
    assert "assets/hwgeneralins.png" not in response.text
    assert "Noto+Sans+KR" in response.text


def test_dashboard_admin_update_button_uses_dino_icon_and_existing_id():
    response = client.get("/")

    assert response.status_code == 200
    assert 'class="header-actions desktop-only"' in response.text
    assert 'id="toggleAdminPanel"' in response.text
    assert "admin-update-button" in response.text
    assert "assets/admin-dino.png" in response.text
    assert "admin-update-icon" in response.text
    assert "관리자 업데이트" in response.text


def test_dashboard_css_uses_hanwha_orange_dark_theme():
    response = client.get("/static/dashboard.css")
    css = response.text

    assert "--brand-orange: #ff6600" in css
    assert "--bg-main: #080808" in css
    assert "--bg-panel: #111111" in css
    assert "--line-gray: #3a3a3a" in css
    assert "--text-main: #ffffff" in css
    assert 'font-family: "Noto Sans KR"' in css
    assert ".app-header" in css
    assert "background: var(--brand-orange)" in css


def test_dashboard_css_forces_filter_controls_to_dark_panels():
    css = client.get("/static/dashboard.css").text

    assert ".checkbox-select" in css
    assert ".checkbox-select.disabled" in css
    assert ".checkbox-list" in css
    assert ".checkbox-empty" in css
    assert ".exclusive-list-filters" in css
    assert "background: var(--bg-card)" in css
    assert "select option" in css
    assert "background: #141414" in css
    assert "border-color: var(--brand-orange)" in css


def test_dashboard_css_keeps_newsboards_two_column_layout():
    css = client.get("/static/dashboard.css").text

    assert ".top-newsboards" in css
    assert "grid-template-columns: minmax(0, 1fr) minmax(0, 1fr)" in css
    assert "@media (max-width: 960px)" in css
