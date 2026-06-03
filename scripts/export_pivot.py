from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import SessionLocal
from app.services.pivot_service import PivotService


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preset", default="product_type_by_month")
    parser.add_argument("--format", choices=["csv", "xlsx"], default="csv")
    args = parser.parse_args()
    service = PivotService()
    preset = next((item for item in service.presets() if item["name"] == args.preset), None)
    if not preset:
        raise SystemExit(f"Unknown preset: {args.preset}")
    with SessionLocal() as db:
        result = service.run_pivot(
            db,
            base=preset["base"],
            classification_mode="primary_only",
            rows=preset.get("rows", []),
            columns=preset.get("columns", []),
            filters={},
            metrics=preset.get("metrics", []),
            include_review=False,
            min_confidence=None,
        )
    suffix = "xlsx" if args.format == "xlsx" else "csv"
    path = f"data/exports/{args.preset}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.{suffix}"
    print({"path": str(service.export(result, path, suffix)), "rows": len(result["records"])})


if __name__ == "__main__":
    main()
