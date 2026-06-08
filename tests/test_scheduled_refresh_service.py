from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.scheduled_refresh_service import ScheduledRefreshConfig, ScheduledRefreshService


def test_should_run_today_requires_configured_day_and_hour():
    service = ScheduledRefreshService(
        config=ScheduledRefreshConfig(
            enabled=True,
            timezone="Asia/Seoul",
            days_of_month=(11,),
            hour=9,
            lookback_days=5,
            run_on_startup_catchup=False,
            max_concurrent_jobs=1,
        )
    )

    assert service.should_run_today(datetime(2026, 6, 11, 9, 10, tzinfo=ZoneInfo("Asia/Seoul")))
    assert not service.should_run_today(datetime(2026, 6, 11, 8, 59, tzinfo=ZoneInfo("Asia/Seoul")))
    assert not service.should_run_today(datetime(2026, 6, 12, 9, 0, tzinfo=ZoneInfo("Asia/Seoul")))


def test_create_scheduled_refresh_job_uses_batch_qwen_pipeline(db_session, monkeypatch):
    monkeypatch.setattr("app.services.crawl_job_service.CrawlJobService.generate_queries", lambda self, db, **kwargs: [])
    service = ScheduledRefreshService(
        config=ScheduledRefreshConfig(
            enabled=True,
            timezone="Asia/Seoul",
            days_of_month=(11,),
            hour=9,
            lookback_days=5,
            run_on_startup_catchup=False,
            max_concurrent_jobs=1,
        )
    )

    job = service.create_scheduled_refresh_job(
        db_session,
        now=datetime(2026, 6, 11, 9, 0, tzinfo=ZoneInfo("Asia/Seoul")),
    )

    assert job.date_from == "2026-06-06"
    assert job.date_to == "2026-06-11"
    assert job.extraction_mode == "batch"
    assert job.pipeline_mode == "crawl_parse_postprocess_qwen"
    assert job.include_qwen_adjudication is True
