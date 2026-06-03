from __future__ import annotations

import csv
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import text

from app.db.database import SessionLocal
from app.services.product_canonicalization_service import ProductCanonicalizationService


EXPORT_PATH = Path("data/exports/product_merge_candidates.csv")


def main() -> None:
    EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    service = ProductCanonicalizationService()
    with SessionLocal() as db, EXPORT_PATH.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "candidate_group_id",
                "product_id",
                "product_name",
                "company_name",
                "partner_company",
                "article_url",
                "article_title",
                "product_core_key",
                "reason",
                "suggested_canonical_name",
                "suggested_action",
            ],
        )
        writer.writeheader()
        article_ids = [
            row[0]
            for row in db.execute(
                text(
                    """
                    SELECT article_id
                    FROM fact_product_article
                    GROUP BY article_id
                    HAVING COUNT(DISTINCT product_id) > 1
                    """
                )
            ).all()
        ]
        group_id = 0
        for article_id in article_ids:
            rows = db.execute(
                text(
                    """
                    SELECT p.product_id, p.normalized_product_name, p.product_core_key,
                           p.partner_company_name, c.company_name_normalized AS company_name,
                           a.title, COALESCE(a.original_url, a.url) AS article_url
                    FROM fact_product_article pa
                    JOIN dim_product p ON p.product_id = pa.product_id
                    LEFT JOIN dim_company c ON c.company_id = p.company_id
                    JOIN fact_article a ON a.article_id = pa.article_id
                    WHERE pa.article_id = :article_id
                      AND COALESCE(p.product_status, 'active') != 'merged'
                    ORDER BY p.product_id
                    """
                ),
                {"article_id": article_id},
            ).mappings().all()
            plans = [
                service.classify_product_name_candidate(row["normalized_product_name"], row["title"] or "")
                for row in rows
            ]
            if len(rows) <= 1:
                continue
            group_id += 1
            suggested = max((row["normalized_product_name"] for row in rows), key=lambda value: len(value or ""), default="")
            for row, candidate_type in zip(rows, plans):
                writer.writerow(
                    {
                        "candidate_group_id": group_id,
                        "product_id": row["product_id"],
                        "product_name": row["normalized_product_name"],
                        "company_name": row["company_name"],
                        "partner_company": row["partner_company_name"],
                        "article_url": row["article_url"],
                        "article_title": row["title"],
                        "product_core_key": row["product_core_key"],
                        "reason": f"same article duplicate candidate; candidate_type={candidate_type}",
                        "suggested_canonical_name": suggested,
                        "suggested_action": "review_merge",
                    }
                )
    print(f"wrote {EXPORT_PATH}")


if __name__ == "__main__":
    main()
