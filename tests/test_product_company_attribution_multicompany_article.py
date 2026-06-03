from __future__ import annotations

from app.db import repository


def test_product_upsert_uses_local_product_window_company(db_session):
    product = repository.upsert_product(
        db_session,
        {
            "raw_product_name": "시그니처 여성 건강보험 4.0",
            "normalized_product_name": "시그니처 여성 건강보험 4.0",
            "company_name": "한화생명",
            "insurance_type": "손해보험",
            "context_text": "한화생명 소식도 함께 전했다. 한화손해보험은 시그니처 여성 건강보험 4.0을 출시했다.",
            "primary_product_type_code": "HEALTH_COMPREHENSIVE",
            "release_year_month": "2026-03",
            "confidence_total": 0.9,
            "needs_review": False,
        },
        allow_unknown_company=False,
    )

    assert product is not None
    company = db_session.get(repository.DimCompany, product.company_id)
    assert company.company_name_normalized == "한화손해보험"


def test_short_alias_product_company_is_not_forced(db_session):
    product = repository.upsert_product(
        db_session,
        {
            "raw_product_name": "건강보험",
            "normalized_product_name": "건강보험",
            "company_name": "삼성",
            "context_text": "삼성은 건강보험을 소개했다.",
            "primary_product_type_code": "HEALTH_COMPREHENSIVE",
            "release_year_month": "2026-01",
            "confidence_total": 0.7,
            "needs_review": False,
        },
        allow_unknown_company=False,
    )

    assert product is None
