from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import SessionLocal
from app.db.models import DimCompany, DimProduct, FactExclusiveUseRight
from app.services.product_company_eligibility import is_product_news_eligible_company


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output", default="data/exports/reinsurer_attribution_audit.csv")
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    with SessionLocal() as db:
        for product in db.query(DimProduct).filter(DimProduct.company_id.isnot(None)).all():
            company = db.get(DimCompany, product.company_id)
            if is_product_news_eligible_company(company):
                continue
            rows.append(
                {
                    "entity_type": "product",
                    "entity_id": product.product_id,
                    "name": product.normalized_product_name,
                    "company": company.company_name_normalized if company else product.company_name_raw,
                    "action": "mark_review_ineligible_company",
                }
            )
            if args.apply:
                product.needs_review = True
                product.product_status = "review_ineligible_company"
        for right in db.query(FactExclusiveUseRight).filter(FactExclusiveUseRight.company_id.isnot(None)).all():
            company = db.get(DimCompany, right.company_id)
            if is_product_news_eligible_company(company):
                continue
            rows.append(
                {
                    "entity_type": "exclusive_right",
                    "entity_id": right.exclusive_right_id,
                    "name": right.subject_name,
                    "company": company.company_name_normalized if company else right.company_name_normalized,
                    "action": "mark_review_ineligible_company",
                }
            )
            if args.apply:
                right.needs_review = True
                right.event_status = "review"
        if args.apply:
            db.commit()
    with output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["entity_type", "entity_id", "name", "company", "action"])
        writer.writeheader()
        writer.writerows(rows)
    print({"apply": args.apply, "count": len(rows), "output": str(output)})


if __name__ == "__main__":
    main()
