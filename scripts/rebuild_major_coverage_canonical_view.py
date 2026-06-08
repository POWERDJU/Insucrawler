from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_major_coverage_duplicates import DEFAULT_OUTPUT, build_rows, write_csv


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--product-id", type=int)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    rows = build_rows(args.product_id)
    path = write_csv(rows, args.output)
    print(
        {
            "status": "planned",
            "duplicate_groups": len(rows),
            "output": str(path),
            "raw_rows_deleted": 0,
            "apply": bool(args.apply),
            "note": "No canonical table is maintained; API/export use runtime deterministic dedupe.",
        }
    )


if __name__ == "__main__":
    main()
