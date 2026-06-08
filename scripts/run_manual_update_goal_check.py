from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import SessionLocal, engine
from app.db.migrations import init_db
from app.services.crawl_job_service import CrawlJobService
from app.services.scheduled_refresh_service import ScheduledRefreshService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create or advance a manual date-range update pipeline.")
    parser.add_argument("--date-from", required=True)
    parser.add_argument("--date-to", required=True)
    parser.add_argument("--max-days", type=int, default=30)
    parser.add_argument("--run-now", action="store_true")
    parser.add_argument("--crawl-job-id", type=int, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db(engine)
    result: dict[str, object] = {}
    with SessionLocal() as db:
        if args.crawl_job_id:
            result["pipeline_step"] = ScheduledRefreshService().run_pipeline_step(db, crawl_job_id=args.crawl_job_id)
        else:
            date_from, date_to = _validate_range(args.date_from, args.date_to, args.max_days)
            job = CrawlJobService().create_manual_range(
                db,
                date_from=date_from,
                date_to=date_to,
                include_llm_extraction=True,
                extraction_mode="batch",
                include_exclusive_right_pipeline=True,
                exclusive_right_pipeline_mode="batch",
                include_reinsurers=False,
                include_foreign_branches=False,
                pipeline_mode="crawl_parse_postprocess_qwen",
                include_qwen_adjudication=True,
                qwen_priority=True,
                run_postprocess=True,
                run_consolidation=True,
                requested_by="manual_goal_check",
                requested_from="cli",
            )
            result["created_job"] = CrawlJobService.job_to_dict(job)
            if args.run_now:
                CrawlJobService().run_job_by_id(job.crawl_job_id)
                result["pipeline_step"] = ScheduledRefreshService().run_pipeline_step(db, crawl_job_id=job.crawl_job_id)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


def _validate_range(date_from: str, date_to: str, max_days: int) -> tuple[str, str]:
    start = date.fromisoformat(date_from)
    end = date.fromisoformat(date_to)
    today = date.today()
    if start > today:
        raise ValueError("date_from cannot be in the future")
    if end > today:
        end = today
    if end < start:
        raise ValueError("date_to must be greater than or equal to date_from")
    if (end - start).days > max_days:
        raise ValueError(f"manual range cannot exceed {max_days} days")
    return start.isoformat(), end.isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
