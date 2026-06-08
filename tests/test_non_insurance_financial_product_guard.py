import pytest

from app.db import repository
from app.db.models import FactArticle
from app.services.article_eligibility_filter_service import ArticleEligibilityFilterService
from app.services.article_eligibility_filter_service import (
    is_non_insurance_financial_product_name,
    is_non_insurance_general_product_name,
)
from app.services.ingestion_service import IngestionService
from app.utils.hashing import article_dedup_hash


def test_non_insurance_financial_product_name_guard():
    assert is_non_insurance_financial_product_name("KOSPI200 지수연동예금") is True
    assert is_non_insurance_financial_product_name("코스닥메가트렌드목표전환형 2호") is True
    assert is_non_insurance_financial_product_name("든든한 암보험") is False


def test_non_insurance_general_product_name_guard():
    assert is_non_insurance_general_product_name("큐로세틴 젤리") is True
    assert is_non_insurance_general_product_name("한국형 AI SOTA K") is True
    assert is_non_insurance_general_product_name("AI 암보험") is False


def test_non_insurance_financial_product_is_not_saved_as_insurance_product(db_session):
    product = repository.upsert_product(
        db_session,
        {
            "raw_product_name": "KOSPI200 지수연동예금",
            "normalized_product_name": "KOSPI200 지수연동예금",
            "company_name": "한화손해보험",
            "insurance_type": "손해보험",
            "primary_product_type_code": "OTHER",
            "confidence_total": 0.9,
            "needs_review": False,
        },
        allow_unknown_company=False,
    )

    assert product is None


def test_asset_manager_kosdaq_fund_article_is_ineligible_even_with_insurer_sales_channel(db_session):
    title = "DB자산운용, AI 반도체 기업에 집중 투자하는 코스닥 펀드 출시"
    description = (
        "한국투자증권, 대신증권, 교보증권, 한양증권, 삼성생명, DB증권, KB증권, "
        "IBK증권 등을 통해 가입할 수 있다."
    )
    article = FactArticle(
        source_api="test",
        title=title,
        description=description,
        publisher="test",
        url="https://example.com/kosdaq-fund",
        original_url="https://example.com/kosdaq-fund",
        query="test",
        query_group="test",
        content_hash=article_dedup_hash("https://example.com/kosdaq-fund", title, ""),
        extraction_status="pending",
    )
    db_session.add(article)
    db_session.commit()

    decision = ArticleEligibilityFilterService().classify_article(db_session, article)

    assert decision.eligible_for_product_extraction is False
    assert decision.eligible_for_exclusive_right_extraction is False
    assert decision.exclusion_reason == "non_insurance_financial_product"
    assert "삼성생명" in decision.detected_insurer_companies
    assert "자산운용" in decision.detected_non_insurance_financial_institutions
    assert "펀드" in decision.detected_non_insurance_products


def test_health_food_article_with_product_liability_insurance_is_ineligible(db_session):
    title = "나프라우드, 약사 공동개발 '큐로세틴 젤리' 출시"
    description = (
        "건강기능식품 브랜드 나프라우드가 약사와 공동개발한 신제품을 공식 출시했다. "
        "KB손해보험 생산물배상책임 보험에 가입했다."
    )
    article = FactArticle(
        source_api="test",
        title=title,
        description=description,
        publisher="test",
        url="https://example.com/quercetin-jelly",
        original_url="https://example.com/quercetin-jelly",
        query="test",
        query_group="test",
        content_hash=article_dedup_hash("https://example.com/quercetin-jelly", title, ""),
        extraction_status="pending",
    )
    db_session.add(article)
    db_session.commit()

    decision = ArticleEligibilityFilterService().classify_article(db_session, article)

    assert decision.eligible_for_product_extraction is False
    assert decision.exclusion_reason == "non_insurance_product_article"
    assert "젤리" in decision.detected_non_insurance_products


def test_ai_service_article_with_insurer_validation_customer_is_ineligible(db_session):
    title = "KT, 한국형 AI 'SOTA K' 출시 …GPT-4o에 한국어·문화 결합"
    description = "메리츠화재, EBS, 연세의료원, 한국전력공사 등 다양한 분야에서 현장 검증을 마쳤다."
    article = FactArticle(
        source_api="test",
        title=title,
        description=description,
        publisher="test",
        url="https://example.com/sota-k",
        original_url="https://example.com/sota-k",
        query="test",
        query_group="test",
        content_hash=article_dedup_hash("https://example.com/sota-k", title, ""),
        extraction_status="pending",
    )
    db_session.add(article)
    db_session.commit()

    decision = ArticleEligibilityFilterService().classify_article(db_session, article)

    assert decision.eligible_for_product_extraction is False
    assert decision.exclusion_reason == "non_insurance_product_article"
    assert "SOTA" in decision.detected_non_insurance_products


def test_industry_trend_product_roundup_article_is_ineligible(db_session):
    title = "자본 전략을 넘어 상품 설계로… 보험사는 '자본 효율형 신상품'에 집중한다"
    description = "NH농협생명은 장기 요양 보험에 간병인 보장을 결합한 신상품을 내놓았다."
    article = FactArticle(
        source_api="test",
        title=title,
        description=description,
        publisher="test",
        url="https://example.com/industry-trend",
        original_url="https://example.com/industry-trend",
        query="test",
        query_group="test",
        content_hash=article_dedup_hash("https://example.com/industry-trend", title, ""),
        extraction_status="pending",
    )
    db_session.add(article)
    db_session.commit()

    decision = ArticleEligibilityFilterService().classify_article(db_session, article)

    assert decision.eligible_for_product_extraction is False
    assert decision.exclusion_reason == "industry_trend_multi_company_article"


def test_credit_life_insurance_article_is_not_excluded_as_loan_product(db_session):
    title = "교보라이프플래닛, 빚 대물림 막는 대출안심 보험 시판"
    description = "신용 생명보험이 출시됐으며 사망시 보험금으로 대출 상환을 지원한다."
    article = FactArticle(
        source_api="test",
        title=title,
        description=description,
        publisher="test",
        url="https://example.com/credit-life",
        original_url="https://example.com/credit-life",
        query="test",
        query_group="test",
        content_hash=article_dedup_hash("https://example.com/credit-life", title, ""),
        extraction_status="pending",
    )
    db_session.add(article)
    db_session.commit()

    decision = ArticleEligibilityFilterService().classify_article(db_session, article)

    assert decision.eligible_for_product_extraction is True
