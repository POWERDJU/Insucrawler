from datetime import datetime

from app.db import repository
from app.db.models import FactArticle
from app.utils.hashing import sha256_text


def add_article(db_session, article_id_suffix: str, pub_date: datetime) -> FactArticle:
    article = FactArticle(
        source_api="unit",
        title=f"article {article_id_suffix}",
        description="release month test",
        url=f"https://example.test/{article_id_suffix}",
        content_hash=sha256_text(f"https://example.test/{article_id_suffix}"),
        pub_date=pub_date,
        extraction_status="extracted",
    )
    db_session.add(article)
    db_session.flush()
    return article


def test_unknown_release_month_uses_earliest_related_article_month(db_session):
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
        },
    )
    articles = [
        add_article(db_session, "feb", datetime(2026, 2, 10)),
        add_article(db_session, "jan", datetime(2026, 1, 15)),
        add_article(db_session, "mar", datetime(2026, 3, 1)),
    ]
    for article in articles:
        repository.link_product_article(db_session, product.product_id, article.article_id)
    db_session.refresh(product)

    assert product.release_year_month == "2026-01"
    assert product.release_year_month_basis == "earliest_related_article_month"
    assert product.release_year_month_source_article_id == articles[1].article_id


def test_explicit_release_month_is_not_overwritten(db_session):
    product = repository.upsert_product(
        db_session,
        {
            "raw_product_name": "명시 출시월 상품",
            "normalized_product_name": "명시 출시월 상품",
            "company_name": "삼성화재",
            "insurance_type": "손해보험",
            "release_year_month": "2026-02",
            "release_year_month_basis": "explicit_in_article",
            "primary_product_type_code": "OTHER",
        },
    )
    article = add_article(db_session, "older", datetime(2026, 1, 5))
    repository.link_product_article(db_session, product.product_id, article.article_id)
    db_session.refresh(product)

    assert product.release_year_month == "2026-02"
    assert product.release_year_month_basis == "explicit_in_article"


def test_inferred_release_month_moves_earlier_when_older_article_arrives(db_session):
    product = repository.upsert_product(
        db_session,
        {
            "raw_product_name": "기사 최초월 상품",
            "normalized_product_name": "기사 최초월 상품",
            "company_name": "삼성화재",
            "insurance_type": "손해보험",
            "release_year_month": "2026-02",
            "release_year_month_basis": "earliest_related_article_month",
            "primary_product_type_code": "OTHER",
        },
    )
    old_article = add_article(db_session, "older-again", datetime(2026, 1, 5))
    repository.link_product_article(db_session, product.product_id, old_article.article_id)
    db_session.refresh(product)

    assert product.release_year_month == "2026-01"
    assert product.release_year_month_source_article_id == old_article.article_id
