from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import SessionLocal, engine
from app.db.migrations import init_db
from app.services.full_data_review_service import FullDataReviewService, FullReviewRequestData


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run full data rule+Qwen review goal check.")
    parser.add_argument("--date-from", default="2025-01-01")
    parser.add_argument("--date-to", default="2026-05-31")
    parser.add_argument("--crawl-job-id", type=int, default=None)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--skip-rule-review", action="store_true")
    parser.add_argument("--skip-qwen", action="store_true")
    parser.add_argument("--max-products", type=int, default=100)
    parser.add_argument("--max-exclusive", type=int, default=50)
    parser.add_argument("--exhaustive-qwen", action="store_true", help="Review every in-scope active row, not only risky candidates.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db(engine)
    with SessionLocal() as db:
        result = FullDataReviewService().run(
            db,
            FullReviewRequestData(
                mode="apply" if args.apply else "dry_run",
                review_scope="all",
                date_from=args.date_from,
                date_to=args.date_to,
                crawl_job_id=args.crawl_job_id,
                include_rule_review=not args.skip_rule_review,
                include_qwen=not args.skip_qwen,
                qwen_priority=True,
                max_products=args.max_products,
                max_exclusive=args.max_exclusive,
                qwen_exhaustive=args.exhaustive_qwen,
            ),
        )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0 if result.get("status") == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
