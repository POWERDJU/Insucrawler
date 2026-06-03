from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import SessionLocal, engine
from app.db.migrations import init_db
from app.services.crawl_job_service import CrawlJobService, env_bool


def main() -> None:
    init_db(engine)
    days_back = int(os.getenv("WEEKLY_UPDATE_DAYS_BACK", "14"))
    service = CrawlJobService()
    with SessionLocal() as db:
        kwargs = {
            "days_back": days_back,
            "include_llm_extraction": env_bool("WEEKLY_UPDATE_INCLUDE_LLM", False),
            "include_reinsurers": env_bool("WEEKLY_UPDATE_INCLUDE_REINSURERS", False),
            "include_foreign_branches": env_bool("WEEKLY_UPDATE_INCLUDE_FOREIGN_BRANCHES", False),
            "requested_by": "weekly_script",
        }
        extraction_mode = os.getenv("WEEKLY_UPDATE_EXTRACTION_MODE") or os.getenv("CRAWL_EXTRACTION_MODE")
        if extraction_mode:
            kwargs["extraction_mode"] = extraction_mode
        job = service.create_incremental(db, **kwargs)
        job_id = job.crawl_job_id
    service.run_job_by_id(job_id)
    with SessionLocal() as db:
        detail = service.get_job_detail(db, job_id)
        print(
            {
                "crawl_job_id": detail["crawl_job_id"],
                "status": detail["status"],
                "date_from": detail["date_from"],
                "date_to": detail["date_to"],
                "total_api_calls": detail["total_api_calls"],
                "total_articles_saved": detail["total_articles_saved"],
                "total_articles_duplicated": detail["total_articles_duplicated"],
                "error_message": detail["error_message"],
            }
        )


if __name__ == "__main__":
    main()
