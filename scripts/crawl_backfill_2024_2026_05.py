from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import SessionLocal, engine
from app.db.migrations import init_db
from app.services.crawl_job_service import CrawlJobService


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill 2024-01 through 2026-05 insurance product news")
    parser.add_argument("--include-llm", action="store_true")
    parser.add_argument("--extraction-mode", choices=["none", "screening_only", "enqueue_only", "realtime", "batch"], default=None)
    parser.add_argument("--include-reinsurers", action="store_true")
    parser.add_argument("--include-foreign-branches", action="store_true")
    args = parser.parse_args()

    init_db(engine)
    service = CrawlJobService()
    with SessionLocal() as db:
        job = service.create_backfill_2024_2026_05(
            db,
            include_llm_extraction=args.include_llm,
            extraction_mode=args.extraction_mode,
            include_reinsurers=args.include_reinsurers,
            include_foreign_branches=args.include_foreign_branches,
            requested_by="cli",
        )
        job_id = job.crawl_job_id
    service.run_job_by_id(job_id)
    with SessionLocal() as db:
        print(service.get_job_detail(db, job_id))


if __name__ == "__main__":
    main()
