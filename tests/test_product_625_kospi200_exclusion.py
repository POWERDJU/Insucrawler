from datetime import datetime

from app.db.models import FactArticle
from app.services.article_eligibility_filter_service import ArticleEligibilityFilterService
from app.services.extract_service import ExtractService
from app.utils.hashing import article_dedup_hash


def test_kospi200_roundup_article_does_not_create_extraction_queue(db_session):
    title = "[금융] IBK기업은행 KOSPI200 지수연동예금 출시 / 한화손보 야구장 스폰서데이 / 하나금융 지역아동 문화체험 / NH농협은행 에너지 절약 캠페인"
    url = "https://www.webeconomy.co.kr/news/articleView.html?idxno=2182240"
    article = FactArticle(
        source_api="test",
        title=title,
        description="IBK기업은행은 KOSPI200 지수연동예금을 출시했다. 한화손해보험은 야구장 스폰서데이를 진행했다.",
        publisher="Web Economy",
        url=url,
        original_url=url,
        pub_date=datetime(2026, 1, 3, 9, 0, 0),
        query="test",
        query_group="test",
        content_hash=article_dedup_hash(url, title, ""),
        extraction_status="pending",
    )
    db_session.add(article)
    db_session.commit()

    result = ExtractService().enqueue_article_extraction(db_session, article.article_id, force_batch_eligible=True)

    assert result["status"] == "excluded_article_eligibility"
    assert result["llm_queue_id"] is None
    assert article.extraction_exclusion_reason == "multi_financial_institution_roundup"
    decision = ArticleEligibilityFilterService().classify_article(db_session, article)
    assert "KOSPI200 지수연동예금" in decision.detected_non_insurance_products
