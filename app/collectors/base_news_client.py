from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class NewsItem:
    title: str
    description: str | None
    pub_date: datetime | None
    link: str
    original_link: str | None
    source_api: str
    query: str
    query_group: str
    publisher: str | None = None


class BaseNewsClient(ABC):
    @abstractmethod
    def search(self, query: str, query_group: str, days_back: int = 30, max_results: int = 100) -> list[NewsItem]:
        raise NotImplementedError
