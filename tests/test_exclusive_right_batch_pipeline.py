from __future__ import annotations

import json
from datetime import datetime

from app.db.models import FactArticle, FactExclusiveUseRight, FactLLMQueue
from app.services.batch_llm_service import BatchLLMService
from app.services.exclusive_right_service import ExclusiveRightService


def _article(db_session, idx: int, title: str | None = None) -> FactArticle:
    article = FactArticle(
        source_api="naver",
        title=title or f"한화손해보험 {idx} 6개월 배타적사용권 획득",
        description="한화손해보험은 신상품심의위원회에서 새로운 위험 담보 독창성을 인정받아 배타적사용권을 획득했다.",
        url=f"https://example.com/exclusive-pipeline-{idx}",
        original_url=f"https://example.com/exclusive-pipeline-{idx}",
        pub_date=datetime(2026, 1, idx + 1),
        content_hash=f"exclusive-pipeline-{idx}",
    )
    db_session.add(article)
    db_session.commit()
    return article


def test_exclusive_right_enqueue_only_creates_queue_without_provider_or_canonical(db_session):
    for idx in range(3):
        _article(db_session, idx)

    result = ExclusiveRightService().extract_pending(
        db_session,
        limit=10,
        mode="enqueue_only",
        date_from="2026-01-01",
        date_to="2026-01-31",
    )

    queues = db_session.query(FactLLMQueue).filter_by(task_type="exclusive_right_extract").all()
    assert result["queued_count"] == 3
    assert len(queues) == 3
    assert {queue.batch_eligible_yn for queue in queues} == {False}
    assert db_session.query(FactExclusiveUseRight).count() == 0


def test_exclusive_right_batch_mode_and_jsonl_use_snippet_bundle(db_session, tmp_path):
    _article(db_session, 1)
    ExclusiveRightService().extract_pending(
        db_session,
        limit=10,
        mode="batch",
        date_from="2026-01-01",
        date_to="2026-01-31",
    )

    job = BatchLLMService().create_from_pending_queue(
        db_session,
        task_type="exclusive_right_extract",
        provider="gemini",
        model_name="gemini-2.5-flash",
        limit=10,
        submit=False,
        output_dir=tmp_path,
    )
    with open(job.input_file_path, encoding="utf-8") as f:
        line = json.loads(f.readline())
    request_text = line["request"]["contents"][0]["parts"][0]["text"]

    assert job.request_count == 1
    assert line["custom_id"].startswith("exclusive_right_extract:queue:")
    assert ":article:" in line["custom_id"]
    assert "exclusive_right" in request_text
    assert "snippets" in request_text
    assert "full_text" not in request_text
