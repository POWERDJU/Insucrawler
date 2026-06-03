from __future__ import annotations

from datetime import datetime

from app.db.models import FactArticle, FactLLMQueue
from app.services.exclusive_right_service import ExclusiveRightService


def _article(db_session, hash_value: str = "exclusive-dedup") -> FactArticle:
    article = FactArticle(
        source_api="naver",
        title="한화손해보험 6개월 배타적사용권 획득",
        description="한화손해보험은 신상품심의위원회에서 배타적사용권을 획득했다.",
        url=f"https://example.com/{hash_value}",
        original_url=f"https://example.com/{hash_value}",
        pub_date=datetime(2026, 1, 13),
        content_hash=hash_value,
    )
    db_session.add(article)
    db_session.commit()
    return article


def test_completed_exclusive_right_queue_prevents_duplicate_enqueue(db_session):
    article = _article(db_session)
    result = ExclusiveRightService().extract_pending(
        db_session,
        limit=10,
        mode="batch",
        date_from="2026-01-01",
        date_to="2026-01-31",
    )
    assert result["queued_count"] == 1
    queue = db_session.query(FactLLMQueue).one()
    queue.status = "completed"
    db_session.commit()

    second = ExclusiveRightService().extract_pending(
        db_session,
        limit=10,
        mode="batch",
        date_from="2026-01-01",
        date_to="2026-01-31",
    )

    assert second["queued_count"] == 0
    assert db_session.query(FactLLMQueue).count() == 1


def test_exclusive_right_queue_status_counts_candidates_and_queues(db_session):
    _article(db_session, "exclusive-status")
    ExclusiveRightService().extract_pending(
        db_session,
        limit=10,
        mode="batch",
        date_from="2026-01-01",
        date_to="2026-01-31",
    )

    status = ExclusiveRightService().queue_status(db_session, date_from="2026-01-01", date_to="2026-01-31")

    assert status["exclusive_right_candidate_count"] == 1
    assert status["queued_pending_count"] == 1
    assert status["queued_batch_eligible_count"] == 1

