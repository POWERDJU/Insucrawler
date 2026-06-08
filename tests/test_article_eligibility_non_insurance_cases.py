from app.db.models import FactArticle
from app.services.article_eligibility_filter_service import ArticleEligibilityFilterService
from app.utils.hashing import article_dedup_hash


def _article(title: str, description: str = "") -> FactArticle:
    return FactArticle(
        source_api="test",
        title=title,
        description=description,
        publisher="test",
        url=f"https://example.com/{abs(hash(title))}",
        original_url=f"https://example.com/{abs(hash(title))}",
        query="test",
        query_group="test",
        content_hash=article_dedup_hash(title, title, description),
        extraction_status="pending",
    )


def test_subscription_service_article_is_ineligible(db_session):
    article = _article(
        "KT, 가전 구독 시니어 통합 패키지 출시",
        "현대해상과 제휴한 보험 혜택이 일부 포함되지만 핵심은 KT 구독서비스다.",
    )
    db_session.add(article)
    db_session.commit()

    decision = ArticleEligibilityFilterService().classify_article(db_session, article)

    assert decision.eligible_for_product_extraction is False
    assert decision.exclusion_reason == "subscription_service_article"
    assert "구독서비스" in decision.detected_non_insurance_services


def test_sbs_golf_multiview_article_is_ineligible(db_session):
    article = _article(
        "SBS골프, 투어 경기 멀티뷰 서비스 출시",
        "KB손해보험 광고가 함께 송출되지만 보험상품 출시는 아니다.",
    )
    db_session.add(article)
    db_session.commit()

    decision = ArticleEligibilityFilterService().classify_article(db_session, article)

    assert decision.eligible_for_product_extraction is False
    assert decision.exclusion_reason == "sports_broadcast_service_article"


def test_campaign_only_article_is_ineligible_without_product_launch(db_session):
    article = _article(
        "한화손해보험, 신규 TV 광고 캠페인 공개",
        "배우 모델을 앞세워 브랜드 캠페인을 전개했다.",
    )
    db_session.add(article)
    db_session.commit()

    decision = ArticleEligibilityFilterService().classify_article(db_session, article)

    assert decision.eligible_for_product_extraction is False
    assert decision.exclusion_reason == "campaign_or_ad_only_article"
