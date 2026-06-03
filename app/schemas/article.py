from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ArticleCollectRequest(BaseModel):
    query_group: str = "new_product"
    days_back: int = 30
    max_results_per_query: int = 100
    include_company_queries: bool = False
    include_reinsurers: bool = False
    include_foreign_branches: bool = False
    include_changed_companies: bool = True
    include_short_term_insurers: bool = True


class ArticleResponse(BaseModel):
    article_id: int
    source_api: str
    title: str
    description: str | None = None
    url: str
    original_url: str | None = None
    pub_date: datetime | None = None
    query: str | None = None
    query_group: str | None = None
    extraction_status: str
