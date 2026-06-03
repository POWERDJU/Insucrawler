from __future__ import annotations

import hashlib

from app.db.models import DimProduct, FactArticle, FactProductArticle, FactProductObservation
from app.services.product_blocking_service import ProductBlockingService


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _article(db, title: str, description: str, url: str) -> FactArticle:
    item = FactArticle(
        source_api="test",
        title=title,
        description=description,
        url=url,
        original_url=url,
        content_hash=_hash(url),
    )
    db.add(item)
    db.flush()
    return item


def _product(
    db,
    name: str,
    *,
    product_type: str | None = "CHILD_ADULT_CHILD",
    month: str = "2026-01",
    article: FactArticle | None = None,
) -> DimProduct:
    item = DimProduct(
        raw_product_name=name,
        normalized_product_name=name,
        product_search_key=f"unknown:{name}:{month}",
        product_core_key=name.replace(" ", "").casefold(),
        company_id=None,
        insurance_type="unknown",
        release_year_month=month,
        primary_product_type_code=product_type,
        confidence_total=0.82,
        needs_review=False,
        product_status="provisional",
    )
    db.add(item)
    db.flush()
    item.canonical_product_id = item.product_id
    if article:
        db.add(FactProductArticle(product_id=item.product_id, article_id=article.article_id, confidence_total=0.8))
    db.add(
        FactProductObservation(
            product_id=item.product_id,
            article_id=article.article_id if article else None,
            raw_product_name=name,
            normalized_product_name_candidate=name,
            product_core_key=item.product_core_key,
            product_type_code=product_type,
            release_year_month=month,
            article_title=article.title if article else None,
            article_description=article.description if article else None,
            source_url=article.original_url if article else None,
            observation_context_text=(article.description if article else "") + " " + name,
            candidate_type="descriptive_alias",
            confidence=0.8,
        )
    )
    db.flush()
    return item


def test_unknown_company_context_block_groups_multi_article_variants(db_session):
    first_article = _article(
        db_session,
        "LG유플러스 키즈폰 고객 대상 어린이 미니보험 출시",
        "키즈폰 이용 고객인 어린이를 위한 미니보험을 선보였다.",
        "https://example.test/kids-1",
    )
    second_article = _article(
        db_session,
        "키즈폰 고객 위한 어린이 용 미니보험 신상품",
        "어린이 특화 미니보험이 키즈폰 고객 대상으로 제공된다.",
        "https://example.test/kids-2",
    )
    products = [
        _product(db_session, "키즈폰 전용 어린이 미니보험", article=first_article),
        _product(db_session, "키즈폰 이용 고객인 어린이를 위한 미니보험", product_type="UNKNOWN", article=first_article),
        _product(db_session, "키즈폰 고객 위한 어린이 용 미니보험", product_type="OTHER", article=second_article),
        _product(db_session, "키즈폰 대상 미니보험", article=second_article),
    ]
    db_session.commit()

    blocks = ProductBlockingService().build_blocks(db_session, target="all", limit=50)
    product_ids = {product.product_id for product in products}

    assert any(product_ids.issubset(set(block.candidate_product_ids)) for block in blocks)


def test_partner_is_inferred_from_article_context_without_product_partner(db_session):
    article = _article(
        db_session,
        "LG유플러스 키즈폰 고객 대상 미니보험 출시",
        "LG 와 키즈폰 고객 위한 미니보험을 소개했다.",
        "https://example.test/lg-kids",
    )
    first = _product(db_session, "LG 키즈폰 어린이 특화 미니보험", product_type="UNKNOWN", article=article)
    second = _product(db_session, "키즈폰 미니보험", product_type="CHILD_ADULT_CHILD", article=article)
    db_session.commit()

    blocks = ProductBlockingService().build_blocks(db_session, target="all", limit=50)
    matched = [block for block in blocks if {first.product_id, second.product_id}.issubset(set(block.candidate_product_ids))]

    assert matched
    assert matched[0].partner_company_name in {"LG", "LG유플러스"}


def test_soft_product_type_compatibility_keeps_unknown_and_blocks_clear_conflict(db_session):
    service = ProductBlockingService()

    assert service.product_type_compatible_soft("CHILD_ADULT_CHILD", "UNKNOWN")
    assert service.product_type_compatible_soft("CHILD_ADULT_CHILD", "OTHER")
    assert service.product_type_compatible_soft("CHILD_ADULT_CHILD", "HEALTH_COMPREHENSIVE")
    assert not service.product_type_compatible_soft("AUTO", "DENTAL")
