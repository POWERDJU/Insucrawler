from app.db.models import FactCrawlEventLog, FactCrawlJob, FactCrawlTask
from app.services.crawl_job_service import CrawlJobService


def test_crawl_job_task_status_transition_and_counts(db_session):
    job = FactCrawlJob(job_name="unit", job_type="manual_range", status="pending", date_from="2026-01-01", date_to="2026-01-31")
    db_session.add(job)
    db_session.flush()
    task = FactCrawlTask(
        crawl_job_id=job.crawl_job_id,
        task_name="task",
        status="pending",
        date_from="2026-01-01",
        date_to="2026-01-31",
        query_group="unit",
        query_text="보험 신상품",
    )
    db_session.add(task)
    db_session.commit()

    job.status = "running"
    task.status = "completed"
    task.api_calls = 2
    task.items_fetched = 5
    task.articles_saved = 3
    task.articles_duplicated = 1
    CrawlJobService()._sync_job_counts(db_session, job)
    job.status = "completed"
    db_session.commit()

    assert job.total_tasks == 1
    assert job.completed_tasks == 1
    assert job.failed_tasks == 0
    assert job.total_api_calls == 2
    assert job.total_articles_saved == 3
    assert job.total_articles_duplicated == 1
    assert job.status == "completed"


def test_crawl_job_completed_task_count_sums_all_completed_tasks(db_session):
    job = FactCrawlJob(job_name="unit", job_type="manual_range", status="running", date_from="2026-01-01", date_to="2026-01-31")
    db_session.add(job)
    db_session.flush()
    for index in range(3):
        db_session.add(
            FactCrawlTask(
                crawl_job_id=job.crawl_job_id,
                task_name=f"task-{index}",
                status="completed",
                date_from="2026-01-01",
                date_to="2026-01-31",
                query_group="unit",
                query_text=f"보험 신상품 {index}",
                api_calls=1,
            )
        )
    db_session.commit()

    CrawlJobService()._sync_job_counts(db_session, job)

    assert job.total_tasks == 3
    assert job.completed_tasks == 3
    assert job.failed_tasks == 0
    assert job.total_api_calls == 3


def test_crawl_failure_records_task_and_event(db_session):
    job = FactCrawlJob(job_name="unit", job_type="manual_range", status="running", date_from="2026-01-01", date_to="2026-01-31")
    db_session.add(job)
    db_session.flush()
    task = FactCrawlTask(crawl_job_id=job.crawl_job_id, task_name="task", status="failed", date_from="2026-01-01", date_to="2026-01-31", query_text="보험 신상품", last_error="boom")
    db_session.add(task)
    CrawlJobService()._log_event(db_session, job.crawl_job_id, None, "job_failed", "boom")
    db_session.commit()

    event = db_session.query(FactCrawlEventLog).filter(FactCrawlEventLog.crawl_job_id == job.crawl_job_id).one()
    assert task.status == "failed"
    assert task.last_error == "boom"
    assert event.event_type == "job_failed"
