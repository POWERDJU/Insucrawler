from __future__ import annotations

from app.db import repository
from app.services.product_service import ProductService


def test_product_detail_dedupes_major_coverages_before_response(db_session):
    product = repository.upsert_product(
        db_session,
        {
            "raw_product_name": "테스트 건강보험",
            "normalized_product_name": "테스트 건강보험",
            "company_name": "삼성화재",
            "insurance_type": "손해보험",
            "release_year_month": "2026-01",
            "primary_product_type_code": "HEALTH_COMPREHENSIVE",
            "needs_review": False,
        },
    )
    first = repository.add_major_coverage(
        db_session,
        product.product_id,
        {
            "coverage_name_raw": "암 진단비",
            "coverage_name_normalized": "암 진단비",
            "risk_area": "암",
            "benefit_type": "진단비",
            "max_amount_krw": 10000000,
            "condition_text": "암 진단 시",
            "coverage_summary": "암 진단비를 보장합니다.",
            "display_order": 1,
            "confidence": 0.6,
        },
    )
    second = repository.add_major_coverage(
        db_session,
        product.product_id,
        {
            "coverage_name_raw": "암진단비",
            "coverage_name_normalized": "암 진단비",
            "risk_area": "암",
            "benefit_type": "진단비",
            "max_amount_krw": 10000000,
            "condition_text": "암 진단 시",
            "coverage_summary": "암 진단비를 최대 1000만원까지 보장하는 주요 담보다.",
            "display_order": 2,
            "confidence": 0.9,
        },
    )
    repository.add_major_coverage(
        db_session,
        product.product_id,
        {
            "coverage_name_raw": "입원비",
            "coverage_name_normalized": "입원비",
            "risk_area": "입원",
            "benefit_type": "입원비",
            "condition_text": "입원 시",
            "coverage_summary": "입원비를 보장합니다.",
            "display_order": 3,
            "confidence": 0.8,
        },
    )
    db_session.commit()

    detail = ProductService().get_detail(db_session, product.product_id)
    coverages = detail["major_coverages"]

    assert len(coverages) == 2
    assert {item["coverage_name_normalized"] for item in coverages} == {"암 진단비", "입원비"}
    selected = next(item for item in coverages if item["coverage_name_normalized"] == "암 진단비")
    assert selected["coverage_id"] == second.coverage_id
    assert selected["coverage_id"] != first.coverage_id


def test_dashboard_js_uses_shared_coverage_dedupe_for_desktop_and_mobile():
    source = open("app/static/dashboard.js", encoding="utf-8").read()

    assert "function dedupeCoverages" in source
    assert "const coverages = dedupeCoverages(product.major_coverages || []);" in source
    assert "function renderMobileCoverageCards(coverages)" in source
    assert "coverages = dedupeCoverages(coverages || []);" in source
