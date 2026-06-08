from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import SessionLocal
from app.db.models import FactArticle, FactLLMQueue
from app.services.article_eligibility_filter_service import ArticleEligibilityFilterService


def main() -> None:
    parser = argparse.ArgumentParser(description="Requeue batch items after excluding ineligible source articles.")
    parser.add_argument("--batch-job-id", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.dry_run and not args.apply:
        args.dry_run = True
    service = ArticleEligibilityFilterService()
    result = {"total_queue_items": 0, "excluded_ineligible_count": 0, "requeued_count": 0}
    with SessionLocal() as db:
        query = db.query(FactLLMQueue)
        if args.batch_job_id:
            query = query.filter(FactLLMQueue.llm_batch_job_id == args.batch_job_id)
        else:
            query = query.filter(FactLLMQueue.status.in_(["running", "failed", "pending"]))
        for queue in query.order_by(FactLLMQueue.llm_queue_id).all():
            result["total_queue_items"] += 1
            ineligible = False
            if queue.target_type == "article":
                article = db.get(FactArticle, queue.target_id)
                if article:
                    decision = service.classify_article(db, article)
                    ineligible = not decision.is_eligible
                    if args.apply and ineligible:
                        service.mark_article(db, article, decision)
            if ineligible:
                result["excluded_ineligible_count"] += 1
                if args.apply:
                    queue.status = "excluded_ineligible_article"
                    queue.batch_eligible_yn = False
                    queue.last_error = "Excluded by deterministic article eligibility filter."
                continue
            if args.apply and queue.status in {"running", "failed"}:
                queue.status = "pending"
                queue.llm_batch_job_id = None
                queue.batch_eligible_yn = True
                result["requeued_count"] += 1
        if args.apply:
            db.commit()
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
