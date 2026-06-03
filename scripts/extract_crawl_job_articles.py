from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.db.database import SessionLocal
from app.db.models import FactArticle
from app.services.extract_service import ExtractService
from app.services.screening_service import ScreeningService


lock = threading.Lock()
summary = {"processed": 0, "saved": 0, "schema_fail": 0, "failed": 0}
EXTRACTION_MODES = ("none", "screening_only", "enqueue_only", "realtime", "batch")


def claim_article(crawl_job_id: int) -> int | None:
    for attempt in range(30):
        try:
            with SessionLocal() as db:
                row = db.execute(
                    text(
                        """
                        UPDATE fact_article
                        SET extraction_status = 'processing'
                        WHERE article_id = (
                            SELECT article_id
                            FROM fact_article
                            WHERE crawl_job_id = :crawl_job_id
                              AND extraction_status = 'pending'
                            ORDER BY article_id
                            LIMIT 1
                        )
                        RETURNING article_id
                        """
                    ),
                    {"crawl_job_id": crawl_job_id},
                ).first()
                db.commit()
                return int(row[0]) if row else None
        except OperationalError as exc:
            if "database is locked" not in str(exc).lower() or attempt == 29:
                raise
            time.sleep(min(10.0, 0.5 * (attempt + 1)))
    return None


def mark_failed(article_id: int, status: str = "failed") -> None:
    with SessionLocal() as db:
        article = db.get(FactArticle, article_id)
        if article:
            article.extraction_status = status
        db.commit()


def worker(crawl_job_id: int) -> None:
    while True:
        article_id = claim_article(crawl_job_id)
        if article_id is None:
            return
        try:
            with SessionLocal() as db:
                result = ExtractService().extract_article(db, article_id)
            status = result.get("status")
        except Exception:
            mark_failed(article_id)
            status = "failed"
        with lock:
            summary["processed"] += 1
            if status == "saved":
                summary["saved"] += 1
            elif status == "schema_fail":
                summary["schema_fail"] += 1
            else:
                summary["failed"] += 1
            if summary["processed"] % 10 == 0:
                print(json.dumps(summary, ensure_ascii=False), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--crawl-job-id", type=int, required=True)
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument(
        "--extraction-mode",
        choices=EXTRACTION_MODES,
        default=os.getenv("CRAWL_EXTRACTION_MODE", "enqueue_only"),
        help="Default is enqueue_only; use realtime only for small manual tests.",
    )
    args = parser.parse_args()

    if args.extraction_mode == "none":
        print(json.dumps({"processed": 0, "mode": "none"}, ensure_ascii=False), flush=True)
        return
    if args.extraction_mode == "screening_only":
        with SessionLocal() as db:
            articles = (
                db.query(FactArticle)
                .filter(FactArticle.crawl_job_id == args.crawl_job_id, FactArticle.extraction_status == "pending")
                .order_by(FactArticle.article_id)
                .all()
            )
            screening = ScreeningService()
            for article in articles:
                screening.screen_article(db, article)
            db.commit()
        print(json.dumps({"processed": len(articles), "mode": "screening_only"}, ensure_ascii=False), flush=True)
        return
    if args.extraction_mode in {"enqueue_only", "batch"}:
        with SessionLocal() as db:
            result = ExtractService().enqueue_articles_for_crawl_job(
                db,
                args.crawl_job_id,
                force_batch_eligible=args.extraction_mode == "batch",
            )
            db.commit()
        print(json.dumps({"mode": args.extraction_mode, **{k: v for k, v in result.items() if k != "results"}}, ensure_ascii=False), flush=True)
        return

    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as executor:
        futures = [executor.submit(worker, args.crawl_job_id) for _ in range(max(1, args.concurrency))]
        for future in as_completed(futures):
            future.result()
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
