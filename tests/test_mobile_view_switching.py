from __future__ import annotations

from pathlib import Path


HTML = Path("app/templates/dashboard.html").read_text(encoding="utf-8")
CSS = Path("app/static/dashboard.css").read_text(encoding="utf-8")
JS = Path("app/static/dashboard.js").read_text(encoding="utf-8")


def _function_body(name: str) -> str:
    marker = f"function {name}"
    async_marker = f"async function {name}"
    start = JS.find(marker)
    if start < 0:
      start = JS.find(async_marker)
    assert start >= 0, f"{name} function not found"
    next_function = JS.find("\nfunction ", start + 1)
    next_async = JS.find("\nasync function ", start + 1)
    candidates = [idx for idx in [next_function, next_async] if idx > start]
    end = min(candidates) if candidates else len(JS)
    return JS[start:end]


def test_mobile_view_tabs_drive_full_view_state():
    assert 'data-mobile-active-view="products"' in HTML
    assert 'data-mobile-view-tab="products"' in HTML
    assert 'data-mobile-view-tab="exclusive-rights"' in HTML
    assert ">상품</button>" in HTML

    body = _function_body("setActiveMobileView")
    assert 'data-mobile-active-view"' in body
    assert "state.activeMobileView" in body
    assert "loadExclusiveRightList" in body
    assert "closeMobileProductDetail" in body


def test_mobile_sections_are_classed_by_product_and_exclusive_views():
    assert 'id="monthlyNewProductBoard" class="monthly-board board-card mobile-products-section"' in HTML
    assert 'id="recentExclusiveRightsBoard" class="monthly-board exclusive-board board-card mobile-exclusive-section"' in HTML
    assert 'class="mobile-filter-bar mobile-only mobile-products-section"' in HTML
    assert 'class="workbench mobile-products-section"' in HTML
    assert 'id="exclusiveRightListPanel" class="panel exclusive-list-panel mobile-exclusive-section"' in HTML
    assert 'id="mobileExclusiveCards" class="mobile-results mobile-only mobile-exclusive-section"' in HTML


def test_mobile_css_hides_inactive_view_sections_only_on_mobile():
    media_start = CSS.index("@media (max-width: 767px)")
    mobile_css = CSS[media_start:]

    assert '.dashboard-shell[data-mobile-active-view="products"] .mobile-exclusive-section' in mobile_css
    assert '.dashboard-shell[data-mobile-active-view="exclusive-rights"] .mobile-products-section' in mobile_css
    assert "display: none !important" in mobile_css
    assert ".top-newsboards" in mobile_css


def test_mobile_filter_paths_remain_independent():
    product_body = _function_body("applyMobileProductFilter")
    exclusive_body = _function_body("applyMobileExclusiveFilter")
    open_body = _function_body("openMobileFilterSheet")

    assert "runQuery" in product_body
    assert "loadExclusiveRightList" not in product_body
    assert "syncDesktopExclusiveFiltersToMobile" not in product_body
    assert "loadExclusiveRightList" in exclusive_body
    assert "runQuery" not in exclusive_body
    assert "syncDesktopExclusiveFiltersToMobile" not in open_body


def test_mobile_card_renderers_keep_condensed_fields():
    product_body = _function_body("renderMobileProductCards")
    exclusive_body = _function_body("renderMobileExclusiveCards")

    for forbidden in ["insurance_type", "major_coverage_count", "article_count", "needs_review", "confidence_total", "product_status"]:
        assert forbidden not in product_body

    for forbidden in ["article_count", "needs_review", "exclusive_right_type", "confidence_total", "company_name_raw"]:
        assert forbidden not in exclusive_body
