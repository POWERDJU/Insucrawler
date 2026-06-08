from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import SessionLocal
from app.db.models import DimCompany, FactArticle, FactExclusiveUseRight, FactExclusiveUseRightArticle
from app.services.exclusive_right_local_context import validate_exclusive_subject_before_save
from app.services.product_company_eligibility import is_product_news_eligible_company


def _future_month(month: str | None, article: FactArticle | None) -> bool:
    if not month or not article or not article.pub_date:
        return False
    return month > article.pub_date.strftime("%Y-%m")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output", default="data/exports/invalid_exclusive_rights.csv")
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    with SessionLocal() as db:
        rights = db.query(FactExclusiveUseRight).filter(FactExclusiveUseRight.event_status == "active").all()
        for right in rights:
            reasons: list[str] = []
            article = None
            if right.primary_article_id:
                article = db.get(FactArticle, right.primary_article_id)
            if article is None:
                link = db.query(FactExclusiveUseRightArticle).filter_by(exclusive_right_id=right.exclusive_right_id).first()
                article = db.get(FactArticle, link.article_id) if link else None
            validation = validate_exclusive_subject_before_save(
                right.subject_name,
                evidence_text=right.evidence_text,
                window_text=" ".join(part for part in [right.primary_article_title, right.evidence_text] if part),
                article_title=right.primary_article_title,
            )
            if validation.needs_review:
                reasons.append(validation.reason)
            if _future_month(right.acquired_year_month, article):
                reasons.append("exclusive_right_future_acquired_month")
            company = db.get(DimCompany, right.company_id) if right.company_id else None
            if right.company_id and not is_product_news_eligible_company(company):
                reasons.append("company_is_reinsurer_or_foreign_branch")
            if not reasons:
                continue
            rows.append(
                {
                    "exclusive_right_id": right.exclusive_right_id,
                    "subject_name": right.subject_name,
                    "company_name": right.company_name_normalized,
                    "acquired_year_month": right.acquired_year_month,
                    "reasons": ";".join(sorted(set(reasons))),
                }
            )
            if args.apply:
                right.needs_review = True
                right.event_status = "review"
        if args.apply:
            db.commit()
    with output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["exclusive_right_id", "subject_name", "company_name", "acquired_year_month", "reasons"],
        )
        writer.writeheader()
        writer.writerows(rows)
    print({"apply": args.apply, "count": len(rows), "output": str(output)})


if __name__ == "__main__":
    main()
