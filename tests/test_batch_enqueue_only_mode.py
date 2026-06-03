from __future__ import annotations

from app.db.models import FactArticle, FactCrawlJob, FactLLMQueue
from app.services.batch_llm_service import BatchLLMService


def _job(db, name: str) -> FactCrawlJob:
    job = FactCrawlJob(
        job_name=name,
        job_type="unit",
        status="completed",
        date_from="2026-01-01",
        date_to="2026-01-31",
        extraction_mode="batch",
        include_llm_extraction=True,
    )
    db.add(job)
    db.flush()
    return job


def _article_with_queue(db, job: FactCrawlJob, suffix: str) -> tuple[FactArticle, FactLLMQueue]:
    article = FactArticle(
        source_api="naver",
        title=f"배치 테스트 보험 출시 {suffix}",
        description="보험 신상품 출시 기사",
        url=f"https://example.test/batch-filter/{suffix}",
        content_hash=f"batch-filter-{suffix}",
        crawl_job_id=job.crawl_job_id,
        extraction_status="queued",
    )
    db.add(article)
    db.flush()
    queue = FactLLMQueue(
        target_type="article",
        target_id=article.article_id,
        task_type="extract",
        priority="medium",
        batch_eligible_yn=True,
        status="pending",
    )
    db.add(queue)
    db.flush()
    return article, queue


def test_batch_creation_can_be_scoped_to_crawl_job_id(db_session, tmp_path):
    job_a = _job(db_session, "batch-a")
    job_b = _job(db_session, "batch-b")
    _, queue_a = _article_with_queue(db_session, job_a, "a")
    _, queue_b = _article_with_queue(db_session, job_b, "b")

    job = BatchLLMService().create_from_pending_queue(
        db_session,
        task_type="extract",
        provider="gemini",
        model_name="gemini-2.5-flash",
        limit=10,
        submit=False,
        crawl_job_id=job_a.crawl_job_id,
        output_dir=tmp_path,
    )

    assert job.request_count == 1
    assert queue_a.llm_batch_job_id == job.llm_batch_job_id
    assert queue_a.status == "running"
    assert queue_b.llm_batch_job_id is None
    assert queue_b.status == "pending"


def test_pending_batch_eligible_count_can_filter_by_crawl_job_id(db_session):
    job_a = _job(db_session, "count-a")
    job_b = _job(db_session, "count-b")
    _article_with_queue(db_session, job_a, "a")
    _article_with_queue(db_session, job_b, "b")

    service = BatchLLMService()

    assert service.pending_batch_eligible_count(db_session) == 2
    assert service.pending_batch_eligible_count(db_session, crawl_job_id=job_a.crawl_job_id) == 1
