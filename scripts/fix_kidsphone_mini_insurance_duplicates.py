from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import text

from app.db.database import SessionLocal
from app.db.models import DimProduct
from app.services.product_canonicalization_service import ProductNamePlan
from app.services.product_canonicalization_service import ProductCanonicalizationService


KEYWORDS = ["키즈폰", "어린이", "미니", "키즈케어", "LG유플러스"]
CONTEXT_KEYWORDS = ["키즈폰", "키즈케어", "LG유플러스"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report or merge kidsphone/mini-insurance duplicate candidates.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    service = ProductCanonicalizationService()
    pattern_sql = " OR ".join(
        [
            "p.normalized_product_name LIKE :kw_{idx} OR p.raw_product_name LIKE :kw_{idx} OR a.title LIKE :kw_{idx}".format(idx=idx)
            for idx, _ in enumerate(KEYWORDS)
        ]
    )
    params = {f"kw_{idx}": f"%{keyword}%" for idx, keyword in enumerate(KEYWORDS)}
    with SessionLocal() as db:
        article_rows = db.execute(
            text(
                f"""
                SELECT DISTINCT pa.article_id
                FROM fact_product_article pa
                JOIN dim_product p ON p.product_id = pa.product_id
                JOIN fact_article a ON a.article_id = pa.article_id
                WHERE ({pattern_sql})
                  AND COALESCE(p.product_status, 'active') != 'merged'
                """
            ),
            params,
        ).mappings().all()
        for row in article_rows:
            article_id = row["article_id"]
            if args.dry_run:
                names = db.execute(
                    text(
                        """
                        SELECT p.product_id, p.normalized_product_name
                        FROM fact_product_article pa
                        JOIN dim_product p ON p.product_id = pa.product_id
                        WHERE pa.article_id = :article_id
                          AND COALESCE(p.product_status, 'active') != 'merged'
                        ORDER BY p.product_id
                        """
                    ),
                    {"article_id": article_id},
                ).mappings().all()
                print(f"[dry-run] article_id={article_id}: " + " | ".join(f"{item['product_id']}:{item['normalized_product_name']}" for item in names))
        keyword_conditions = " OR ".join(
            [
                f"p.normalized_product_name LIKE :kw_{idx} OR p.raw_product_name LIKE :kw_{idx} OR a.title LIKE :kw_{idx} OR a.description LIKE :kw_{idx}"
                for idx, _ in enumerate(KEYWORDS)
            ]
        )
        context_conditions = " OR ".join(
            [
                f"p.normalized_product_name LIKE :ctx_{idx} OR p.raw_product_name LIKE :ctx_{idx} OR a.title LIKE :ctx_{idx} OR a.description LIKE :ctx_{idx}"
                for idx, _ in enumerate(CONTEXT_KEYWORDS)
            ]
        )
        params_with_context = {
            **params,
            **{f"ctx_{idx}": f"%{keyword}%" for idx, keyword in enumerate(CONTEXT_KEYWORDS)},
        }
        product_rows = db.execute(
            text(
                f"""
                SELECT DISTINCT p.product_id, p.company_id, p.normalized_product_name
                FROM dim_product p
                LEFT JOIN fact_product_article pa ON pa.product_id = p.product_id
                LEFT JOIN fact_article a ON a.article_id = pa.article_id
                WHERE ({keyword_conditions})
                  AND ({context_conditions})
                  AND p.company_id IS NOT NULL
                  AND COALESCE(p.product_status, 'active') != 'merged'
                ORDER BY p.company_id, p.product_id
                """
            ),
            params_with_context,
        ).mappings().all()
        groups: dict[int, list[dict]] = {}
        for row in product_rows:
            groups.setdefault(row["company_id"], []).append(dict(row))
        for company_id, items in groups.items():
            if len(items) <= 1:
                continue
            plans = [
                ProductNamePlan(
                    index=idx,
                    raw_name=item["normalized_product_name"],
                    canonical_name=service.canonical_name_from_raw(item["normalized_product_name"]),
                    candidate_type=service.classify_product_name_candidate(item["normalized_product_name"]),
                )
                for idx, item in enumerate(items)
            ]
            canonical_plan = service.select_canonical_plan(plans)
            canonical_item = items[canonical_plan.index]
            if args.dry_run:
                print(
                    f"[dry-run] company_id={company_id} canonical={canonical_item['product_id']}:{canonical_item['normalized_product_name']} "
                    + "duplicates="
                    + " | ".join(f"{item['product_id']}:{item['normalized_product_name']}" for item in items if item["product_id"] != canonical_item["product_id"])
                )
                continue
            canonical = db.get(DimProduct, canonical_item["product_id"])
            if not canonical:
                continue
            for item in items:
                if item["product_id"] == canonical.product_id:
                    continue
                duplicate = db.get(DimProduct, item["product_id"])
                if not duplicate:
                    continue
                article_ids = [
                    row[0]
                    for row in db.execute(
                        text(
                            """
                            SELECT DISTINCT article_id
                            FROM fact_product_article
                            WHERE product_id IN (:canonical_id, :duplicate_id)
                            """
                        ),
                        {"canonical_id": canonical.product_id, "duplicate_id": duplicate.product_id},
                    ).all()
                ]
                service.merge_products(
                    db,
                    canonical,
                    duplicate,
                    decision_source="deterministic_context_cluster",
                    confidence=0.88,
                    reason="kidsphone/mini insurance contextual aliases",
                    evidence_article_ids=article_ids,
                )
                print(f"merged duplicate={duplicate.product_id}:{duplicate.normalized_product_name} -> canonical={canonical.product_id}:{canonical.normalized_product_name}")
        if args.apply:
            db.commit()


if __name__ == "__main__":
    main()
