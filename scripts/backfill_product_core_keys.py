from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import SessionLocal, engine
from app.db.migrations import init_db
from app.db.models import (
    DimCompany,
    DimProduct,
    FactCoverageEvidence,
    FactProductArticle,
    FactProductMajorCoverage,
    FactProductNarrativeInsight,
    FactProductStructuredFeature,
    FactSalesMetricStructured,
)
from app.db.repository import company_aliases_for_company, record_product_alias
from app.normalizers.product_name_normalizer import (
    build_product_identity_key,
    normalize_product_name,
    normalize_product_name_core,
    product_core_key_candidates,
    product_search_key,
)
from app.utils.dates import utcnow


PROTECTED_BASIS_ORDER = {
    "manual": 0,
    "explicit_in_article": 1,
    "external_grounded_source": 2,
    "earliest_related_article_month": 3,
    "inferred_from_article_date": 4,
    "first_seen_only": 5,
    "unknown": 6,
    None: 7,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill product core keys and merge exact duplicate products.")
    parser.add_argument("--apply", action="store_true", help="Apply exact same-company/core-key merges. Without this, only emits candidates.")
    args = parser.parse_args()

    init_db(engine)
    with SessionLocal() as db:
        products = db.query(DimProduct).order_by(DimProduct.product_id).all()
        for product in products:
            company = db.get(DimCompany, product.company_id) if product.company_id else None
            aliases = company_aliases_for_company(company)
            base_name = product.normalized_product_name or product.raw_product_name
            normalized = normalize_product_name(base_name, aliases)
            core_key = normalize_product_name_core(base_name, aliases)
            product.product_core_key = core_key
            product.product_identity_key = build_product_identity_key(product.company_id, base_name, aliases)
            record_product_alias(
                db,
                product,
                product.raw_product_name,
                normalized,
                core_key,
                article_id=None,
                source_type="backfill",
            )
        db.flush()

        candidates = collect_merge_candidates(db)
        export_path = write_candidates(candidates)
        merged = 0
        if args.apply:
            for items in candidates:
                canonical = choose_canonical(items)
                for duplicate in sorted((item for item in items if item.product_id != canonical.product_id), key=lambda item: item.product_id):
                    merge_product(db, canonical, duplicate)
                    merged += 1
            db.flush()

        for product in db.query(DimProduct).order_by(DimProduct.product_id).all():
            company = db.get(DimCompany, product.company_id) if product.company_id else None
            aliases = company_aliases_for_company(company)
            base_name = product.normalized_product_name or product.raw_product_name
            normalized = normalize_product_name(base_name, aliases)
            product.normalized_product_name = normalized or product.normalized_product_name
            product.product_core_key = normalize_product_name_core(base_name, aliases)
            product.product_identity_key = build_product_identity_key(product.company_id, base_name, aliases)
            product.product_search_key = product_search_key(product.normalized_product_name, company.company_name_normalized if company else None)

        db.commit()
        print({"products": len(products), "candidate_groups": len(candidates), "merged_products": merged, "candidate_csv": str(export_path)})


def choose_canonical(items: list[DimProduct]) -> DimProduct:
    return sorted(
        items,
        key=lambda item: (
            PROTECTED_BASIS_ORDER.get(item.release_year_month_basis, 6),
            0 if item.release_year_month else 1,
            item.product_id,
        ),
    )[0]


def collect_merge_candidates(db) -> list[list[DimProduct]]:
    products = db.query(DimProduct).filter(DimProduct.company_id.isnot(None)).all()
    groups: dict[tuple[int, str], list[DimProduct]] = defaultdict(list)
    for product in products:
        company = db.get(DimCompany, product.company_id) if product.company_id else None
        aliases = company_aliases_for_company(company)
        keys = product_core_key_candidates(product.normalized_product_name or product.raw_product_name, aliases)
        if product.product_core_key:
            keys.append(product.product_core_key)
        for key in dict.fromkeys(item for item in keys if item):
            groups[(product.company_id, key)].append(product)
        if company:
            normalized = normalize_product_name(product.normalized_product_name or product.raw_product_name, aliases)
            search_key = product_search_key(normalized, company.company_name_normalized)
            if search_key:
                groups[(product.company_id, f"search:{search_key}")].append(product)

    product_ids = {product.product_id: product for product in products}
    parent = {product_id: product_id for product_id in product_ids}

    def find(product_id: int) -> int:
        while parent[product_id] != product_id:
            parent[product_id] = parent[parent[product_id]]
            product_id = parent[product_id]
        return product_id

    def union(left: int, right: int) -> None:
        root_left = find(left)
        root_right = find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    for items in groups.values():
        if len(items) <= 1:
            continue
        first = items[0].product_id
        for item in items[1:]:
            union(first, item.product_id)

    components: dict[int, list[DimProduct]] = defaultdict(list)
    for product_id, product in product_ids.items():
        components[find(product_id)].append(product)
    return [items for items in components.values() if len(items) > 1]


def merge_product(db, canonical: DimProduct, duplicate: DimProduct) -> None:
    if not canonical.release_year_month or PROTECTED_BASIS_ORDER.get(duplicate.release_year_month_basis, 6) < PROTECTED_BASIS_ORDER.get(canonical.release_year_month_basis, 6):
        canonical.release_year_month = duplicate.release_year_month or canonical.release_year_month
        canonical.release_year_month_basis = duplicate.release_year_month_basis or canonical.release_year_month_basis
        canonical.release_year_month_source_article_id = duplicate.release_year_month_source_article_id or canonical.release_year_month_source_article_id
        canonical.release_year_month_source_type = duplicate.release_year_month_source_type or canonical.release_year_month_source_type
        canonical.release_year_month_inferred_at = duplicate.release_year_month_inferred_at or canonical.release_year_month_inferred_at
    canonical.confidence_total = max(float(canonical.confidence_total or 0), float(duplicate.confidence_total or 0))
    canonical.needs_review = bool(canonical.needs_review or duplicate.needs_review)
    if not canonical.product_category_summary and duplicate.product_category_summary:
        canonical.product_category_summary = duplicate.product_category_summary

    for link in db.query(FactProductArticle).filter(FactProductArticle.product_id == duplicate.product_id).all():
        exists = (
            db.query(FactProductArticle)
            .filter(FactProductArticle.product_id == canonical.product_id, FactProductArticle.article_id == link.article_id)
            .first()
        )
        if exists:
            db.delete(link)
        else:
            link.product_id = canonical.product_id

    for model in [
        FactProductStructuredFeature,
        FactProductNarrativeInsight,
        FactProductMajorCoverage,
        FactSalesMetricStructured,
        FactCoverageEvidence,
    ]:
        db.query(model).filter(model.product_id == duplicate.product_id).update({"product_id": canonical.product_id}, synchronize_session=False)

    db.execute(text("UPDATE dim_product_alias SET product_id = :canonical WHERE product_id = :duplicate"), {"canonical": canonical.product_id, "duplicate": duplicate.product_id})
    db.delete(duplicate)


def write_candidates(candidates: list[list[DimProduct]]) -> Path:
    export_dir = Path("data/exports")
    export_dir.mkdir(parents=True, exist_ok=True)
    path = export_dir / f"product_merge_candidates_{utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["company_id", "product_core_key", "product_id", "normalized_product_name", "raw_product_name", "release_year_month", "release_year_month_basis"])
        for items in candidates:
            for item in sorted(items, key=lambda product: product.product_id):
                writer.writerow([
                    item.company_id,
                    item.product_core_key,
                    item.product_id,
                    item.normalized_product_name,
                    item.raw_product_name,
                    item.release_year_month,
                    item.release_year_month_basis,
                ])
    return path


if __name__ == "__main__":
    main()
