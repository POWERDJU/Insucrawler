from __future__ import annotations

from datetime import datetime

from app.db.models import DimProduct, FactArticle, FactProductArticle, FactProductMajorCoverage, FactProductNarrativeInsight, FactProductTypeAssignment
from app.db.repository import link_product_article
from app.services.ingestion_service import IngestionService
from app.services.monthly_new_product_service import MonthlyNewProductService
from app.utils.hashing import article_dedup_hash


def seed_monthly_product(
    db,
    *,
    name: str = "월간 테스트 건강보험",
    company_name: str = "삼성생명",
    insurance_type: str = "생명보험",
    release_year_month: str = "2026-05",
    needs_review: bool = False,
    narrative: dict | None = None,
    article_title: str = "삼성생명, 월간 테스트 건강보험 출시",
    article_description: str = "월간 테스트 건강보험을 신규 출시했다.",
    article_pub_date: str = "2026-05-10T09:00:00",
    article_url: str | None = None,
    source_article: bool = False,
):
    product = IngestionService().upsert_structured_product(
        db,
        {
            "product": {
                "raw_product_name": name,
                "normalized_product_name": name,
                "company_name": company_name,
                "insurance_type": insurance_type,
                "release_year_month": release_year_month,
                "release_year_month_basis": "explicit_in_article",
                "primary_product_type_code": "HEALTH_COMPREHENSIVE",
                "confidence_total": 0.88,
                "needs_review": needs_review,
            },
            "product_type_assignments": [
                {"product_type_code": "HEALTH_COMPREHENSIVE", "assignment_role": "primary", "confidence": 0.9},
            ],
            "narrative_insights": {
                "product_development_summary": "건강 보장 수요를 반영한 이달의 신상품입니다.",
                "feature_summary": "건강 보장을 간략히 제공하는 상품입니다.",
                "coverage_summary": "진단과 수술 보장을 중심으로 구성했습니다.",
            }
            if narrative is None
            else narrative,
            "major_coverages": [
                {"coverage_name_raw": "질병진단비", "risk_area": "질병", "benefit_type": "진단", "coverage_summary": "질병 진단 보장"},
            ],
        },
        create_manual_record=False,
    )
    resolved_url = article_url or f"https://example.com/monthly-product/{product.product_id}"
    article = FactArticle(
        source_api="test",
        title=article_title,
        description=article_description,
        publisher="Test News",
        url=resolved_url,
        original_url=resolved_url,
        pub_date=datetime.fromisoformat(article_pub_date),
        query="test",
        query_group="test",
        content_hash=article_dedup_hash(resolved_url, article_title, ""),
        extraction_status="extracted",
    )
    db.add(article)
    db.flush()
    link_product_article(db, product.product_id, article.article_id, confidence_total=0.9, needs_review=needs_review)
    if source_article:
        product.release_year_month_source_article_id = article.article_id
    db.commit()
    return product, article


def test_monthly_new_products_returns_current_month_items(db_session):
    product, article = seed_monthly_product(db_session, article_url="https://example.com/monthly-product")

    result = MonthlyNewProductService().get_monthly_new_products(db_session, year_month="2026-05")

    assert result["year_month"] == "2026-05"
    assert result["fallback_used"] is False
    assert result["items"][0]["product_id"] == product.product_id
    assert result["items"][0]["product_name"] == "월간 테스트 건강보험"
    assert result["items"][0]["company_name"] == "삼성생명"
    assert result["items"][0]["primary_product_type"] == "건강(종합)"
    assert result["items"][0]["summary"] == "건강 보장 수요를 반영한 이달의 신상품입니다."
    assert result["items"][0]["article_url"] == article.original_url


def test_monthly_new_products_fallback_latest(db_session):
    seed_monthly_product(db_session, release_year_month="2026-04")

    result = MonthlyNewProductService().get_monthly_new_products(db_session, year_month="2026-05", fallback_latest=True)

    assert result["year_month"] == "2026-04"
    assert result["display_year_month"] == "2026년 4월"
    assert result["fallback_used"] is True
    assert len(result["items"]) == 1


def test_monthly_new_products_excludes_review_when_requested(db_session):
    seed_monthly_product(db_session, needs_review=True)

    result = MonthlyNewProductService().get_monthly_new_products(db_session, year_month="2026-05", include_review=False, fallback_latest=False)

    assert result["items"] == []


def test_monthly_new_products_excludes_rider_products(db_session):
    seed_monthly_product(db_session, name="월간 테스트 건강보험", article_url="https://example.com/monthly-main")
    seed_monthly_product(db_session, name="입원일당 특약", article_url="https://example.com/monthly-rider")

    result = MonthlyNewProductService().get_monthly_new_products(db_session, year_month="2026-05")

    names = {item["product_name"] for item in result["items"]}
    assert "월간 테스트 건강보험" in names
    assert "입원일당 특약" not in names


def test_monthly_new_products_filters_insurance_type(db_session):
    seed_monthly_product(db_session, name="생보 건강보험", company_name="삼성생명", insurance_type="생명보험")
    seed_monthly_product(db_session, name="손보 건강보험", company_name="삼성화재", insurance_type="손해보험")

    result = MonthlyNewProductService().get_monthly_new_products(db_session, year_month="2026-05", insurance_type="손해보험")

    assert [item["company_name"] for item in result["items"]] == ["삼성화재"]


def test_monthly_new_products_prefers_release_source_article(db_session):
    product, older_article = seed_monthly_product(
        db_session,
        article_title="월간 테스트 건강보험 관련 안내",
        article_description="상품 안내 기사",
        article_pub_date="2026-05-01T09:00:00",
        article_url="https://example.com/monthly-old",
    )
    source_article = FactArticle(
        source_api="test",
        title="삼성생명, 월간 테스트 건강보험 출시",
        description="대표 출시 기사",
        publisher="Test News",
        url="https://example.com/monthly-source",
        original_url="https://example.com/monthly-source",
        pub_date=datetime.fromisoformat("2026-05-12T09:00:00"),
        query="test",
        query_group="test",
        content_hash=article_dedup_hash("https://example.com/monthly-source", "삼성생명, 월간 테스트 건강보험 출시", ""),
        extraction_status="extracted",
    )
    db_session.add(source_article)
    db_session.flush()
    link_product_article(db_session, product.product_id, source_article.article_id, confidence_total=0.9, needs_review=False)
    product.release_year_month_source_article_id = source_article.article_id
    db_session.commit()

    result = MonthlyNewProductService().get_monthly_new_products(db_session, year_month="2026-05")

    assert older_article.article_id != source_article.article_id
    assert result["items"][0]["article_url"] == "https://example.com/monthly-source"


def test_monthly_new_products_summary_fallback_order(db_session):
    seed_monthly_product(
        db_session,
        narrative={"feature_summary": "feature summary", "coverage_summary": "coverage summary"},
        article_description="article description",
        article_title="article title",
    )
    result = MonthlyNewProductService().get_monthly_new_products(db_session, year_month="2026-05")
    assert result["items"][0]["summary"] == "feature summary"

    db_session.query(FactProductArticle).delete()
    db_session.query(FactProductMajorCoverage).delete()
    db_session.query(FactProductNarrativeInsight).delete()
    db_session.query(FactProductTypeAssignment).delete()
    db_session.query(DimProduct).delete()
    db_session.commit()
    seed_monthly_product(
        db_session,
        name="월간 테스트 건강보험 2",
        narrative={},
        article_description="article description",
        article_title="article title",
        article_url="https://example.com/monthly-product-2",
    )
    result = MonthlyNewProductService().get_monthly_new_products(db_session, year_month="2026-05")
    assert result["items"][0]["summary"] == "article description"
