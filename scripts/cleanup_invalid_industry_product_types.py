from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import SessionLocal
from app.db.models import DimProduct, DimProductType, FactProductArticle
from app.services.product_type_industry_validation_service import ProductTypeIndustryValidationService


def main() -> None:
    parser = argparse.ArgumentParser(description="Cleanup products whose representative product type conflicts with insurer industry.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output", default="data/exports/invalid_industry_product_type_cleanup_plan.csv")
    args = parser.parse_args()
    if not args.dry_run and not args.apply:
        args.dry_run = True

    service = ProductTypeIndustryValidationService()
    rows = []
    with SessionLocal() as db:
        products = db.query(DimProduct).order_by(DimProduct.product_id).all()
        type_names = {row.product_type_code: row.product_type_name_ko for row in db.query(DimProductType).all()}
        for product in products:
            result = service.validate(
                insurance_type=product.insurance_type,
                primary_product_type_code=product.primary_product_type_code,
                product_name=product.normalized_product_name or product.raw_product_name,
                company_name=product.company_name_raw,
            )
            if result.valid:
                continue
            rows.append(
                {
                    "product_id": product.product_id,
                    "product_name": product.normalized_product_name or product.raw_product_name,
                    "company_name": product.company_name_raw,
                    "insurance_type": product.insurance_type,
                    "primary_product_type_code": product.primary_product_type_code,
                    "primary_product_type_name": type_names.get(product.primary_product_type_code or ""),
                    "current_status": product.product_status,
                    "proposed_status": result.proposed_status,
                    "exclusion_reason": result.exclusion_reason,
                    "related_article_count": db.query(FactProductArticle).filter(FactProductArticle.product_id == product.product_id).count(),
                    "reason": result.reason,
                }
            )
            if args.apply:
                product.product_status = result.proposed_status or service.excluded_status
                product.needs_review = True
                product.consolidation_status = result.exclusion_reason
        if args.apply:
            db.commit()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()) if rows else [
            "product_id", "product_name", "company_name", "insurance_type", "primary_product_type_code",
            "primary_product_type_name", "current_status", "proposed_status", "exclusion_reason",
            "related_article_count", "reason",
        ])
        writer.writeheader()
        writer.writerows(rows)
    print({"rows": len(rows), "output": str(output_path), "applied": bool(args.apply)})


if __name__ == "__main__":
    main()
