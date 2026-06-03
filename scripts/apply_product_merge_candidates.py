from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import text

from app.db.database import SessionLocal
from app.services.product_canonicalization_service import ProductCanonicalizationService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge obvious same-article product duplicates.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=500)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    service = ProductCanonicalizationService()
    with SessionLocal() as db:
        article_ids = [
            row[0]
            for row in db.execute(
                text(
                    """
                    SELECT article_id
                    FROM fact_product_article
                    GROUP BY article_id
                    HAVING COUNT(DISTINCT product_id) > 1
                    LIMIT :limit
                    """
                ),
                {"limit": args.limit},
            ).all()
        ]
        total_decisions = 0
        for article_id in article_ids:
            if args.dry_run:
                product_count = db.execute(
                    text("SELECT COUNT(DISTINCT product_id) FROM fact_product_article WHERE article_id = :article_id"),
                    {"article_id": article_id},
                ).scalar_one()
                if product_count > 1:
                    print(f"[dry-run] article_id={article_id} has {product_count} product candidates")
                continue
            total_decisions += len(service.merge_same_article_products(db, article_id))
        if args.apply:
            db.commit()
            print(f"applied merge decisions: {total_decisions}")


if __name__ == "__main__":
    main()
