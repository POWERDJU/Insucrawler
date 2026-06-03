from fastapi.testclient import TestClient

from app.api.main import app
from app.db.database import get_db
from app.db.models import FactArticle, FactCrawlTask, FactLLMQueue
from app.collectors.base_news_client import NewsItem
from app.collectors.naver_news_client import NaverNewsClient
from app.services.admin_auth_service import clear_admin_sessions
from app.services.crawl_job_service import CrawlJobService


def auth_client(monkeypatch, db_session):
    clear_admin_sessions()
    monkeypatch.setenv("ADMIN_BATCH_PASSWORD", "secret")

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    token = client.post("/api/admin/auth", json={"password": "secret"}).json()["token"]
    return client, {"Authorization": f"Bearer {token}"}


def small_queries(self, db, **kwargs):
    return [{"query_group": "unit", "query_text": "보험 신상품"}]


def test_admin_test_2026_01_creates_job(monkeypatch, db_session):
    monkeypatch.setattr(CrawlJobService, "generate_queries", small_queries)
    monkeypatch.setattr(CrawlJobService, "run_job_by_id", lambda self, crawl_job_id: None)
    client, headers = auth_client(monkeypatch, db_session)
    try:
        response = client.post("/api/admin/crawl-jobs/test-2026-01", headers=headers, json={})
        detail = client.get(f"/api/admin/crawl-jobs/{response.json()['crawl_job_id']}", headers=headers).json()

        assert response.status_code == 200
        assert detail["date_from"] == "2026-01-01"
        assert detail["date_to"] == "2026-01-31"
        assert detail["total_tasks"] == 1
    finally:
        app.dependency_overrides.clear()


def test_admin_backfill_creates_monthly_tasks(monkeypatch, db_session):
    monkeypatch.setattr(CrawlJobService, "generate_queries", small_queries)
    monkeypatch.setattr(CrawlJobService, "run_job_by_id", lambda self, crawl_job_id: None)
    client, headers = auth_client(monkeypatch, db_session)
    try:
        response = client.post("/api/admin/crawl-jobs/backfill-2024-2026-05", headers=headers, json={})
        job_id = response.json()["crawl_job_id"]

        assert response.status_code == 200
        assert db_session.query(FactCrawlTask).filter(FactCrawlTask.crawl_job_id == job_id).count() == 29
    finally:
        app.dependency_overrides.clear()


def test_admin_incremental_and_manual_detail(monkeypatch, db_session):
    monkeypatch.setattr(CrawlJobService, "generate_queries", small_queries)
    monkeypatch.setattr(CrawlJobService, "run_job_by_id", lambda self, crawl_job_id: None)
    client, headers = auth_client(monkeypatch, db_session)
    try:
        incremental = client.post("/api/admin/crawl-jobs/incremental", headers=headers, json={"days_back": 14})
        manual = client.post("/api/admin/crawl-jobs/manual-range", headers=headers, json={"date_from": "2026-01-01", "date_to": "2026-01-31"})
        detail = client.get(f"/api/admin/crawl-jobs/{manual.json()['crawl_job_id']}", headers=headers)

        assert incremental.status_code == 200
        assert manual.status_code == 200
        assert detail.status_code == 200
        assert detail.json()["date_from"] == "2026-01-01"
    finally:
        app.dependency_overrides.clear()


def test_admin_search_preview_allows_manual_month_keyword(monkeypatch, db_session):
    def fake_search_page(self, query, query_group, display=100, start=1, sort="date"):
        return [
            NewsItem(
                title="한화손해보험 건강보험 기사",
                description=None,
                pub_date=None,
                link="https://example.test/news",
                original_link=None,
                source_api="naver",
                query=query,
                query_group=query_group,
            )
        ]

    monkeypatch.setattr(NaverNewsClient, "search_page", fake_search_page)
    client, headers = auth_client(monkeypatch, db_session)
    try:
        response = client.post(
            "/api/admin/search-preview/naver-news",
            headers=headers,
            json={"query": "한화손해보험 건강보험 2026년 1월", "display": 10, "sort": "date"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["query"] == "한화손해보험 건강보험 2026년 1월"
        assert payload["items"][0]["title"] == "한화손해보험 건강보험 기사"
    finally:
        app.dependency_overrides.clear()


def test_admin_llm_batch_job_create_and_detail(monkeypatch, db_session, tmp_path):
    monkeypatch.setenv("LLM_BATCH_OUTPUT_DIR", str(tmp_path))
    article = FactArticle(
        source_api="naver",
        title="배치 관리자 보험 출시",
        description="보험 신상품 출시",
        url="https://example.test/admin-batch",
        content_hash="admin-batch-hash",
    )
    db_session.add(article)
    db_session.flush()
    db_session.add(
        FactLLMQueue(
            target_type="article",
            target_id=article.article_id,
            task_type="extract",
            priority="medium",
            batch_eligible_yn=True,
            status="pending",
        )
    )
    db_session.commit()
    client, headers = auth_client(monkeypatch, db_session)
    try:
        create = client.post(
            "/api/admin/llm-batch-jobs/create",
            headers=headers,
            json={"task_type": "extract", "provider": "gemini", "model_name": "gemini-2.5-flash", "limit": 10, "submit": False},
        )
        job_id = create.json()["llm_batch_job_id"]
        listing = client.get("/api/admin/llm-batch-jobs", headers=headers)
        detail = client.get(f"/api/admin/llm-batch-jobs/{job_id}", headers=headers)

        assert create.status_code == 200
        assert create.json()["request_count"] == 1
        assert listing.status_code == 200
        assert detail.status_code == 200
        assert detail.json()["queues"][0]["status"] == "running"
    finally:
        app.dependency_overrides.clear()
