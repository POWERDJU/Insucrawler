from __future__ import annotations


def test_dashboard_js_defensively_dedupes_component_families_for_mobile_and_desktop():
    source = open("app/static/dashboard.js", encoding="utf-8").read()

    assert "function coverageComponentFamily" in source
    assert "function normalizeCoverageArea" in source
    assert "function normalizeBenefitType" in source
    assert "renderMobileCoverageCards(product.major_coverages || [])" in source
    assert "const coverages = dedupeCoverages(product.major_coverages || []);" in source
