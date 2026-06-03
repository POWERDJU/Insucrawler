from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.database import SessionLocal
from app.services.product_duplicate_guard_service import ProductDuplicateGuardService


def main() -> None:
    parser = argparse.ArgumentParser(description="Check remaining canonical product duplicate risk without LLM calls.")
    parser.add_argument("--target", default="all", choices=["all"])
    parser.add_argument("--company-name", default=None)
    parser.add_argument("--company-id", type=int, default=None)
    parser.add_argument("--output", default="data/exports/product_duplicate_check.csv")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        service = ProductDuplicateGuardService()
        groups = service.find_duplicate_family_groups(
            db,
            filters={"company_id": args.company_id, "company_name": args.company_name},
        )
        path = service.export_groups_csv(groups, Path(args.output))
        summary = service.summarize_duplicate_risk(groups)
        summary["csv_path"] = str(path)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
