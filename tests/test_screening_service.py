from app.services.screening_service import ScreeningService


def test_screening_high_for_product_launch_article():
    result = ScreeningService().screen_text(
        title="삼성화재, 건강보험 신상품 출시",
        description="암 진단비와 수술비를 보장하는 건강보험을 선보였다.",
        source_type="naver",
    )

    assert result.rule_relevance_score >= 0.7
    assert result.llm_priority == "high"
    assert result.llm_required_yn is True


def test_screening_low_for_hr_and_social_article():
    result = ScreeningService().screen_text(
        title="삼성화재 임원 인사와 사회공헌 캠페인 진행",
        description="보험 상품 출시와 무관한 봉사활동 소식이다.",
        source_type="naver",
    )

    assert result.rule_relevance_score < 0.4
    assert result.llm_priority in {"low", "skip"}


def test_screening_skips_unrelated_blog():
    result = ScreeningService().screen_text(
        title="주말 여행 후기",
        description="맛집과 카페를 소개하는 일반 블로그 글",
        source_type="blog",
    )

    assert result.llm_priority == "skip"
    assert result.llm_required_yn is False
