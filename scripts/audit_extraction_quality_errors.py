from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import SessionLocal
from app.db.models import DimProduct, FactArticle, FactExclusiveUseRight, FactLLMQueue, FactSalesMetricStructured


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--crawl-job-id", type=int)
    args = parser.parse_args()

    with SessionLocal() as db:
        article_query = db.query(FactArticle)
        queue_query = db.query(FactLLMQueue)
        if args.crawl_job_id is not None:
            article_query = article_query.filter(FactArticle.crawl_job_id == args.crawl_job_id)
            queue_query = queue_query.filter(FactLLMQueue.crawl_job_id == args.crawl_job_id)
        payload = {
            "crawl_job_id": args.crawl_job_id,
            "articles": {
                "total": article_query.count(),
                "excluded_article_eligibility": article_query.filter(FactArticle.extraction_status == "excluded_article_eligibility").count(),
                "multi_company_flagged": article_query.filter(FactArticle.multi_company_article_yn.is_(True)).count(),
            },
            "queues": {
                "pending": queue_query.filter(FactLLMQueue.status == "pending").count(),
                "running": queue_query.filter(FactLLMQueue.status == "running").count(),
                "failed": queue_query.filter(FactLLMQueue.status == "failed").count(),
                "completed": queue_query.filter(FactLLMQueue.status == "completed").count(),
            },
            "products": {
                "active": db.query(DimProduct).filter(DimProduct.product_status == "active").count(),
                "review": db.query(DimProduct).filter(DimProduct.product_status.like("review%")).count(),
            },
            "exclusive_rights": {
                "active": db.query(FactExclusiveUseRight).filter(FactExclusiveUseRight.event_status == "active").count(),
                "review": db.query(FactExclusiveUseRight).filter(FactExclusiveUseRight.event_status == "review").count(),
            },
            "sales_metrics_needing_review": db.query(FactSalesMetricStructured).filter(FactSalesMetricStructured.needs_human_review.is_(True)).count(),
        }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
