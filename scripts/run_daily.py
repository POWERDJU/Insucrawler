from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import SessionLocal, engine
from app.db.migrations import init_db
from app.db.seed_master_data import seed_all
from app.services.collect_service import CollectService
from app.services.extract_service import ExtractService
from app.services.pivot_service import PivotService


def main() -> None:
    init_db(engine)
    with SessionLocal() as db:
        seed_all(db)
        collect_result = CollectService().collect_naver(db, "new_product", 30, 100)
        extraction_mode = os.getenv("CRAWL_EXTRACTION_MODE", "enqueue_only")
        if extraction_mode == "realtime":
            extract_result = ExtractService().extract_pending_articles(db, 20)
        elif extraction_mode in {"enqueue_only", "batch"}:
            extract_result = {
                "mode": extraction_mode,
                "note": "Daily run queued pending articles; use realtime only for small manual tests.",
                **_enqueue_pending(db, batch=extraction_mode == "batch", limit=20),
            }
        else:
            extract_result = {"mode": extraction_mode, "processed": 0}
        pivot_result = PivotService().run_pivot(
            db,
            base="product",
            classification_mode="primary_only",
            rows=["release_year_month"],
            columns=["product_type_name"],
            filters={},
            metrics=[{"name": "product_count", "agg": "count_distinct", "field": "product_id"}],
            include_review=False,
            min_confidence=None,
        )
        PivotService().export(pivot_result, "data/exports/daily_product_type_by_month.csv", "csv")
    print({"collect": collect_result, "extract": extract_result, "export": "data/exports/daily_product_type_by_month.csv"})


def _enqueue_pending(db, *, batch: bool, limit: int) -> dict:
    from app.db.models import FactArticle

    service = ExtractService()
    articles = (
        db.query(FactArticle)
        .filter(FactArticle.extraction_status == "pending")
        .order_by(FactArticle.article_id)
        .limit(limit)
        .all()
    )
    results = [service.enqueue_article_extraction(db, article.article_id, force_batch_eligible=batch) for article in articles]
    db.commit()
    return {
        "processed": len(results),
        "queued": sum(1 for item in results if item.get("status") == "queued"),
        "screened_skip": sum(1 for item in results if item.get("status") == "screened_skip"),
        "cluster_extracted": sum(1 for item in results if item.get("status") == "cluster_extracted"),
    }


if __name__ == "__main__":
    main()
