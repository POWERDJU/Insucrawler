from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy.orm import Session

from app.collectors.naver_news_client import NaverNewsClient
from app.db.models import FactArticle
from app.services.company_service import CompanyService
from app.utils.dates import utcnow
from app.utils.hashing import article_dedup_hash


COMPANY_QUERY_TEMPLATES = [
    "{company} 신상품",
    "{company} 보험 출시",
    "{company} 암보험",
    "{company} 건강보험",
    "{company} 운전자보험",
    "{company} 간편보험",
    "{company} 판매건수",
    "{company} 월초보험료",
]


class CollectService:
    def __init__(self, query_config_path: str | Path = "config/query_sets.yaml") -> None:
        self.query_config_path = Path(query_config_path)

    def load_queries(self, query_group: str) -> list[str]:
        with self.query_config_path.open("r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        groups = config.get("query_groups") or {}
        if query_group not in groups:
            raise ValueError(f"Unknown query_group: {query_group}")
        return groups[query_group]

    def company_query_terms(
        self,
        company: dict[str, Any],
        max_aliases_per_company: int | None = None,
    ) -> list[str]:
        max_aliases = max_aliases_per_company
        if max_aliases is None:
            max_aliases = int(os.getenv("MAX_COMPANY_ALIASES_FOR_QUERY", "3"))
        names = [company["company_name_normalized"]]
        aliases = [part.strip() for part in (company.get("alias") or "").split("|") if part.strip()]
        names.extend(aliases[: max(0, max_aliases)])
        seen: set[str] = set()
        return [name for name in names if name and not (name in seen or seen.add(name))]

    def generate_company_queries(
        self,
        db: Session,
        include_reinsurers: bool = False,
        include_foreign_branches: bool = False,
        include_changed_companies: bool = True,
        include_short_term_insurers: bool = True,
        max_aliases_per_company: int | None = None,
    ) -> list[str]:
        companies = CompanyService().list_companies(
            db,
            include_product_news_default_only=True,
            include_reinsurers=include_reinsurers,
            include_foreign_branches=include_foreign_branches,
            include_changed_companies=include_changed_companies,
            include_short_term_insurers=include_short_term_insurers,
        )
        queries: list[str] = []
        seen: set[str] = set()
        for company in companies:
            for name in self.company_query_terms(company, max_aliases_per_company=max_aliases_per_company):
                for template in COMPANY_QUERY_TEMPLATES:
                    query = template.format(company=name)
                    if query not in seen:
                        queries.append(query)
                        seen.add(query)
        return queries

    def collect_naver(
        self,
        db: Session,
        query_group: str,
        days_back: int = 30,
        max_results_per_query: int = 100,
        include_company_queries: bool = False,
        include_reinsurers: bool = False,
        include_foreign_branches: bool = False,
        include_changed_companies: bool = True,
        include_short_term_insurers: bool = True,
    ) -> dict[str, int]:
        client = NaverNewsClient()
        inserted = 0
        skipped = 0
        seen_hashes: set[str] = set()
        queries = self.load_queries(query_group)
        if include_company_queries:
            queries += self.generate_company_queries(
                db,
                include_reinsurers=include_reinsurers,
                include_foreign_branches=include_foreign_branches,
                include_changed_companies=include_changed_companies,
                include_short_term_insurers=include_short_term_insurers,
            )
        queries = list(dict.fromkeys(queries))
        for query in queries:
            for item in client.search(query=query, query_group=query_group, days_back=days_back, max_results=max_results_per_query):
                content_hash = article_dedup_hash(item.original_link or item.link, item.title, item.description)
                if content_hash in seen_hashes:
                    skipped += 1
                    continue
                exists = db.query(FactArticle).filter(FactArticle.content_hash == content_hash).first()
                if exists:
                    skipped += 1
                    continue
                seen_hashes.add(content_hash)
                db.add(
                    FactArticle(
                        source_api=item.source_api,
                        title=item.title,
                        description=item.description,
                        publisher=item.publisher,
                        url=item.link,
                        original_url=item.original_link,
                        pub_date=item.pub_date,
                        collected_at=utcnow(),
                        query=item.query,
                        query_group=item.query_group,
                        content_hash=content_hash,
                        extraction_status="pending",
                    )
                )
                inserted += 1
        db.commit()
        return {"inserted": inserted, "skipped_duplicates": skipped, "queries_used": len(queries)}
