from app.db.models import FactCrawlTask
from app.services.crawl_job_service import CrawlJobService
from app.services.crawl_query_generator import has_month_keyword


def test_backfill_tasks_do_not_contain_month_keywords_even_for_monthly_jobs(db_session, monkeypatch):
    monkeypatch.setenv("CRAWL_USE_MONTH_KEYWORD", "true")

    job = CrawlJobService().create_test_2026_01(db_session)
    tasks = db_session.query(FactCrawlTask).filter(FactCrawlTask.crawl_job_id == job.crawl_job_id).all()
    query_texts = [task.query_text for task in tasks]

    assert query_texts
    assert not any(has_month_keyword(text) for text in query_texts)
    assert not any("2026년 1월" in text or "2026.01" in text or "2026-01" in text for text in query_texts)


def test_query_generator_skips_discovered_product_name_with_month_keyword(db_session):
    from app.db import repository

    repository.upsert_product(
        db_session,
        {
            "raw_product_name": "테스트 건강보험 2026년 1월",
            "normalized_product_name": "테스트 건강보험 2026년 1월",
            "company_name": "삼성화재",
            "insurance_type": "손해보험",
            "primary_product_type_code": "HEALTH_COMPREHENSIVE",
        },
    )
    db_session.commit()

    texts = [item["query_text"] for item in CrawlJobService().generate_queries(db_session, year=2026, month=1)]

    assert "테스트 건강보험 2026년 1월" not in texts
    assert "삼성화재 테스트 건강보험 2026년 1월" not in texts
    assert not any(has_month_keyword(text) for text in texts)
