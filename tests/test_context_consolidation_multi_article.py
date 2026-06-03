from __future__ import annotations

import hashlib

from app.db.models import DimCompany, DimProduct, FactArticle, FactProductArticle, FactProductMergeDecision, FactProductObservation
from app.services.product_consolidation_service import ProductConsolidationService


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
    company_id: int | None = None,
    product_type: str | None = "CHILD_ADULT_CHILD",
    month: str = "2026-01",
    article: FactArticle | None = None,
    candidate_type: str = "descriptive_alias",
) -> DimProduct:
    item = DimProduct(
        raw_product_name=name,
        normalized_product_name=name,
        product_search_key=f"{company_id or 'unknown'}:{name}:{month}",
        product_core_key=name.replace(" ", "").casefold(),
        company_id=company_id,
        insurance_type="unknown",
        release_year_month=month,
        primary_product_type_code=product_type,
        confidence_total=0.84,
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
            company_id=company_id,
            product_type_code=product_type,
            release_year_month=month,
            article_title=article.title if article else None,
            article_description=article.description if article else None,
            source_url=article.original_url if article else None,
            observation_context_text=(article.description if article else "") + " " + name,
            candidate_type=candidate_type,
            confidence=0.8,
        )
    )
    db.flush()
    return item


def _company(db, name: str) -> DimCompany:
    item = DimCompany(company_name_normalized=name, insurance_type="손해보험", include_in_product_news_default="Y")
    db.add(item)
    db.flush()
    return item


def test_rule_only_context_consolidation_merges_unknown_company_variants(db_session):
    first_article = _article(
        db_session,
        "LG유플러스 키즈폰 고객 대상 어린이 미니보험 출시",
        "키즈폰 전용 어린이 미니보험은 키즈폰 고객의 생활 위험을 보장한다.",
        "https://example.test/context-merge-1",
    )
    second_article = _article(
        db_session,
        "키즈폰 고객 전용 미니보험 신상품",
        "키즈폰 대상 미니보험과 어린이 특화 미니보험을 소개했다.",
        "https://example.test/context-merge-2",
    )
    canonical = _product(db_session, "키즈폰 전용 어린이 미니보험", article=first_article)
    duplicate = _product(db_session, "키즈폰 이용 고객인 어린이를 위한 미니보험", product_type="UNKNOWN", article=first_article)
    weak = _product(db_session, "키즈폰 대상 미니보험", product_type="OTHER", article=second_article, candidate_type="weak_mention")
    db_session.commit()

    result = ProductConsolidationService().run(db_session, mode="rule_only_apply", target="all", limit=0)
    db_session.refresh(canonical)
    db_session.refresh(duplicate)
    db_session.refresh(weak)

    assert result["auto_merge_count"] >= 2
    statuses = {canonical.product_status, duplicate.product_status, weak.product_status}
    assert statuses == {"active", "merged"}
    assert sum(product.product_status == "active" for product in [canonical, duplicate, weak]) == 1
    sources = {row.decision_source for row in db_session.query(FactProductMergeDecision).all()}
    assert sources.intersection(
        {
            "deterministic_context_high_similarity",
            "deterministic_context_containment",
            "deterministic_weak_mention_alias",
            "deterministic_unknown_partner_context",
        }
    )


def test_known_company_conflict_prevents_context_auto_merge(db_session):
    first_company = _company(db_session, "삼성화재")
    second_company = _company(db_session, "현대해상")
    article = _article(
        db_session,
        "같은 이름 건강보험 출시",
        "유사한 건강보험 명칭이지만 보험회사가 다르다.",
        "https://example.test/company-conflict",
    )
    first = _product(db_session, "간편 건강보험", company_id=first_company.company_id, product_type="HEALTH_COMPREHENSIVE", article=article)
    second = _product(db_session, "간편 건강보험", company_id=second_company.company_id, product_type="HEALTH_COMPREHENSIVE", article=article)
    db_session.commit()

    ProductConsolidationService().run(db_session, mode="rule_only_apply", target="all", limit=0)
    db_session.refresh(first)
    db_session.refresh(second)

    assert first.product_status != "merged"
    assert second.product_status != "merged"


def test_all_pages_consolidation_does_not_miss_far_apart_product_ids(db_session):
    article = _article(
        db_session,
        "LG유플러스 키즈폰 고객 대상 미니보험 출시",
        "키즈폰 고객에게 어린이 미니보험을 제공한다.",
        "https://example.test/all-pages-context",
    )
    first = _product(db_session, "키즈폰 전용 어린이 미니보험", article=article)
    for index in range(505):
        _product(db_session, f"무관 테스트 상품 {index}", product_type="AUTO", month="2025-01")
    second = _product(db_session, "키즈폰 고객 전용 미니보험", product_type="UNKNOWN", article=article)
    db_session.commit()

    limited = ProductConsolidationService().run(db_session, mode="dry_run", target="all", limit=500)
    assert not any({first.product_id, second.product_id}.issubset(set(block["candidate_product_ids"])) for block in limited["blocks"])

    ProductConsolidationService().run(db_session, mode="rule_only_apply", target="all", limit=0)
    db_session.refresh(first)
    db_session.refresh(second)

    assert second.product_status == "merged"
    assert second.merged_into_product_id == first.product_id
