from __future__ import annotations

from app.db import repository


def test_low_priority_release_basis_does_not_overwrite_explicit_month(db_session):
    product = repository.upsert_product(
        db_session,
        {
            "raw_product_name": "명시월 상품",
            "normalized_product_name": "명시월 상품",
            "company_name": "삼성화재",
            "insurance_type": "손해보험",
            "release_year_month": "2026-02",
            "release_year_month_basis": "explicit_in_article",
            "primary_product_type_code": "OTHER",
            "needs_review": False,
        },
    )

    same = repository.upsert_product(
        db_session,
        {
            "raw_product_name": "명시월 상품",
            "normalized_product_name": "명시월 상품",
            "company_name": "삼성화재",
            "insurance_type": "손해보험",
            "release_year_month": "2026-01",
            "release_year_month_basis": "earliest_related_article_month",
            "primary_product_type_code": "OTHER",
            "needs_review": False,
        },
    )
    db_session.refresh(product)

    assert same.product_id == product.product_id
    assert product.release_year_month == "2026-02"
    assert product.release_year_month_basis == "explicit_in_article"
