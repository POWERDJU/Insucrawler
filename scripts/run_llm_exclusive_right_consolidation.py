from __future__ import annotations

import argparse
from pathlib import Path

from app.db.database import SessionLocal
from app.services.exclusive_right_llm_consolidation_service import ExclusiveRightLLMConsolidationService


def main() -> None:
    parser = argparse.ArgumentParser(description="Run optional LLM-assisted exclusive-right list-level consolidation.")
    parser.add_argument("--mode", choices=["dry-run", "apply"], default="dry-run")
    parser.add_argument("--target", default="all", choices=["all", "candidates", "selected"])
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--max-blocks", type=int, default=20)
    parser.add_argument("--plan-file", default="data/exports/exclusive_right_llm_merge_plan.csv")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        result = ExclusiveRightLLMConsolidationService().run(
            db,
            mode="dry_run" if args.mode == "dry-run" else "apply",
            target=args.target,
            limit=args.limit,
            max_blocks=args.max_blocks,
            plan_file=Path(args.plan_file),
        )
        for key, value in result.items():
            print(f"{key}: {value}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
