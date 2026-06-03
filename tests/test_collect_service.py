from datetime import datetime

from app.collectors.base_news_client import NewsItem
from app.services.collect_service import CollectService


class DuplicateClient:
    def search(self, query, query_group, days_back=30, max_results=100):
        return [
            NewsItem(
                title="중복 기사",
                description="같은 기사",
                pub_date=datetime(2026, 5, 26),
                link="https://example.com/a",
                original_link="https://example.com/original-a",
                source_api="naver_news",
                query=query,
                query_group=query_group,
            )
        ]


def test_collect_deduplicates_within_same_batch(db_session, monkeypatch):
    service = CollectService()
    monkeypatch.setattr(service, "load_queries", lambda query_group: ["보험 신상품", "생명보험 신상품"])
    monkeypatch.setattr("app.services.collect_service.NaverNewsClient", lambda: DuplicateClient())
    result = service.collect_naver(db_session, "new_product", days_back=1, max_results_per_query=1)
    assert result["inserted"] == 1
    assert result["skipped_duplicates"] == 1


def test_company_query_generation_uses_aliases_and_default_exclusions(db_session):
    service = CollectService()
    queries = service.generate_company_queries(db_session, max_aliases_per_company=3)
    assert "DGB생명 신상품" in queries
    assert "MG손보 보험 출시" in queries
    assert "예별손보 보험 출시" in queries
    assert "캐롯손보 보험 출시" in queries
    assert "마이브라운 보험 출시" in queries
    assert "코리안리 신상품" not in queries

    expanded = service.generate_company_queries(db_session, include_reinsurers=True, max_aliases_per_company=1)
    assert "코리안리 신상품" in expanded
