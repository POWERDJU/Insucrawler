from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import SessionLocal
from app.services.crawl_job_service import CrawlJobService


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a crawl job and prepare the exclusive-use-right batch pipeline.")
    parser.add_argument("--date-from", required=True)
    parser.add_argument("--date-to", required=True)
    parser.add_argument("--exclusive-mode", choices=["screening_only", "enqueue_only", "batch", "realtime", "none"], default="batch")
    parser.add_argument("--submit-batch", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--include-reinsurers", action="store_true")
    parser.add_argument("--include-foreign-branches", action="store_true")
    args = parser.parse_args()

    service = CrawlJobService()
    with SessionLocal() as db:
        job = service.create_manual_range(
            db,
            date_from=args.date_from,
            date_to=args.date_to,
            include_llm_extraction=False,
            extraction_mode="none",
            include_exclusive_right_pipeline=args.exclusive_mode != "none",
            exclusive_right_pipeline_mode=args.exclusive_mode,
            exclusive_right_auto_submit_batch=args.submit_batch,
            exclusive_right_auto_consolidate=True,
            exclusive_right_limit=args.limit,
            include_reinsurers=args.include_reinsurers,
            include_foreign_branches=args.include_foreign_branches,
            requested_by="script",
        )
        job_id = job.crawl_job_id

    service.run_job_by_id(job_id)
    with SessionLocal() as db:
        detail = service.get_job_detail(db, job_id)
    print(json.dumps(detail, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
