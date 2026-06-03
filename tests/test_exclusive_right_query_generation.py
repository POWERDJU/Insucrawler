from app.services.crawl_job_service import CrawlJobService
from app.db.models import FactCrawlTask


def test_exclusive_right_queries_are_generated_without_month_keywords(db_session):
    queries = CrawlJobService().generate_queries(db_session, year=2026, month=1, max_aliases_per_company=0, max_queries_per_company=1)
    texts = {item["query_text"] for item in queries}
    groups = {item["query_group"] for item in queries}

    assert "보험 배타적사용권" in texts
    assert "보험 배타적 사용권" in texts
    assert any(text.endswith("배타적사용권") and text.startswith("메리츠화재") for text in texts)
    assert {"exclusive_right_common", "exclusive_right_company"} <= groups
    assert not any("2026년 1월" in text or "2026.01" in text or "2026-01" in text for text in texts)


def test_exclusive_right_query_group_is_saved_to_crawl_tasks(db_session):
    job = CrawlJobService().create_manual_range(
        db_session,
        date_from="2026-01-01",
        date_to="2026-01-31",
        include_llm_extraction=False,
    )
    task_groups = {task.query_group for task in db_session.query(FactCrawlTask).filter_by(crawl_job_id=job.crawl_job_id).all()}

    assert "exclusive_right_common" in task_groups
    assert "exclusive_right_company" in task_groups
