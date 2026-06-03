from datetime import datetime

from app.collectors.base_news_client import NewsItem
from app.db.models import FactArticle, FactCrawlJob, FactCrawlTask
from app.services.crawl_job_service import CrawlJobService, crawl_article_hash


def news_item(title: str, link: str, original_link: str | None = None) -> NewsItem:
    return NewsItem(title, "desc", datetime(2026, 1, 15, 9, 0), link, original_link, "naver", "보험 신상품", "unit", "publisher")


def test_crawl_dedup_uses_original_url_first():
    first = news_item("A", "https://news.example.com/a", "https://origin.example.com/a")
    second = news_item("B", "https://news.example.com/b", "https://origin.example.com/a")

    assert crawl_article_hash(first) == crawl_article_hash(second)


def test_crawl_dedup_uses_link_when_original_url_missing():
    first = news_item("A", "https://news.example.com/a")
    second = news_item("B", "https://news.example.com/a")

    assert crawl_article_hash(first) == crawl_article_hash(second)


def test_crawl_dedup_falls_back_to_title_pub_date_publisher():
    first = NewsItem("Same", None, datetime(2026, 1, 15, 9, 0), "", None, "naver", "q", "g", "P")
    second = NewsItem("Same", None, datetime(2026, 1, 15, 9, 0), "", None, "naver", "q", "g", "P")

    assert crawl_article_hash(first) == crawl_article_hash(second)


def test_duplicate_article_is_not_inserted(db_session):
    service = CrawlJobService()
    job = FactCrawlJob(job_name="unit", job_type="manual_range", status="running", date_from="2026-01-01", date_to="2026-01-31")
    db_session.add(job)
    db_session.flush()
    task = FactCrawlTask(crawl_job_id=job.crawl_job_id, task_name="task", date_from="2026-01-01", date_to="2026-01-31", query_text="보험 신상품")
    db_session.add(task)
    db_session.flush()
    item = news_item("A", "https://news.example.com/a", "https://origin.example.com/a")

    assert service._save_article(db_session, item, job, task) is True
    assert service._save_article(db_session, item, job, task) is False
    assert db_session.query(FactArticle).count() == 1
