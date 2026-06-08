from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.database import SessionLocal
from app.db.models import DimProduct, FactProductMajorCoverage
from app.services.coverage_dedupe_service import group_duplicate_coverages


DEFAULT_OUTPUT = Path("data/exports/major_coverage_duplicate_audit.csv")


def build_rows(product_id: int | None = None) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with SessionLocal() as db:
        query = db.query(DimProduct)
        if product_id:
            query = query.filter(DimProduct.product_id == product_id)
        for product in query.order_by(DimProduct.product_id).all():
            coverages = [
                {column.name: getattr(item, column.name) for column in item.__table__.columns}
                for item in db.query(FactProductMajorCoverage)
                .filter(FactProductMajorCoverage.product_id == product.product_id)
                .order_by(FactProductMajorCoverage.display_order, FactProductMajorCoverage.coverage_id)
                .all()
            ]
            for group in group_duplicate_coverages(coverages):
                if group.source_count <= 1:
                    continue
                canonical = group.canonical_coverage
                members = [item for item in coverages if item.get("coverage_id") == canonical.get("coverage_id") or item.get("coverage_id") in group.duplicate_coverage_ids]
                rows.append(
                    {
                        "product_id": str(product.product_id),
                        "product_name": product.normalized_product_name or product.raw_product_name or "",
                        "coverage_group_key": group.canonical_key,
                        "canonical_coverage_name": canonical.get("coverage_name_normalized") or canonical.get("coverage_name_raw") or "",
                        "duplicate_coverage_ids": ",".join(str(item) for item in group.duplicate_coverage_ids),
                        "duplicate_coverage_names": " | ".join(
                            str(item.get("coverage_name_normalized") or item.get("coverage_name_raw") or "")
                            for item in members
                        ),
                        "family": group.canonical_key.split("|", 1)[0].replace("family:", ""),
                        "merge_reason": group.merge_reason,
                        "action": "display_dedupe_only",
                        "review_reason": "",
                    }
                )
    return rows


def write_csv(rows: list[dict[str, str]], path: Path = DEFAULT_OUTPUT) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "product_id",
        "product_name",
        "coverage_group_key",
        "canonical_coverage_name",
        "duplicate_coverage_ids",
        "duplicate_coverage_names",
        "family",
        "merge_reason",
        "action",
        "review_reason",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--product-id", type=int)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    rows = build_rows(args.product_id)
    path = write_csv(rows, args.output)
    print({"duplicate_groups": len(rows), "output": str(path), "dry_run": args.dry_run})


if __name__ == "__main__":
    main()
