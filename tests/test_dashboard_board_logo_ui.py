from __future__ import annotations


def test_dashboard_boards_have_company_logo_slots():
    html = open("app/templates/dashboard.html", encoding="utf-8").read()

    assert "monthlyLogoWrap" in html
    assert "monthlyCompanyLogo" in html
    assert "exclusiveLogoWrap" in html
    assert "exclusiveCompanyLogo" in html
    assert "newsboard-card-with-logo" in html


def test_dashboard_js_renders_company_logos_for_top_boards():
    script = open("app/static/dashboard.js", encoding="utf-8").read()

    assert "function renderNewsboardLogo" in script
    assert "item.company_logo_url" in script
    assert "monthlyCompanyLogo" in script
    assert "exclusiveCompanyLogo" in script
    assert "has-logo" in script


def test_dashboard_css_positions_company_logo_slots():
    css = open("app/static/dashboard.css", encoding="utf-8").read()

    assert ".newsboard-logo-wrap" in css
    assert ".newsboard-company-logo" in css
    assert "object-fit: contain" in css
    assert ".newsboard-card-with-logo.has-logo" in css
