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


def test_dashboard_newsboard_cards_have_fixed_height_and_summary_clamp():
    css = open("app/static/dashboard.css", encoding="utf-8").read()

    assert ".top-newsboards .monthly-board" in css
    assert "min-height: 316px" in css
    assert "max-height: 316px" in css
    assert ".top-newsboards .monthly-card p" in css
    assert "-webkit-line-clamp: 4" in css
    assert ".top-newsboards .monthly-card h3" in css
    assert "-webkit-line-clamp: 2" in css
    assert "min-height: 292px" in css
    assert "justify-content: flex-start" in css
    assert "margin-top: auto" not in css
    assert ".top-newsboards .monthly-card-footer" in css
    assert "position: absolute" in css
    assert "bottom: 18px" in css
    assert "text-align: right" in css
