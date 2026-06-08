from __future__ import annotations

from app.db import repository
from app.services.product_service import ProductService


def _product(db_session):
    return repository.upsert_product(
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


def test_product_detail_returns_deduped_coverages_and_hides_raw_by_default(db_session):
    product = _product(db_session)
    first = repository.add_major_coverage(db_session, product.product_id, {"coverage_name_raw": "임신지원금", "confidence": 0.6})
    second = repository.add_major_coverage(db_session, product.product_id, {"coverage_name_raw": "임신지원금 특약", "confidence": 0.9})
    repository.add_major_coverage(db_session, product.product_id, {"coverage_name_raw": "출산지원금", "confidence": 0.8})
    db_session.commit()

    detail = ProductService().get_detail(db_session, product.product_id)

    assert "raw_coverages" not in detail
    assert len(detail["major_coverages"]) == 2
    assert detail["coverage_dedupe_summary"]["raw_count"] == 3
    assert detail["coverage_dedupe_summary"]["deduped_count"] == 2
    selected_ids = {item["coverage_id"] for item in detail["major_coverages"]}
    assert second.coverage_id in selected_ids
    assert first.coverage_id not in selected_ids


def test_product_detail_debug_includes_raw_coverages(db_session):
    product = _product(db_session)
    repository.add_major_coverage(db_session, product.product_id, {"coverage_name_raw": "임신지원금"})
    repository.add_major_coverage(db_session, product.product_id, {"coverage_name_raw": "임신 지원금"})
    db_session.commit()

    detail = ProductService().get_detail(db_session, product.product_id, debug=True)

    assert len(detail["major_coverages"]) == 1
    assert len(detail["raw_coverages"]) == 2
