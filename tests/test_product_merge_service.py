from sqlalchemy import text

from app.db.models import DimCompany, DimProduct, FactArticle, FactProductArticle
from app.services.product_canonicalization_service import ProductCanonicalizationService
from app.utils.hashing import sha256_text


def _company_id(db):
    company = db.query(DimCompany).filter(DimCompany.company_name_normalized == "삼성화재").first()
    assert company is not None
    return company.company_id


def _product(db, name: str, company_id: int) -> DimProduct:
    item = DimProduct(
        raw_product_name=name,
        normalized_product_name=name,
        product_search_key=f"{company_id}:{name}",
        product_core_key=name.replace(" ", ""),
        product_identity_key=f"company:{company_id}|product:{name.replace(' ', '')}",
        company_id=company_id,
        insurance_type="손해보험",
        release_year_month="2026-01",
        primary_product_type_code="CHILD_ADULT_CHILD",
        confidence_total=0.9,
        needs_review=False,
        product_status="active",
    )
    db.add(item)
    db.flush()
    item.canonical_product_id = item.product_id
    return item


def test_merge_same_article_products_marks_duplicate_and_keeps_alias(db_session):
    company_id = _company_id(db_session)
    canonical = _product(db_session, "키즈폰 전용 어린이 미니 보험", company_id)
    duplicate = _product(db_session, "미니 보험", company_id)
    article = FactArticle(
        source_api="naver",
        title="LG유플러스 키즈폰 고객 전용 미니 보험 출시",
        description="키즈폰 이용 고객인 어린이를 위한 미니 보험",
        url="https://example.com/kids",
        content_hash=sha256_text("merge-test"),
    )
    db_session.add(article)
    db_session.flush()
    db_session.add(FactProductArticle(product_id=canonical.product_id, article_id=article.article_id))
    db_session.add(FactProductArticle(product_id=duplicate.product_id, article_id=article.article_id))
    db_session.commit()

    decisions = ProductCanonicalizationService().merge_same_article_products(db_session, article.article_id)
    db_session.commit()

    assert len(decisions) == 1
    db_session.refresh(duplicate)
    assert duplicate.product_status == "merged"
    assert duplicate.merged_into_product_id == canonical.product_id
    aliases = db_session.execute(
        text("SELECT raw_product_name FROM dim_product_alias WHERE product_id = :product_id"),
        {"product_id": canonical.product_id},
    ).all()
    assert ("미니 보험",) in aliases
