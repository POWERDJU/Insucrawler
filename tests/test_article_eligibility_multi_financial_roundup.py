from app.services.article_eligibility_filter_service import ArticleEligibilityFilterService


def test_multi_financial_roundup_article_is_ineligible(db_session):
    text = """
    [금융] IBK기업은행 KOSPI200 지수연동예금 출시 / 한화손보 야구장 스폰서데이 /
    하나금융 지역아동 문화체험 / NH농협은행 에너지 절약 캠페인
    IBK기업은행은 KOSPI200 지수연동예금을 출시했다.
    한화손해보험은 야구장 스폰서데이를 진행했다.
    """

    decision = ArticleEligibilityFilterService().classify_text(db_session, text)

    assert decision.eligible_for_product_extraction is False
    assert decision.eligible_for_exclusive_right_extraction is False
    assert decision.exclusion_reason == "multi_financial_institution_roundup"
    assert "KOSPI200 지수연동예금" in decision.detected_non_insurance_products


def test_single_insurer_bank_channel_context_is_not_auto_excluded(db_session):
    text = "삼성생명은 우리은행과 제휴해 치매보험 상품을 은행 창구에서 판매한다고 밝혔다."

    decision = ArticleEligibilityFilterService().classify_text(db_session, text)

    assert decision.eligible_for_product_extraction is True
