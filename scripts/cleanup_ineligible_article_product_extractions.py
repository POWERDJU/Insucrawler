from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import SessionLocal
from app.services.multi_company_extraction_cleanup_service import MultiCompanyExtractionCleanupService


def main() -> None:
    parser = argparse.ArgumentParser(description="Cleanup product source records derived from ineligible articles.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output", default="data/exports/ineligible_article_product_cleanup_plan.csv")
    args = parser.parse_args()
    if not args.dry_run and not args.apply:
        args.dry_run = True
    service = MultiCompanyExtractionCleanupService()
    with SessionLocal() as db:
        plan = service.product_cleanup_plan(db)
        service.write_plan_csv(plan, args.output)
        result = service.apply_product_cleanup(db) if args.apply else {"source_records_excluded": 0, "products_marked": 0}
    print(json.dumps({"plan_rows": len(plan), "output": args.output, "applied": bool(args.apply), **result}, ensure_ascii=False))


if __name__ == "__main__":
    main()
