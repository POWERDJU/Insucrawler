from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import desc

from app.db.database import SessionLocal, engine
from app.db.migrations import init_db
from app.db.models import FactCrawlJob
from app.services.scheduled_refresh_service import ScheduledRefreshService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect or advance scheduled refresh pipeline.")
    parser.add_argument("--run-due", action="store_true", help="Create a due scheduled refresh job if today/hour matches config.")
    parser.add_argument("--pipeline-step", action="store_true", help="Advance one crawl/batch/postprocess/Qwen step.")
    parser.add_argument("--crawl-job-id", type=int, default=None)
    parser.add_argument("--now", default=None, help="Optional ISO datetime for due/date-range checks.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db(engine)
    service = ScheduledRefreshService()
    now = datetime.fromisoformat(args.now) if args.now else None
    result: dict[str, object] = {}
    with SessionLocal() as db:
        result["status"] = service.status(db, now=now)
        if args.run_due:
            result["run_due"] = service.run_due_once(db, now=now)
        if args.pipeline_step:
            crawl_job_id = args.crawl_job_id or _latest_pipeline_job_id(db)
            if crawl_job_id:
                result["pipeline_step"] = service.run_pipeline_step(db, crawl_job_id=crawl_job_id)
            else:
                result["pipeline_step"] = {"status": "skipped", "reason": "no pipeline job"}
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


def _latest_pipeline_job_id(db) -> int | None:
    job = (
        db.query(FactCrawlJob)
        .filter(
            FactCrawlJob.job_type.in_(["scheduled_refresh", "manual_range", "incremental"]),
            FactCrawlJob.pipeline_mode != "crawl_only",
        )
        .order_by(desc(FactCrawlJob.crawl_job_id))
        .first()
    )
    return job.crawl_job_id if job else None


if __name__ == "__main__":
    raise SystemExit(main())
