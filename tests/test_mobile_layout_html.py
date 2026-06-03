from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.main import app


client = TestClient(app)


def test_dashboard_has_mobile_layout_scaffolding():
    response = client.get("/")
    html = response.text

    assert response.status_code == 200
    assert 'data-mobile-active-view="products"' in html
    assert "mobile-view-tabs" in html
    assert "mobile-board-tabs" in html
    assert 'data-mobile-view-tab="products"' in html
    assert 'data-mobile-view-tab="exclusive-rights"' in html
    assert "mobile-products-section" in html
    assert "mobile-exclusive-section" in html
    assert 'id="mobileFilterSummary"' in html
    assert 'id="mobileFilterSheet"' in html
    assert 'id="mobileProductCards"' in html
    assert 'id="mobileProductDetailModal"' in html
    assert 'id="mobileExclusiveCards"' in html
    assert 'id="mobileExclusiveFilterSheet"' in html
    assert 'role="dialog"' in html
    assert 'aria-modal="true"' in html


def test_mobile_css_uses_mobile_only_breakpoint_and_cards():
    css = client.get("/static/dashboard.css").text

    assert "@media (max-width: 767px)" in css
    assert ".desktop-results" in css
    assert ".mobile-results" in css
    assert 'data-mobile-active-view="products"' in css
    assert 'data-mobile-active-view="exclusive-rights"' in css
    assert ".mobile-exclusive-section" in css
    assert ".mobile-products-section" in css
    assert ".mobile-filter-sheet" in css
    assert ".mobile-product-card" in css
    assert ".mobile-detail-modal" in css
    assert ".mobile-coverage-card" in css
    assert ".mobile-exclusive-card" in css
    assert "overflow-x: hidden" in css
    assert "min-height: 44px" in css


def test_mobile_javascript_functions_exist():
    js = client.get("/static/dashboard.js").text

    for name in [
        "isMobileViewport",
        "initMobileLayout",
        "openMobileFilterSheet",
        "closeMobileFilterSheet",
        "syncDesktopFiltersToMobile",
        "syncMobileFiltersToDesktop",
        "updateMobileFilterSummary",
        "renderMobileProductCards",
        "openMobileProductDetail",
        "closeMobileProductDetail",
        "renderMobileProductDetail",
        "renderMobileCoverageCards",
        "renderMobileExclusiveCards",
        "setActiveMobileView",
    ]:
        assert f"function {name}" in js or f"async function {name}" in js


def test_mobile_card_renderers_do_not_expose_internal_fields():
    js = client.get("/static/dashboard.js").text
    mobile_section = js[js.index("function renderMobileProductCards") : js.index("function bindAdminEvents")]

    forbidden = [
        "주요보장수",
        "관련기사수",
        "검수필요",
        "confidence_total",
        "product_status",
        "보정이력",
        "통합이력",
        "추출근거",
        "evidence_text",
    ]
    for word in forbidden:
        assert word not in mobile_section
