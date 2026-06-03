from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import repository
from app.db.database import SessionLocal, engine
from app.db.migrations import init_db
from app.db.models import DimProduct, DimProductAlias, FactArticle


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill fact_product_observation from products and aliases.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    init_db(engine)
    created = 0
    with SessionLocal() as db:
        for product in db.query(DimProduct).order_by(DimProduct.product_id).all():
            if not args.dry_run:
                repository.record_product_observation(
                    db,
                    product=product,
                    raw_product_name=product.raw_product_name,
                    normalized_product_name_candidate=product.normalized_product_name,
                    product_core_key=product.product_core_key,
                    company_name_raw=product.company_name_raw,
                    partner_company_name=product.partner_company_name,
                    product_type_code=product.primary_product_type_code,
                    release_year_month=product.release_year_month,
                    observation_context_text=product.partner_context_summary,
                    candidate_type="official_name" if product.product_status == "active" else "unknown",
                    confidence=float(product.confidence_total or 0.0),
                )
            created += 1
        for alias in db.query(DimProductAlias).order_by(DimProductAlias.product_alias_id).all():
            product = db.get(DimProduct, alias.product_id)
            article = db.get(FactArticle, alias.article_id) if alias.article_id else None
            if not product:
                continue
            if not args.dry_run:
                repository.record_product_observation(
                    db,
                    product=product,
                    article=article,
                    raw_product_name=alias.raw_product_name,
                    normalized_product_name_candidate=alias.normalized_product_name_candidate,
                    product_core_key=alias.product_core_key,
                    company_name_raw=product.company_name_raw,
                    partner_company_name=product.partner_company_name,
                    product_type_code=product.primary_product_type_code,
                    release_year_month=product.release_year_month,
                    candidate_type=alias.source_type or "unknown",
                    confidence=float(product.confidence_total or 0.0),
                )
            created += 1
        if not args.dry_run:
            db.commit()
    print(json.dumps({"dry_run": args.dry_run, "observations": created}, ensure_ascii=False))


if __name__ == "__main__":
    main()
