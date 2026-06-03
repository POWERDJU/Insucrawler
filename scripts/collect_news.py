from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import SessionLocal
from app.services.collect_service import CollectService


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query-group", default="new_product")
    parser.add_argument("--days-back", type=int, default=30)
    parser.add_argument("--max-results-per-query", type=int, default=100)
    parser.add_argument("--include-company-queries", action="store_true")
    parser.add_argument("--include-reinsurers", action="store_true")
    parser.add_argument("--include-foreign-branches", action="store_true")
    parser.add_argument("--exclude-changed-companies", action="store_true")
    parser.add_argument("--exclude-short-term-insurers", action="store_true")
    args = parser.parse_args()
    with SessionLocal() as db:
        result = CollectService().collect_naver(
            db,
            args.query_group,
            args.days_back,
            args.max_results_per_query,
            include_company_queries=args.include_company_queries,
            include_reinsurers=args.include_reinsurers,
            include_foreign_branches=args.include_foreign_branches,
            include_changed_companies=not args.exclude_changed_companies,
            include_short_term_insurers=not args.exclude_short_term_insurers,
        )
    print(result)


if __name__ == "__main__":
    main()
