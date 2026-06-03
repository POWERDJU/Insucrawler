from __future__ import annotations

from datetime import datetime

from app.db.models import FactArticle, FactContentScreening, FactCrawlJob, FactLLMQueue
from app.services.crawl_job_service import CrawlJobService
from app.services.screening_service import ScreeningResult, ScreeningService


def _job(db, name: str, mode: str) -> FactCrawlJob:
    job = FactCrawlJob(
        job_name=name,
        job_type="unit",
        status="completed",
        date_from="2026-01-01",
        date_to="2026-01-31",
        include_llm_extraction=mode not in {"none", "screening_only"},
        extraction_mode=mode,
    )
    db.add(job)
    db.flush()
    return job


def _article(db, job: FactCrawlJob, suffix: str) -> FactArticle:
    article = FactArticle(
        source_api="naver",
        title=f"삼성화재 건강보험 출시 {suffix}",
        description="신상품 출시와 보장 내용을 다룬 기사입니다.",
        url=f"https://example.test/{suffix}",
        original_url=f"https://example.test/{suffix}",
        pub_date=datetime(2026, 1, 10),
        content_hash=f"crawl-scope-{suffix}",
        crawl_job_id=job.crawl_job_id,
        extraction_status="pending",
    )
    db.add(article)
    db.flush()
    return article


def _force_high_screening(monkeypatch):
    def fake_screen(self, db, article, body_text=None):
        row = FactContentScreening(
            article_id=article.article_id,
            source_type=article.source_api,
            rule_relevance_score=0.9,
            matched_company_names_json="[]",
            matched_product_type_codes_json='["HEALTH_COMPREHENSIVE"]',
            matched_launch_keywords_json='["출시"]',
            matched_negative_keywords_json="[]",
            is_candidate=True,
            candidate_reason="launch keyword",
            llm_required_yn=True,
            llm_priority="high",
        )
        db.add(row)
        db.flush()
        return ScreeningResult(
            article_id=article.article_id,
            source_type=article.source_api,
            rule_relevance_score=0.9,
            matched_company_names=[],
            matched_product_type_codes=["HEALTH_COMPREHENSIVE"],
            matched_launch_keywords=["출시"],
            matched_negative_keywords=[],
            is_candidate=True,
            candidate_reason="launch keyword",
            llm_required_yn=True,
            llm_priority="high",
        )

    monkeypatch.setattr(ScreeningService, "screen_article", fake_screen)


def test_crawl_job_realtime_extraction_is_scoped_to_job_id(db_session, monkeypatch):
    job_a = _job(db_session, "job-a", "realtime")
    job_b = _job(db_session, "job-b", "realtime")
    article_a = _article(db_session, job_a, "a")
    article_b = _article(db_session, job_b, "b")
    called = []

    def fake_extract_for_job(self, db, crawl_job_id, limit=None):
        called.append(crawl_job_id)
        rows = db.query(FactArticle).filter(FactArticle.crawl_job_id == crawl_job_id, FactArticle.extraction_status == "pending").all()
        for article in rows:
            article.extraction_status = "extracted"
        db.flush()
        return {"processed": len(rows), "results": []}

    monkeypatch.setattr("app.services.extract_service.ExtractService.extract_pending_articles_for_crawl_job", fake_extract_for_job)

    CrawlJobService()._run_optional_extraction(db_session, job_a)

    assert called == [job_a.crawl_job_id]
    assert db_session.get(FactArticle, article_a.article_id).extraction_status == "extracted"
    assert db_session.get(FactArticle, article_b.article_id).extraction_status == "pending"


def test_enqueue_only_creates_queue_without_provider_call(db_session, monkeypatch):
    _force_high_screening(monkeypatch)
    job = _job(db_session, "queue-job", "enqueue_only")
    article = _article(db_session, job, "queue")

    CrawlJobService()._run_optional_extraction(db_session, job)

    queue = db_session.query(FactLLMQueue).filter(FactLLMQueue.target_id == article.article_id).one_or_none()
    assert queue is not None
    assert queue.status == "pending"
    assert db_session.get(FactArticle, article.article_id).extraction_status == "queued"


def test_batch_mode_creates_batch_eligible_queue_without_provider_call(db_session, monkeypatch):
    _force_high_screening(monkeypatch)
    job = _job(db_session, "batch-job", "batch")
    article = _article(db_session, job, "batch")

    CrawlJobService()._run_optional_extraction(db_session, job)

    queue = db_session.query(FactLLMQueue).filter(FactLLMQueue.target_id == article.article_id).one_or_none()
    assert queue is not None
    assert queue.batch_eligible_yn is True
    assert queue.status == "pending"
