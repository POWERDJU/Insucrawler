from __future__ import annotations

import argparse

from app.db.database import SessionLocal, engine
from app.db.migrations import upgrade_article_columns
from app.services.multi_company_extraction_cleanup_service import MultiCompanyExtractionCleanupService


def main() -> None:
    parser = argparse.ArgumentParser(description="Source-level cleanup for product records derived from multi-company articles.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", default="data/exports/multi_company_product_cleanup_plan.csv")
    args = parser.parse_args()
    upgrade_article_columns(engine)
    service = MultiCompanyExtractionCleanupService()
    with SessionLocal() as db:
        plan = service.product_cleanup_plan(db)
        service.write_plan_csv(plan, args.output)
        if args.apply:
            print("DB backup is recommended before apply. Physical product deletion will not be performed.")
            result = service.apply_product_cleanup(db)
            print(result)
        else:
            print("Dry-run complete. No DB changes were made.")
    print(f"plan_rows={len(plan)} output={args.output}")


if __name__ == "__main__":
    main()
