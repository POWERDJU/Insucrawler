from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import SessionLocal
from app.services.batch_llm_service import BatchLLMService
from app.services.exclusive_right_consolidation_service import ExclusiveRightConsolidationService
from app.services.exclusive_right_service import ExclusiveRightService


def main() -> None:
    parser = argparse.ArgumentParser(description="Run exclusive-use-right screening/queue/batch/import workflow.")
    parser.add_argument("--date-from", default=None)
    parser.add_argument("--date-to", default=None)
    parser.add_argument("--crawl-job-id", type=int, default=None)
    parser.add_argument("--mode", choices=["none", "screening_only", "enqueue_only", "batch", "realtime"], default="enqueue_only")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--create-batch", action="store_true")
    parser.add_argument("--submit-batch", action="store_true")
    parser.add_argument("--import-results", default=None, help="Import a local batch output JSONL file.")
    parser.add_argument("--batch-job-id", type=int, default=None)
    parser.add_argument("--consolidate", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    result: dict = {}
    with SessionLocal() as db:
        result["extract"] = ExclusiveRightService().extract_pending(
            db,
            limit=args.limit,
            mode=args.mode,
            date_from=args.date_from,
            date_to=args.date_to,
            crawl_job_id=args.crawl_job_id,
        )
        if args.mode == "batch" and (args.create_batch or args.submit_batch or args.import_results is not None):
            batch_service = BatchLLMService()
            job = None
            if args.batch_job_id:
                from app.db.models import FactLLMBatchJob

                job = db.get(FactLLMBatchJob, args.batch_job_id)
                if job is None:
                    raise SystemExit(f"Batch job not found: {args.batch_job_id}")
            else:
                job = batch_service.create_from_pending_queue(
                    db,
                    task_type="exclusive_right_extract",
                    limit=args.limit,
                    submit=args.submit_batch,
                    crawl_job_id=args.crawl_job_id,
                )
            db.commit()
            result["batch_job_id"] = job.llm_batch_job_id
            if args.import_results:
                result["import"] = batch_service.import_results(db, job, args.import_results)
                db.commit()
        if args.consolidate:
            mode = "dry_run" if args.dry_run else "rule_only_apply"
            result["consolidation"] = ExclusiveRightConsolidationService().run(
                db,
                mode=mode,
                crawl_job_id=args.crawl_job_id,
                date_from=args.date_from,
                date_to=args.date_to,
            )
            db.commit()
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
