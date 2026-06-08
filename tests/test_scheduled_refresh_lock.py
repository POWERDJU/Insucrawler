from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.db.models import FactCrawlJob
from app.services.scheduled_refresh_service import ScheduledRefreshConfig, ScheduledRefreshService


def _service() -> ScheduledRefreshService:
    return ScheduledRefreshService(
        config=ScheduledRefreshConfig(
            enabled=True,
            timezone="Asia/Seoul",
            days_of_month=(1, 6, 11, 16, 21, 26, 31),
            hour=9,
            lookback_days=5,
            run_on_startup_catchup=False,
            max_concurrent_jobs=1,
        )
    )


def test_scheduled_refresh_lock_blocks_second_running_job(db_session):
    db_session.add(
        FactCrawlJob(
            job_name="scheduled_refresh_running",
            job_type="scheduled_refresh",
            status="running",
            date_from="2026-06-06",
            date_to="2026-06-11",
        )
    )
    db_session.commit()

    with pytest.raises(ValueError):
        _service().create_scheduled_refresh_job(
            db_session,
            now=datetime(2026, 6, 11, 9, 0, tzinfo=ZoneInfo("Asia/Seoul")),
        )


def test_scheduled_refresh_reuses_same_slot_job(db_session, monkeypatch):
    service = _service()
    monkeypatch.setattr("app.services.crawl_job_service.CrawlJobService.generate_queries", lambda self, db, **kwargs: [])

    first = service.create_scheduled_refresh_job(
        db_session,
        now=datetime(2026, 6, 11, 9, 0, tzinfo=ZoneInfo("Asia/Seoul")),
    )
    first.status = "completed"
    db_session.commit()
    second = service.create_scheduled_refresh_job(
        db_session,
        now=datetime(2026, 6, 11, 9, 30, tzinfo=ZoneInfo("Asia/Seoul")),
    )

    assert second.crawl_job_id == first.crawl_job_id
