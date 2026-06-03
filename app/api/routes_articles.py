from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import FactArticle
from app.schemas.article import ArticleCollectRequest
from app.services.collect_service import CollectService

router = APIRouter()


@router.post("/collect")
def collect_articles(request: ArticleCollectRequest, db: Session = Depends(get_db)) -> dict:
    return CollectService().collect_naver(
        db,
        request.query_group,
        request.days_back,
        request.max_results_per_query,
        include_company_queries=request.include_company_queries,
        include_reinsurers=request.include_reinsurers,
        include_foreign_branches=request.include_foreign_branches,
        include_changed_companies=request.include_changed_companies,
        include_short_term_insurers=request.include_short_term_insurers,
    )


@router.get("")
def list_articles(
    query: str | None = None,
    source_api: str | None = None,
    pub_date_from: str | None = None,
    pub_date_to: str | None = None,
    extraction_status: str | None = None,
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
) -> list[dict]:
    q = db.query(FactArticle)
    if query:
        q = q.filter(FactArticle.query == query)
    if source_api:
        q = q.filter(FactArticle.source_api == source_api)
    if extraction_status:
        q = q.filter(FactArticle.extraction_status == extraction_status)
    if pub_date_from:
        q = q.filter(FactArticle.pub_date >= datetime.fromisoformat(pub_date_from))
    if pub_date_to:
        q = q.filter(FactArticle.pub_date <= datetime.fromisoformat(pub_date_to))
    rows = q.order_by(FactArticle.pub_date.desc().nullslast(), FactArticle.article_id.desc()).limit(limit).all()
    return [{column.name: getattr(row, column.name) for column in row.__table__.columns} for row in rows]
