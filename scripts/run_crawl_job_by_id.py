from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.crawl_job_service import CrawlJobService


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an existing crawl job by id.")
    parser.add_argument("crawl_job_id", type=int)
    args = parser.parse_args()
    CrawlJobService().run_job_by_id(args.crawl_job_id)


if __name__ == "__main__":
    main()
