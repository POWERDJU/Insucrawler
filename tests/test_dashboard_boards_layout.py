from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.main import app


def test_dashboard_boards_share_top_newsboards_wrapper():
    response = TestClient(app).get("/")

    assert response.status_code == 200
    html = response.text
    assert "top-newsboards" in html
    assert html.index("top-newsboards") < html.index("monthlyNewProductBoard") < html.index("recentExclusiveRightsBoard")
    assert "board-card" in html


def test_dashboard_css_has_two_column_board_grid_and_mobile_breakpoint():
    css = open("app/static/dashboard.css", encoding="utf-8").read()

    assert ".top-newsboards" in css
    assert "grid-template-columns: minmax(0, 1fr) minmax(0, 1fr)" in css
    assert "@media (max-width: 960px)" in css
    assert "grid-template-columns: 1fr" in css
