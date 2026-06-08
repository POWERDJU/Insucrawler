from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.scheduled_refresh_service import ScheduledRefreshConfig, ScheduledRefreshService


def test_scheduled_refresh_date_range_uses_recent_lookback_days():
    service = ScheduledRefreshService(
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

    start, end = service.compute_refresh_date_range(datetime(2026, 6, 11, 9, 0, tzinfo=ZoneInfo("Asia/Seoul")))

    assert start.isoformat() == "2026-06-06"
    assert end.isoformat() == "2026-06-11"


def test_scheduled_refresh_skips_nonexistent_31st():
    service = ScheduledRefreshService(
        config=ScheduledRefreshConfig(
            enabled=True,
            timezone="Asia/Seoul",
            days_of_month=(31,),
            hour=9,
            lookback_days=5,
            run_on_startup_catchup=False,
            max_concurrent_jobs=1,
        )
    )

    next_run = service.next_run_at(datetime(2026, 6, 1, 0, 0, tzinfo=ZoneInfo("Asia/Seoul")))

    assert next_run.date().isoformat() == "2026-07-31"
