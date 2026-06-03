from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import SessionLocal
from app.db.models import FactArticle
from app.services.extract_service import ExtractService
from app.services.screening_service import ScreeningService


EXTRACTION_MODES = ("none", "screening_only", "enqueue_only", "realtime", "batch")


def main() -> None:
    parser = argparse.ArgumentParser(description="Reprocess already-collected articles through the LLM extraction/classification pipeline.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum pending articles to process. 0 means all pending articles.")
    parser.add_argument("--mode", type=str, default=None, help="Optional LLM_PIPELINE_MODE override for this run.")
    parser.add_argument("--crawl-job-id", type=int, default=None, help="Restrict processing to one crawl job.")
    parser.add_argument(
        "--extraction-mode",
        choices=EXTRACTION_MODES,
        default=os.getenv("CRAWL_EXTRACTION_MODE", "enqueue_only"),
        help="Default is enqueue_only. Use realtime only for small manual tests.",
    )
    parser.add_argument("--sleep", type=float, default=0.0, help="Seconds to sleep between articles.")
    args = parser.parse_args()

    if args.mode:
        os.environ["LLM_PIPELINE_MODE"] = args.mode

    started = time.perf_counter()
    processed = 0
    saved = 0
    failed = 0
    schema_failed = 0
    total_products = 0
    service = ExtractService()

    with SessionLocal() as db:
        if args.extraction_mode == "none":
            print(json.dumps({"event": "completed", "processed": 0, "mode": "none"}, ensure_ascii=False), flush=True)
            return
        if args.extraction_mode == "screening_only":
            query = db.query(FactArticle).filter(FactArticle.extraction_status == "pending").order_by(FactArticle.article_id)
            if args.crawl_job_id is not None:
                query = query.filter(FactArticle.crawl_job_id == args.crawl_job_id)
            if args.limit and args.limit > 0:
                query = query.limit(args.limit)
            articles = query.all()
            screening = ScreeningService()
            for article in articles:
                screening.screen_article(db, article)
            db.commit()
            print(json.dumps({"event": "completed", "processed": len(articles), "mode": "screening_only"}, ensure_ascii=False), flush=True)
            return
        if args.extraction_mode in {"enqueue_only", "batch"}:
            if args.crawl_job_id is not None:
                result = service.enqueue_articles_for_crawl_job(
                    db,
                    args.crawl_job_id,
                    force_batch_eligible=args.extraction_mode == "batch",
                    limit=args.limit or None,
                )
            else:
                query = db.query(FactArticle).filter(FactArticle.extraction_status == "pending").order_by(FactArticle.article_id)
                if args.limit and args.limit > 0:
                    query = query.limit(args.limit)
                rows = query.all()
                results = [
                    service.enqueue_article_extraction(
                        db,
                        article.article_id,
                        force_batch_eligible=args.extraction_mode == "batch",
                    )
                    for article in rows
                ]
                result = {
                    "processed": len(results),
                    "queued": sum(1 for item in results if item.get("status") == "queued"),
                    "screened_skip": sum(1 for item in results if item.get("status") == "screened_skip"),
                    "cluster_extracted": sum(1 for item in results if item.get("status") == "cluster_extracted"),
                }
            db.commit()
            print(json.dumps({"event": "completed", "mode": args.extraction_mode, **result}, ensure_ascii=False), flush=True)
            return

        query = db.query(FactArticle).filter(FactArticle.extraction_status == "pending").order_by(FactArticle.pub_date.asc().nullslast(), FactArticle.article_id.asc())
        if args.crawl_job_id is not None:
            query = query.filter(FactArticle.crawl_job_id == args.crawl_job_id)
        if args.limit and args.limit > 0:
            query = query.limit(args.limit)
        article_ids = [row.article_id for row in query.all()]
        print(json.dumps({"event": "start", "pending_articles": len(article_ids), "mode": os.getenv("LLM_PIPELINE_MODE"), "extraction_mode": args.extraction_mode}, ensure_ascii=False), flush=True)

    for index, article_id in enumerate(article_ids, start=1):
        with SessionLocal() as db:
            try:
                result = service.extract_article(db, article_id)
            except Exception as exc:
                failed += 1
                result = {"status": "failed", "message": str(exc), "product_ids": []}
                article = db.get(FactArticle, article_id)
                if article:
                    article.extraction_status = "failed"
                    db.commit()
            status = result.get("status")
            if status == "saved":
                saved += 1
            elif status == "schema_fail":
                schema_failed += 1
            elif status == "failed":
                failed += 1
            product_count = len(result.get("product_ids") or [])
            total_products += product_count
            processed += 1
            remaining = len(article_ids) - processed
            counts = _counts(db)
            print(
                json.dumps(
                    {
                        "event": "article_done",
                        "index": index,
                        "total": len(article_ids),
                        "remaining": remaining,
                        "article_id": article_id,
                        "status": status,
                        "products_from_article": product_count,
                        "product_count": counts["product_count"],
                        "failed_articles": counts["failed_articles"],
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
        if args.sleep:
            time.sleep(args.sleep)

    elapsed_seconds = round(time.perf_counter() - started, 2)
    with SessionLocal() as db:
        counts = _counts(db)
    print(
        json.dumps(
            {
                "event": "completed",
                "processed": processed,
                "saved": saved,
                "failed": failed,
                "schema_failed": schema_failed,
                "products_from_results": total_products,
                **counts,
                "elapsed_seconds": elapsed_seconds,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


def _counts(db) -> dict[str, int]:
    product_count = db.execute(text("SELECT COUNT(*) FROM dim_product")).scalar_one()
    extracted_articles = db.execute(text("SELECT COUNT(*) FROM fact_article WHERE extraction_status = 'extracted'")).scalar_one()
    pending_articles = db.execute(text("SELECT COUNT(*) FROM fact_article WHERE extraction_status = 'pending'")).scalar_one()
    failed_articles = db.execute(text("SELECT COUNT(*) FROM fact_article WHERE extraction_status IN ('failed', 'schema_fail')")).scalar_one()
    return {
        "product_count": product_count,
        "extracted_articles": extracted_articles,
        "pending_articles": pending_articles,
        "failed_articles": failed_articles,
    }


if __name__ == "__main__":
    main()
