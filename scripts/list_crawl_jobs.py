from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import SessionLocal, engine
from app.db.migrations import init_db
from app.services.crawl_job_service import CrawlJobService


def main() -> None:
    parser = argparse.ArgumentParser(description="List recent crawl jobs")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    init_db(engine)
    with SessionLocal() as db:
        for job in CrawlJobService().list_jobs(db, limit=args.limit):
            print(
                f"{job['crawl_job_id']}\t{job['status']}\t{job['job_name']}\t"
                f"{job['date_from']}~{job['date_to']}\t"
                f"tasks={job['completed_tasks']}/{job['total_tasks']}\t"
                f"saved={job['total_articles_saved']}\tdup={job['total_articles_duplicated']}\tapi={job['total_api_calls']}"
            )


if __name__ == "__main__":
    main()
