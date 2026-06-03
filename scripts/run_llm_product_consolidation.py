from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.database import SessionLocal
from app.services.product_full_list_consolidation_service import ProductFullListConsolidationService


def main() -> None:
    parser = argparse.ArgumentParser(description="Run optional LLM-assisted company full-list product consolidation.")
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--target", default="all", choices=["all", "company", "selected", "candidates", "all_provisional", "new_since_last_job"])
    parser.add_argument("--company-name", default=None)
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--max-companies", type=int, default=None)
    parser.add_argument("--max-blocks", type=int, default=20)
    parser.add_argument("--model", default=None)
    parser.add_argument("--output", "--plan-file", dest="plan_file", default="data/exports/product_full_list_llm_merge_plan.csv")
    args = parser.parse_args()

    if args.target == "company" and not args.company_name:
        parser.error("--target company requires --company-name")
    if args.model:
        import os

        os.environ["PRODUCT_LLM_CONSOLIDATION_MODEL"] = args.model

    db = SessionLocal()
    try:
        result = ProductFullListConsolidationService().run_full_list_consolidation(
            db,
            mode="dry_run" if args.mode == "dry-run" else "apply",
            target="all" if args.target == "company" else args.target,
            company_name=args.company_name,
            limit=args.limit,
            max_companies=args.max_companies,
            max_blocks=args.max_blocks,
            plan_file=Path(args.plan_file),
        )
        for key, value in result.items():
            print(f"{key}: {value}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
