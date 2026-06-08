from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import SessionLocal
from app.db.models import FactArticle
from app.services.article_eligibility_filter_service import ArticleEligibilityFilterService


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit article eligibility for product/exclusive-right extraction.")
    parser.add_argument("--date-from")
    parser.add_argument("--date-to")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output", default="data/exports/article_eligibility_audit.csv")
    args = parser.parse_args()
    if not args.dry_run and not args.apply:
        args.dry_run = True

    service = ArticleEligibilityFilterService()
    rows = []
    with SessionLocal() as db:
        query = db.query(FactArticle).order_by(FactArticle.article_id)
        if args.date_from:
            query = query.filter(FactArticle.pub_date >= datetime.fromisoformat(args.date_from))
        if args.date_to:
            query = query.filter(FactArticle.pub_date < datetime.fromisoformat(args.date_to) + timedelta(days=1))
        for article in query.all():
            decision = service.classify_article(db, article)
            rows.append(
                {
                    "article_id": article.article_id,
                    "pub_date": article.pub_date,
                    "title": article.title,
                    "original_url": article.original_url or article.url,
                    "eligible_for_product_extraction": decision.eligible_for_product_extraction,
                    "eligible_for_exclusive_right_extraction": decision.eligible_for_exclusive_right_extraction,
                    "exclusion_reason": decision.exclusion_reason,
                    "detected_insurer_companies": "|".join(decision.detected_insurer_companies),
                    "detected_non_insurance_financial_institutions": "|".join(decision.detected_non_insurance_financial_institutions),
                    "detected_non_insurance_products": "|".join(decision.detected_non_insurance_products),
                    "suggested_action": "exclude_source" if not decision.is_eligible else "keep",
                    "evidence": json.dumps(decision.evidence, ensure_ascii=False),
                }
            )
            if args.apply and not decision.is_eligible:
                service.mark_article(db, article, decision)
        if args.apply:
            db.commit()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "article_id", "pub_date", "title", "original_url", "eligible_for_product_extraction",
        "eligible_for_exclusive_right_extraction", "exclusion_reason", "detected_insurer_companies",
        "detected_non_insurance_financial_institutions", "detected_non_insurance_products",
        "suggested_action", "evidence",
    ]
    with output.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print({"rows": len(rows), "excluded": sum(1 for row in rows if row["suggested_action"] == "exclude_source"), "output": str(output), "applied": bool(args.apply)})


if __name__ == "__main__":
    main()
