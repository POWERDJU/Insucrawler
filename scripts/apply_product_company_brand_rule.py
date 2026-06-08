from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.database import SessionLocal
from app.services.product_company_brand_rule_service import ProductCompanyBrandRuleService


DEFAULT_OUTPUT = ROOT / "data" / "exports" / "product_company_brand_rule_plan.csv"


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply deterministic product-name company brand attribution rules.")
    parser.add_argument("--apply", action="store_true", help="Apply safe changes to DB. Default is dry-run.")
    parser.add_argument("--product-id", type=int, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    service = ProductCompanyBrandRuleService()
    with SessionLocal() as db:
        rows = service.build_plan(db, product_id=args.product_id, limit=args.limit)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = list(asdict(rows[0]).keys()) if rows else ["product_id", "product_name", "old_company_name", "new_company_name", "action", "reason"]
        with args.output.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(asdict(row))
        summary = {"plan_count": len(rows), "applied": {}}
        if args.apply:
            summary["applied"] = service.apply_plan(db, rows)
            db.commit()
        print(f"plan_count={summary['plan_count']} applied={summary['applied']} csv={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
