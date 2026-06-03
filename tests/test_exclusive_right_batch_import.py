from __future__ import annotations

import json
from datetime import datetime

from app.db.models import (
    FactArticle,
    FactExclusiveUseRight,
    FactExclusiveUseRightAlias,
    FactExclusiveUseRightArticle,
    FactExclusiveUseRightObservation,
    FactLLMCostLog,
    FactLLMQueue,
    FactLLMRun,
)
from app.services.batch_llm_service import BatchLLMService
from app.services.exclusive_right_service import ExclusiveRightService


def _exclusive_payload(status: str = "acquired") -> dict:
    return {
        "exclusive_right_relevance": {"is_relevant": True, "status": status, "reason": "batch test"},
        "exclusive_rights": [
            {
                "company_name_raw": "한화손해보험",
                "company_name_candidate": "한화손해보험",
                "insurance_type_candidate": "손해보험",
                "exclusive_right_type": {
                    "code": "NEW_RISK_COVERAGE",
                    "name_ko": "새로운 위험 담보",
                    "basis": "새로운 위험 담보",
                    "evidence_text": "새로운 위험 담보 배타적사용권",
                    "confidence": 0.9,
                },
                "subject": {
                    "subject_type": "product",
                    "raw_subject_name": "OO보험",
                    "normalized_subject_name_candidate": "OO보험",
                    "subject_core_key": "oo보험",
                },
                "exclusivity": {"months": 6, "period_text": "6개월", "evidence_text": "6개월 배타적사용권"},
                "acquired": {"year_month": "2026-01", "basis": "explicit_in_article", "date_text": "2026년 1월"},
                "feature_summary": "새로운 위험 담보에 대한 배타적사용권",
                "evidence_summary": "한화손해보험은 OO보험에 대해 6개월 배타적사용권을 획득했다.",
                "confidence": 0.88,
                "needs_review": False,
            }
        ],
    }


def _prepared_batch(db_session, tmp_path):
    article = FactArticle(
        source_api="naver",
        title="한화손해보험 OO보험 6개월 배타적사용권 획득",
        description="한화손해보험은 OO보험에 대해 6개월 배타적사용권을 획득했다.",
        url="https://example.com/exclusive-import",
        original_url="https://example.com/exclusive-import",
        pub_date=datetime(2026, 1, 9),
        content_hash="exclusive-import",
    )
    db_session.add(article)
    db_session.commit()
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
    queue = db_session.query(FactLLMQueue).filter_by(task_type="exclusive_right_extract").one()
    return article, queue, job


def _write_output(path, custom_id: str, payload: dict) -> None:
    output_line = {
        "custom_id": custom_id,
        "response": {
            "text": json.dumps(payload, ensure_ascii=False),
            "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 50},
        },
    }
    path.write_text(json.dumps(output_line, ensure_ascii=False) + "\n", encoding="utf-8")


def test_batch_import_saves_exclusive_right_result_and_cost(db_session, tmp_path):
    article, queue, job = _prepared_batch(db_session, tmp_path)
    output_path = tmp_path / "output.jsonl"
    _write_output(output_path, f"exclusive_right_extract:queue:{queue.llm_queue_id}:article:{article.article_id}", _exclusive_payload())

    result = BatchLLMService().import_results(db_session, job, output_path)

    assert result["completed"] == 1
    assert db_session.query(FactExclusiveUseRight).count() == 1
    assert db_session.query(FactExclusiveUseRightObservation).count() == 1
    assert db_session.query(FactExclusiveUseRightArticle).count() == 1
    assert db_session.query(FactExclusiveUseRightAlias).count() == 1
    assert db_session.query(FactLLMQueue).one().status == "completed"
    assert db_session.query(FactLLMRun).one().batch_yn is True
    assert db_session.query(FactLLMCostLog).one().batch_yn is True


def test_batch_import_is_idempotent_for_same_output(db_session, tmp_path):
    article, queue, job = _prepared_batch(db_session, tmp_path)
    output_path = tmp_path / "output.jsonl"
    _write_output(output_path, f"exclusive_right_extract:queue:{queue.llm_queue_id}:article:{article.article_id}", _exclusive_payload())

    service = BatchLLMService()
    service.import_results(db_session, job, output_path)
    service.import_results(db_session, job, output_path)

    assert db_session.query(FactExclusiveUseRight).count() == 1
    assert db_session.query(FactExclusiveUseRightObservation).count() == 1
    assert db_session.query(FactExclusiveUseRightArticle).count() == 1
    assert db_session.query(FactExclusiveUseRightAlias).count() == 1


def test_applied_or_planned_batch_output_does_not_create_active_canonical(db_session, tmp_path):
    article, queue, job = _prepared_batch(db_session, tmp_path)
    output_path = tmp_path / "planned_output.jsonl"
    _write_output(output_path, f"exclusive_right_extract:queue:{queue.llm_queue_id}:article:{article.article_id}", _exclusive_payload("applied_or_planned"))

    BatchLLMService().import_results(db_session, job, output_path)

    assert db_session.query(FactExclusiveUseRight).count() == 0
    observation = db_session.query(FactExclusiveUseRightObservation).one()
    assert observation.needs_review is True
    assert observation.exclusive_right_id is None

