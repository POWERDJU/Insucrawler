from __future__ import annotations

import email.utils
import os
from datetime import datetime, timedelta
from typing import Any

import httpx

from app.collectors.base_news_client import BaseNewsClient, NewsItem
from app.utils.text import strip_html


class NaverNewsClient(BaseNewsClient):
    endpoint = "https://openapi.naver.com/v1/search/news.json"

    def __init__(self, client_id: str | None = None, client_secret: str | None = None) -> None:
        self.client_id = client_id or os.getenv("NAVER_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("NAVER_CLIENT_SECRET")

    def _headers(self) -> dict[str, str]:
        if not self.client_id or not self.client_secret:
            raise RuntimeError("NAVER_CLIENT_ID and NAVER_CLIENT_SECRET are required")
        return {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret,
        }

    @staticmethod
    def _parse_pub_date(value: str | None) -> datetime | None:
        if not value:
            return None
        parsed = email.utils.parsedate_to_datetime(value)
        return parsed.replace(tzinfo=None)

    def search(self, query: str, query_group: str, days_back: int = 30, max_results: int = 100) -> list[NewsItem]:
        collected: list[NewsItem] = []
        cutoff = datetime.utcnow() - timedelta(days=days_back)
        display = min(max_results, 100)
        for start in range(1, max_results + 1, display):
            items = self.search_page(query=query, query_group=query_group, display=display, start=start, sort="date")
            if not items:
                break
            for item in items:
                if item.pub_date and item.pub_date < cutoff:
                    continue
                collected.append(item)
            if len(items) < display:
                break
        return collected[:max_results]

    def search_page(self, query: str, query_group: str, display: int = 100, start: int = 1, sort: str = "date") -> list[NewsItem]:
        params: dict[str, Any] = {"query": query, "display": min(display, 100), "start": start, "sort": sort}
        with httpx.Client(timeout=20) as client:
            response = client.get(self.endpoint, headers=self._headers(), params=params)
            response.raise_for_status()
        return [self._item_from_naver(raw_item, query, query_group) for raw_item in response.json().get("items", [])]

    def _item_from_naver(self, item: dict[str, Any], query: str, query_group: str) -> NewsItem:
        return NewsItem(
            title=strip_html(item.get("title")),
            description=strip_html(item.get("description")),
            pub_date=self._parse_pub_date(item.get("pubDate")),
            link=item.get("link") or item.get("originallink") or "",
            original_link=item.get("originallink"),
            source_api="naver",
            query=query,
            query_group=query_group,
        )
