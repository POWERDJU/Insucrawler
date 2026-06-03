from datetime import datetime

from app.collectors.base_news_client import NewsItem
from app.collectors.naver_news_client import NaverNewsClient
from app.services.crawl_job_service import item_in_range


def item(pub_date: datetime) -> NewsItem:
    return NewsItem("title", None, pub_date, "https://example.com/a", None, "naver", "q", "g")


def test_pub_date_range_filter_includes_january_2026():
    assert item_in_range(item(datetime(2026, 1, 1, 0, 0)), datetime(2026, 1, 1).date(), datetime(2026, 1, 31).date())
    assert item_in_range(item(datetime(2026, 1, 31, 23, 59)), datetime(2026, 1, 1).date(), datetime(2026, 1, 31).date())


def test_pub_date_range_filter_excludes_outside_dates():
    assert not item_in_range(item(datetime(2025, 12, 31, 23, 59)), datetime(2026, 1, 1).date(), datetime(2026, 1, 31).date())
    assert not item_in_range(item(datetime(2026, 2, 1, 0, 0)), datetime(2026, 1, 1).date(), datetime(2026, 1, 31).date())


def test_naver_pub_date_parser_handles_timezone():
    parsed = NaverNewsClient._parse_pub_date("Wed, 14 Jan 2026 09:30:00 +0900")
    assert parsed.year == 2026
    assert parsed.month == 1
    assert parsed.day == 14
    assert parsed.tzinfo is None
