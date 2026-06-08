from app.services.article_eligibility_filter_service import ArticleEligibilityFilterService
from app.services.product_name_validation_service import ProductNameValidationService


def test_product_error_patterns_are_rejected_or_excluded(db_session):
    name_service = ProductNameValidationService()
    article_service = ArticleEligibilityFilterService()

    assert name_service.validate("12일 사망보험").accepted is False
    assert name_service.validate("나아가 장기 보장성보험").accepted is False
    assert name_service.validate("월2000원대 보험").accepted is False
    assert name_service.validate("결합한보험").accepted is False

    service_decision = article_service.classify_text(
        db_session,
        "LG헬로비전, 시니어 통합 패키지 출시\n현대해상 보험 혜택을 일부 안내한다.",
    )
    assert service_decision.eligible_for_product_extraction is False
    assert service_decision.exclusion_reason == "subscription_service_article"

    food_decision = article_service.classify_text(
        db_session,
        "프리미엄 참기름 신제품 출시\n생산물배상책임보험에 가입했다.",
    )
    assert food_decision.eligible_for_product_extraction is False


def test_multi_financial_article_with_insurer_channel_is_excluded(db_session):
    decision = ArticleEligibilityFilterService().classify_text(
        db_session,
        "DB자산운용, AI 반도체 기업에 집중 투자하는 코스닥 펀드 출시\n"
        "삼성생명과 여러 증권사를 통해 가입할 수 있다.",
    )

    assert decision.eligible_for_product_extraction is False
    assert decision.exclusion_reason == "non_insurance_financial_product"
    assert "펀드" in decision.detected_non_insurance_products
