from app.services.screening_service import ScreeningService


def test_exclusive_right_screening_scores_acquired_article_as_candidate():
    result = ScreeningService().screen_text(
        title="한화손해보험, 6개월 배타적사용권 획득",
        description="신상품심의위원회에서 새로운 위험 담보 독창성을 인정받았다.",
        source_type="naver",
    )

    assert result.exclusive_right_score >= 0.70
    assert result.exclusive_right_candidate_yn is True
    assert "배타적사용권" in (result.matched_exclusive_keywords or [])


def test_exclusive_right_screening_does_not_promote_planned_only_article():
    result = ScreeningService().screen_text(
        title="보험사가 배타적사용권 신청을 추진할 예정",
        description="아직 획득 또는 부여 사실은 없다.",
        source_type="naver",
    )

    assert result.exclusive_right_score < 0.70
    assert result.exclusive_right_candidate_yn is False
