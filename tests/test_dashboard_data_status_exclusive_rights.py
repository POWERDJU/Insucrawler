from datetime import datetime

from app.db.models import FactArticle, FactLLMQueue
from app.services.dashboard_service import DashboardService
from app.services.exclusive_right_service import ExclusiveRightService
from app.services.screening_service import ScreeningService


def test_dashboard_data_status_includes_exclusive_right_counts(db_session):
    article = FactArticle(
        source_api="naver",
        title="한화손해보험 배타적사용권 획득",
        description="한화손해보험은 OO보험에 6개월 배타적사용권을 획득했다.",
        url="https://example.com/status-exclusive",
        original_url="https://example.com/status-exclusive",
        pub_date=datetime(2026, 5, 1),
        content_hash="status-exclusive",
    )
    pending_article = FactArticle(
        source_api="naver",
        title="삼성화재 배타적사용권 획득",
        description="삼성화재가 6개월 배타적사용권을 획득했다.",
        url="https://example.com/status-pending-exclusive",
        original_url="https://example.com/status-pending-exclusive",
        pub_date=datetime(2026, 5, 2),
        content_hash="status-pending-exclusive",
    )
    db_session.add_all([article, pending_article])
    db_session.commit()
    ExclusiveRightService().create_from_text(db_session, article.description, article=article)
    ScreeningService().screen_article(db_session, pending_article)
    db_session.add(FactLLMQueue(target_type="article", target_id=pending_article.article_id, task_type="exclusive_right_extract", priority="high"))
    db_session.commit()

    status = DashboardService().data_status(db_session)

    assert status["exclusive_right_count"] == 1
    assert status["recent_exclusive_right_count_12m"] == 1
    assert status["pending_exclusive_right_extraction_count"] >= 1
    assert status["last_exclusive_right_acquired_year_month"] == "2026-05"
