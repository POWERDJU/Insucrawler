from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.database import SessionLocal
from app.db.models import DimProduct
from app.db import repository


DEFAULT_OUTPUT = Path("data/exports/product_release_month_rebuild_plan.csv")


def build_plan(apply: bool = False, output: Path = DEFAULT_OUTPUT, *, recalculate_explicit: bool = False) -> list[dict]:
    output.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    with SessionLocal() as db:
        products = db.query(DimProduct).filter(DimProduct.product_status != "merged").order_by(DimProduct.product_id).all()
        for product in products:
            before_month = product.release_year_month
            before_basis = product.release_year_month_basis
            if recalculate_explicit and product.release_year_month_basis == "explicit_in_article":
                product.release_year_month = None
                product.release_year_month_basis = "unknown"
                product.release_year_month_source_article_id = None
                product.release_year_month_source_type = None
            changed = repository.update_release_month_if_unknown(db, product.product_id)
            after_month = product.release_year_month
            after_basis = product.release_year_month_basis
            if changed or before_month != after_month or before_basis != after_basis:
                rows.append(
                    {
                        "product_id": product.product_id,
                        "product_name": product.normalized_product_name,
                        "before_release_year_month": before_month,
                        "before_basis": before_basis,
                        "after_release_year_month": after_month,
                        "after_basis": after_basis,
                        "source_article_id": product.release_year_month_source_article_id,
                        "action": "apply" if apply else "dry_run",
                    }
                )
        if apply:
            db.commit()
        else:
            db.rollback()
    with output.open("w", encoding="utf-8-sig", newline="") as f:
        fieldnames = [
            "product_id",
            "product_name",
            "before_release_year_month",
            "before_basis",
            "after_release_year_month",
            "after_basis",
            "source_article_id",
            "action",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild product release months from explicit article text and related article dates.")
    parser.add_argument("--apply", action="store_true", help="Apply changes. Default is dry-run.")
    parser.add_argument("--recalculate-explicit", action="store_true", help="Recalculate existing explicit_in_article rows. Manual and external rows remain protected.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()
    rows = build_plan(apply=args.apply, output=Path(args.output), recalculate_explicit=args.recalculate_explicit)
    print(f"{'applied' if args.apply else 'dry-run'} rows={len(rows)} output={args.output}")


if __name__ == "__main__":
    main()
