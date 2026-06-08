from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import SessionLocal
from app.db.models import DimProduct, FactArticle, FactProductArticle
from app.services.article_eligibility_filter_service import ArticleEligibilityFilterService
from app.services.product_name_validation_service import ProductNameValidationService


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output", default="data/exports/invalid_product_extractions.csv")
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    with SessionLocal() as db:
        name_validator = ProductNameValidationService()
        article_filter = ArticleEligibilityFilterService()
        products = db.query(DimProduct).filter(DimProduct.product_status.in_(["active", "provisional"])).all()
        for product in products:
            reasons: list[str] = []
            decision = name_validator.validate(product.normalized_product_name or product.raw_product_name)
            if not decision.accepted:
                reasons.append(decision.reason)
            linked_articles = (
                db.query(FactArticle)
                .join(FactProductArticle, FactProductArticle.article_id == FactArticle.article_id)
                .filter(FactProductArticle.product_id == product.product_id)
                .limit(5)
                .all()
            )
            for article in linked_articles:
                article_decision = article_filter.classify_article(db, article)
                if not article_decision.is_eligible:
                    reasons.append(article_decision.exclusion_reason or "article_ineligible")
                    break
            if not reasons:
                continue
            rows.append(
                {
                    "product_id": product.product_id,
                    "product_name": product.normalized_product_name,
                    "company_id": product.company_id,
                    "product_status": product.product_status,
                    "reasons": ";".join(sorted(set(reasons))),
                }
            )
            if args.apply:
                product.product_status = "review"
                product.needs_review = True
        if args.apply:
            db.commit()
    with output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["product_id", "product_name", "company_id", "product_status", "reasons"])
        writer.writeheader()
        writer.writerows(rows)
    print({"apply": args.apply, "count": len(rows), "output": str(output)})


if __name__ == "__main__":
    main()
