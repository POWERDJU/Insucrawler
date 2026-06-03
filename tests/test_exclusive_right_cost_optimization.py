from __future__ import annotations

from datetime import datetime

from app.db.models import FactArticle, FactLLMQueue
from app.services.exclusive_right_service import ExclusiveRightService
from app.services.screening_service import ScreeningService


def test_non_exclusive_article_gets_no_exclusive_right_queue(db_session):
    article = FactArticle(
        source_api="naver",
        title="한화손해보험 건강보험 신상품 출시",
        description="한화손해보험이 건강보험 신상품을 출시했다.",
        url="https://example.com/non-exclusive",
        original_url="https://example.com/non-exclusive",
        pub_date=datetime(2026, 1, 14),
        content_hash="non-exclusive",
    )
    db_session.add(article)
    db_session.commit()

    ScreeningService().screen_article(db_session, article)
    result = ExclusiveRightService().extract_pending(
        db_session,
        limit=10,
        mode="batch",
        date_from="2026-01-01",
        date_to="2026-01-31",
    )

    assert result["candidate_count"] == 0
    assert db_session.query(FactLLMQueue).filter_by(task_type="exclusive_right_extract").count() == 0


def test_screening_only_mode_does_not_enqueue(db_session):
    article = FactArticle(
        source_api="naver",
        title="한화손해보험 6개월 배타적사용권 획득",
        description="한화손해보험은 신상품심의위원회에서 새로운 위험 담보 배타적사용권을 획득했다.",
        url="https://example.com/screening-only",
        original_url="https://example.com/screening-only",
        pub_date=datetime(2026, 1, 15),
        content_hash="screening-only",
    )
    db_session.add(article)
    db_session.commit()

    result = ExclusiveRightService().extract_pending(
        db_session,
        limit=10,
        mode="screening_only",
        date_from="2026-01-01",
        date_to="2026-01-31",
    )

    assert result["candidate_count"] == 1
    assert result["queued_count"] == 0
    assert db_session.query(FactLLMQueue).filter_by(task_type="exclusive_right_extract").count() == 0

