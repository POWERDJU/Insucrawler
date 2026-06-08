from __future__ import annotations


def test_mobile_and_desktop_share_defensive_coverage_dedupe():
    source = open("app/static/dashboard.js", encoding="utf-8").read()

    assert "function dedupeCoverages" in source
    assert "function coverageComponentFamily" in source
    assert "const coverages = dedupeCoverages(product.major_coverages || []);" in source
    assert "function renderMobileCoverageCards(coverages)" in source
    assert "coverages = dedupeCoverages(coverages || []);" in source
    assert "evidence_text" not in source[source.find("function renderMobileCoverageCards") : source.find("function toggleProductDetail")]
