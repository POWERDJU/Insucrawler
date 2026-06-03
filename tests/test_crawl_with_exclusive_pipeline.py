from __future__ import annotations

import json
from datetime import datetime

from fastapi.testclient import TestClient

from app.api.main import app
from app.collectors.base_news_client import NewsItem
from app.db.database import get_db
from app.db.models import (
    FactArticle,
    FactCrawlJob,
    FactCrawlTask,
    FactExclusiveUseRight,
    FactExclusiveUseRightAlias,
    FactExclusiveUseRightArticle,
    FactExclusiveUseRightObservation,
    FactLLMBatchJob,
    FactLLMQueue,
)
from app.services.admin_auth_service import clear_admin_sessions
from app.services.batch_llm_service import BatchLLMService
from app.services.crawl_job_service import CrawlJobService
from app.services.exclusive_right_service import ExclusiveRightService
from app.services.screening_service import ScreeningService


class _FakeNewsClient:
    def search_page(self, query, query_group, display=100, start=1, sort="date"):
        if start != 1:
            return []
        return [
            NewsItem(
                title="한화손해보험, OO보험 6개월 배타적사용권 획득",
                description="한화손해보험은 신상품심의위원회에서 새로운 위험 담보 독창성을 인정받아 배타적사용권을 획득했다.",
                pub_date=datetime(2026, 1, 9, 9, 0),
                link="https://example.test/exclusive-crawl",
                original_link="https://example.test/exclusive-crawl",
                source_api="naver",
                query=query,
                query_group=query_group,
                publisher="테스트뉴스",
            )
        ]


def _small_queries(self, db, **kwargs):
    return [{"query_group": "exclusive_right_common", "query_text": "보험 배타적사용권", "query_source": "exclusive_right_common"}]


def _crawl_job(db_session, *, job_name="exclusive scope") -> FactCrawlJob:
    job = FactCrawlJob(
        job_name=job_name,
        job_type="manual_range",
        status="completed",
        date_from="2026-01-01",
        date_to="2026-01-31",
        include_exclusive_right_pipeline=True,
        exclusive_right_pipeline_mode="batch",
        exclusive_right_auto_consolidate=True,
    )
    db_session.add(job)
    db_session.commit()
    return job


def _exclusive_article(db_session, job: FactCrawlJob, suffix: str) -> FactArticle:
    article = FactArticle(
        source_api="naver",
        title=f"한화손해보험 {suffix} 6개월 배타적사용권 획득",
        description="한화손해보험은 신상품심의위원회에서 새로운 위험 담보 독창성을 인정받아 배타적사용권을 획득했다.",
        url=f"https://example.test/{suffix}",
        original_url=f"https://example.test/{suffix}",
        pub_date=datetime(2026, 1, 10),
        content_hash=f"exclusive-{job.crawl_job_id}-{suffix}",
        crawl_job_id=job.crawl_job_id,
    )
    db_session.add(article)
    db_session.commit()
    ScreeningService().screen_article(db_session, article)
    db_session.commit()
    return article


def _exclusive_payload() -> dict:
    return {
        "exclusive_right_relevance": {"is_relevant": True, "status": "acquired", "reason": "batch test"},
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


def test_crawl_completed_hook_creates_exclusive_batch_queue_without_realtime_provider(monkeypatch, db_session, tmp_path):
    monkeypatch.setenv("LLM_BATCH_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setenv("PRODUCT_CONSOLIDATION_AUTO_AFTER_CRAWL", "false")
    monkeypatch.setattr(CrawlJobService, "generate_queries", _small_queries)
    service = CrawlJobService(client_factory=lambda: _FakeNewsClient())
    job = service.create_manual_range(
        db_session,
        date_from="2026-01-01",
        date_to="2026-01-31",
        include_llm_extraction=False,
        extraction_mode="none",
        include_exclusive_right_pipeline=True,
        exclusive_right_pipeline_mode="batch",
        exclusive_right_auto_submit_batch=False,
        exclusive_right_auto_consolidate=True,
    )

    task = db_session.query(FactCrawlTask).filter_by(crawl_job_id=job.crawl_job_id).one()
    service.run_task(db_session, job, task)
    job.status = "completed"
    service._run_exclusive_right_pipeline_after_crawl(db_session, job)
    db_session.refresh(job)

    queue = db_session.query(FactLLMQueue).filter_by(task_type="exclusive_right_extract").one()
    batch_job = db_session.query(FactLLMBatchJob).filter_by(task_type="exclusive_right_extract").one()
    assert job.status == "completed"
    assert job.exclusive_right_pipeline_status == "batch_created"
    assert job.exclusive_right_candidate_count == 1
    assert queue.crawl_job_id == job.crawl_job_id
    assert queue.batch_eligible_yn is True
    assert queue.status == "running"
    assert batch_job.crawl_job_id == job.crawl_job_id
    assert batch_job.provider_batch_id is None
    assert db_session.query(FactExclusiveUseRight).count() == 0


def test_screening_only_after_crawl_creates_no_queue(monkeypatch, db_session):
    monkeypatch.setenv("PRODUCT_CONSOLIDATION_AUTO_AFTER_CRAWL", "false")
    monkeypatch.setattr(CrawlJobService, "generate_queries", _small_queries)
    service = CrawlJobService(client_factory=lambda: _FakeNewsClient())
    job = service.create_manual_range(
        db_session,
        date_from="2026-01-01",
        date_to="2026-01-31",
        include_exclusive_right_pipeline=True,
        exclusive_right_pipeline_mode="screening_only",
    )

    task = db_session.query(FactCrawlTask).filter_by(crawl_job_id=job.crawl_job_id).one()
    service.run_task(db_session, job, task)
    job.status = "completed"
    service._run_exclusive_right_pipeline_after_crawl(db_session, job)
    db_session.refresh(job)

    assert job.exclusive_right_pipeline_status == "screening_completed"
    assert job.exclusive_right_candidate_count == 1
    assert db_session.query(FactLLMQueue).filter_by(task_type="exclusive_right_extract").count() == 0


def test_exclusive_right_enqueue_is_scoped_to_crawl_job(db_session):
    job_a = _crawl_job(db_session, job_name="job A")
    job_b = _crawl_job(db_session, job_name="job B")
    article_a = _exclusive_article(db_session, job_a, "a")
    article_b = _exclusive_article(db_session, job_b, "b")

    result = ExclusiveRightService().enqueue_pending_for_crawl_job(db_session, job_a.crawl_job_id, batch_eligible=True, limit=10)

    queues = db_session.query(FactLLMQueue).filter_by(task_type="exclusive_right_extract").all()
    assert result["queued_count"] == 1
    assert len(queues) == 1
    assert queues[0].target_id == article_a.article_id
    assert queues[0].crawl_job_id == job_a.crawl_job_id
    assert article_b.article_id != queues[0].target_id


def test_exclusive_right_pipeline_idempotency_for_queue_and_batch(db_session, tmp_path):
    job = _crawl_job(db_session)
    _exclusive_article(db_session, job, "idempotent")
    service = ExclusiveRightService()

    first = service.enqueue_pending_for_crawl_job(db_session, job.crawl_job_id, batch_eligible=True, limit=10)
    second = service.enqueue_pending_for_crawl_job(db_session, job.crawl_job_id, batch_eligible=True, limit=10)
    batch = BatchLLMService().create_from_pending_queue(
        db_session,
        task_type="exclusive_right_extract",
        crawl_job_id=job.crawl_job_id,
        submit=False,
        output_dir=tmp_path,
    )

    assert first["queued_count"] == 1
    assert second["queued_count"] == 0
    assert db_session.query(FactLLMQueue).filter_by(task_type="exclusive_right_extract").count() == 1
    assert batch.request_count == 1
    assert db_session.query(FactLLMQueue).one().llm_batch_job_id == batch.llm_batch_job_id


def test_exclusive_right_batch_auto_submit_option(monkeypatch, db_session, tmp_path):
    monkeypatch.setenv("LLM_BATCH_OUTPUT_DIR", str(tmp_path))
    submitted = []

    def fake_submit(self, db, batch_job):
        submitted.append(batch_job.llm_batch_job_id)
        batch_job.provider_batch_id = "batches/mock-exclusive"
        batch_job.provider_status = "JOB_STATE_PENDING"
        batch_job.status = "submitted"
        return batch_job

    monkeypatch.setattr(BatchLLMService, "submit_batch", fake_submit)
    job = _crawl_job(db_session)
    job.exclusive_right_auto_submit_batch = True
    _exclusive_article(db_session, job, "autosubmit")

    CrawlJobService()._run_exclusive_right_pipeline_after_crawl(db_session, job)
    db_session.refresh(job)

    batch_job = db_session.query(FactLLMBatchJob).filter_by(task_type="exclusive_right_extract").one()
    assert submitted == [batch_job.llm_batch_job_id]
    assert batch_job.provider_batch_id == "batches/mock-exclusive"
    assert job.exclusive_right_batch_job_id == batch_job.llm_batch_job_id
    assert job.exclusive_right_pipeline_status == "batch_submitted"


def test_exclusive_right_batch_import_updates_crawl_job_and_is_idempotent(db_session, tmp_path):
    job = _crawl_job(db_session)
    article = _exclusive_article(db_session, job, "import")
    ExclusiveRightService().enqueue_pending_for_crawl_job(db_session, job.crawl_job_id, batch_eligible=True, limit=10)
    batch = BatchLLMService().create_from_pending_queue(
        db_session,
        task_type="exclusive_right_extract",
        crawl_job_id=job.crawl_job_id,
        submit=False,
        output_dir=tmp_path,
    )
    queue = db_session.query(FactLLMQueue).filter_by(task_type="exclusive_right_extract").one()
    output_path = tmp_path / "exclusive_output.jsonl"
    output_path.write_text(
        json.dumps(
            {
                "custom_id": f"exclusive_right_extract:queue:{queue.llm_queue_id}:article:{article.article_id}:crawl:{job.crawl_job_id}",
                "response": {
                    "text": json.dumps(_exclusive_payload(), ensure_ascii=False),
                    "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 50},
                },
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    service = BatchLLMService()
    first = service.import_results(db_session, batch, output_path)
    second = service.import_results(db_session, batch, output_path)
    db_session.refresh(job)

    assert first["completed"] == 1
    assert second["completed"] == 0
    assert db_session.query(FactExclusiveUseRight).count() == 1
    assert db_session.query(FactExclusiveUseRightObservation).count() == 1
    assert db_session.query(FactExclusiveUseRightArticle).count() == 1
    assert db_session.query(FactExclusiveUseRightAlias).count() == 1
    assert job.exclusive_right_pipeline_status == "consolidated"
    assert job.exclusive_right_imported_count == 1
    assert job.exclusive_right_canonical_count == 1


def test_admin_crawl_request_persists_exclusive_pipeline_options(monkeypatch, db_session):
    clear_admin_sessions()
    monkeypatch.setenv("ADMIN_BATCH_PASSWORD", "secret")
    monkeypatch.setattr(CrawlJobService, "generate_queries", _small_queries)
    monkeypatch.setattr(CrawlJobService, "run_job_by_id", lambda self, crawl_job_id: None)

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    try:
        token = client.post("/api/admin/auth", json={"password": "secret"}).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post(
            "/api/admin/crawl-jobs/manual-range",
            headers=headers,
            json={
                "date_from": "2026-01-01",
                "date_to": "2026-01-31",
                "include_exclusive_right_pipeline": True,
                "exclusive_right_pipeline_mode": "batch",
                "exclusive_right_auto_submit_batch": False,
                "exclusive_right_auto_consolidate": True,
                "exclusive_right_limit": 500,
            },
        )
        detail = client.get(f"/api/admin/crawl-jobs/{response.json()['crawl_job_id']}", headers=headers).json()

        assert response.status_code == 200
        assert response.json()["exclusive_right_pipeline_requested"] is True
        assert detail["include_exclusive_right_pipeline"] is True
        assert detail["exclusive_right_pipeline_mode"] == "batch"
        assert detail["exclusive_right_limit"] == 500
    finally:
        app.dependency_overrides.clear()
