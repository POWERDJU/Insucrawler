from __future__ import annotations

from app.collectors.base_news_client import BaseNewsClient, NewsItem


class BigKindsClient(BaseNewsClient):
    """Extension point for future BigKinds integration."""

    def search(self, query: str, query_group: str, days_back: int = 30, max_results: int = 100) -> list[NewsItem]:
        raise NotImplementedError("BigKinds integration is intentionally left as a future collector")
