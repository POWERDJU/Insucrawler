from __future__ import annotations

from datetime import datetime

from app.db import repository
from app.db.models import FactArticle
from app.utils.hashing import sha256_text


def _article(db_session, slug: str, title: str, pub_date: datetime, description: str = "") -> FactArticle:
    article = FactArticle(
        source_api="unit",
        title=title,
        description=description,
        url=f"https://example.test/{slug}",
        content_hash=sha256_text(f"https://example.test/{slug}"),
        pub_date=pub_date,
        extraction_status="extracted",
    )
    db_session.add(article)
    db_session.flush()
    return article


def test_release_month_ignores_other_version_and_followup_articles(db_session):
    product = repository.upsert_product(
        db_session,
        {
            "raw_product_name": "시그니처 여성건강보험 4.0",
            "normalized_product_name": "시그니처 여성건강보험 4.0",
            "company_name": "한화손해보험",
            "insurance_type": "손해보험",
            "release_year_month": None,
            "release_year_month_basis": "unknown",
            "primary_product_type_code": "HEALTH_COMPREHENSIVE",
            "needs_review": False,
        },
    )
    other_version = _article(
        db_session,
        "sig-3",
        "한화손해보험, 시그니처 여성건강보험 3.0 출시",
        datetime(2025, 10, 7),
    )
    followup = _article(
        db_session,
        "sig-followup",
        "한화손해보험 시그니처 여성건강보험 판매실적 공개",
        datetime(2026, 3, 3),
    )
    launch = _article(
        db_session,
        "sig-4",
        "한화손해보험, 시그니처 여성건강보험 4.0 출시",
        datetime(2026, 4, 2),
    )
    for article in [other_version, followup, launch]:
        repository.link_product_article(db_session, product.product_id, article.article_id)
    db_session.refresh(product)

    assert product.release_year_month == "2026-04"
    assert product.release_year_month_source_article_id == launch.article_id


def test_release_month_uses_earliest_direct_launch_article_for_same_product(db_session):
    product = repository.upsert_product(
        db_session,
        {
            "raw_product_name": "테스트 케어보험",
            "normalized_product_name": "테스트 케어보험",
            "company_name": "삼성화재",
            "insurance_type": "손해보험",
            "release_year_month": None,
            "release_year_month_basis": "unknown",
            "primary_product_type_code": "OTHER",
            "needs_review": False,
        },
    )
    launch = _article(db_session, "care-launch", "삼성화재, 테스트 케어보험 신규 출시", datetime(2026, 1, 5))
    later = _article(db_session, "care-later", "삼성화재 테스트 케어보험 보장 확대", datetime(2026, 2, 10))
    for article in [later, launch]:
        repository.link_product_article(db_session, product.product_id, article.article_id)
    db_session.refresh(product)

    assert product.release_year_month == "2026-01"
    assert product.release_year_month_source_article_id == launch.article_id
