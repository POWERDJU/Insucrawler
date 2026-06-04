from __future__ import annotations

import argparse
import csv
from pathlib import Path

from app.db.database import SessionLocal, engine
from app.db.migrations import upgrade_article_columns
from app.services.multi_company_article_filter_service import MultiCompanyArticleFilterService


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit and flag multi-company articles.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--date-from")
    parser.add_argument("--date-to")
    parser.add_argument("--output", default="data/exports/multi_company_article_audit.csv")
    args = parser.parse_args()
    upgrade_article_columns(engine)
    service = MultiCompanyArticleFilterService()
    with SessionLocal() as db:
        rows = service.audit_articles(db, date_from=args.date_from, date_to=args.date_to, apply=args.apply)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as f:
        fieldnames = sorted({key for row in rows for key in row.keys()})
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    if args.apply:
        print("Applied article-level multi-company flags. Raw articles were preserved.")
    else:
        print("Dry-run complete. No DB changes were made.")
    print(f"rows={len(rows)} output={output}")


if __name__ == "__main__":
    main()
