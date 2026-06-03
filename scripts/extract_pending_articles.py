from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import SessionLocal
from app.db.models import FactArticle
from app.services.extract_service import ExtractService
from app.services.screening_service import ScreeningService


EXTRACTION_MODES = ("none", "screening_only", "enqueue_only", "realtime", "batch")


def _enqueue_pending(db, *, crawl_job_id: int | None, limit: int, batch: bool) -> dict:
    service = ExtractService()
    if crawl_job_id is not None:
        return service.enqueue_articles_for_crawl_job(db, crawl_job_id, force_batch_eligible=batch, limit=limit)
    query = db.query(FactArticle).filter(FactArticle.extraction_status == "pending").order_by(FactArticle.article_id)
    if limit:
        query = query.limit(limit)
    results = [service.enqueue_article_extraction(db, article.article_id, force_batch_eligible=batch) for article in query.all()]
    db.commit()
    return {
        "processed": len(results),
        "queued": sum(1 for item in results if item.get("status") == "queued"),
        "screened_skip": sum(1 for item in results if item.get("status") == "screened_skip"),
        "cluster_extracted": sum(1 for item in results if item.get("status") == "cluster_extracted"),
        "results": results,
    }


def _screen_pending(db, *, crawl_job_id: int | None, limit: int) -> dict:
    screening = ScreeningService()
    query = db.query(FactArticle).filter(FactArticle.extraction_status == "pending").order_by(FactArticle.article_id)
    if crawl_job_id is not None:
        query = query.filter(FactArticle.crawl_job_id == crawl_job_id)
    if limit:
        query = query.limit(limit)
    rows = query.all()
    for article in rows:
        screening.screen_article(db, article)
    db.commit()
    return {"processed": len(rows), "mode": "screening_only"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--crawl-job-id", type=int, default=None)
    parser.add_argument(
        "--extraction-mode",
        choices=EXTRACTION_MODES,
        default=os.getenv("CRAWL_EXTRACTION_MODE", "enqueue_only"),
        help="Default is enqueue_only to avoid accidental realtime LLM calls.",
    )
    args = parser.parse_args()
    with SessionLocal() as db:
        if args.extraction_mode == "none":
            result = {"processed": 0, "mode": "none"}
        elif args.extraction_mode == "screening_only":
            result = _screen_pending(db, crawl_job_id=args.crawl_job_id, limit=args.limit)
        elif args.extraction_mode in {"enqueue_only", "batch"}:
            result = _enqueue_pending(db, crawl_job_id=args.crawl_job_id, limit=args.limit, batch=args.extraction_mode == "batch")
        elif args.crawl_job_id is not None:
            result = ExtractService().extract_pending_articles_for_crawl_job(db, args.crawl_job_id, args.limit)
        else:
            result = ExtractService().extract_pending_articles(db, args.limit)
    print(result)


if __name__ == "__main__":
    main()
