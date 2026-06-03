from datetime import datetime

from app.db.models import FactArticle, FactLLMQueue
from app.services.exclusive_right_service import ExclusiveRightService


def test_exclusive_right_batch_mode_creates_batch_eligible_queue(db_session):
    article = FactArticle(
        source_api="naver",
        title="삼성화재 6개월 배타적사용권 획득",
        description="배타적사용권을 부여받았다.",
        url="https://example.com/exclusive-batch",
        original_url="https://example.com/exclusive-batch",
        pub_date=datetime(2026, 1, 12),
        content_hash="exclusive-batch",
    )
    db_session.add(article)
    db_session.commit()

    result = ExclusiveRightService().extract_pending(
        db_session,
        limit=10,
        mode="batch",
        date_from="2026-01-01",
        date_to="2026-01-31",
    )
    queue = db_session.query(FactLLMQueue).filter_by(task_type="exclusive_right_extract").one()

    assert result["queued"] == 1
    assert result["batch_eligible"] == 1
    assert queue.batch_eligible_yn is True
