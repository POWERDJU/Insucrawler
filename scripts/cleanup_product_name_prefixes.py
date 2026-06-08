from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db import repository
from app.db.database import SessionLocal
from app.db.models import DimCompany, DimProduct
from app.normalizers.company_normalizer import CompanyNormalizer
from app.normalizers.product_name_normalizer import (
    build_product_identity_key,
    clean_product_name_candidate_result,
    normalize_product_name,
    normalize_product_name_core,
    product_core_key_candidates,
    product_search_key,
    validate_product_name_before_save,
)
from app.services.product_canonicalization_service import ProductCanonicalizationService


OUTPUT = Path("data/exports/product_name_prefix_cleanup_plan.csv")


def _company_aliases(company_name: str | None) -> list[str]:
    if not company_name:
        return []
    return [company_name, *CompanyNormalizer().known_aliases(company_name)]


def _company_name(db, product: DimProduct) -> str | None:
    if not product.company_id:
        return None
    company = db.get(DimCompany, product.company_id)
    return company.company_name_normalized if company else None


def build_plan(db) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for product in db.query(DimProduct).order_by(DimProduct.product_id).all():
        if product.product_status in {"merged", "rejected"}:
            continue
        company_name = _company_name(db, product)
        aliases = _company_aliases(company_name)
        result = clean_product_name_candidate_result(product.normalized_product_name or product.raw_product_name, aliases)
        if not result.removed_prefixes:
            continue
        validation = validate_product_name_before_save(
            result.cleaned_name,
            evidence_text=result.cleaned_name,
            context_text=result.cleaned_name,
            company_aliases=aliases,
        )
        action = "update_cleaned_name" if validation.accepted else "reject_generic_after_prefix_cleanup"
        existing = None
        if validation.accepted:
            normalized = normalize_product_name(result.cleaned_name, aliases)
            existing = (
                db.query(DimProduct)
                .filter(
                    DimProduct.company_id == product.company_id,
                    DimProduct.product_search_key == product_search_key(normalized, company_name),
                    DimProduct.product_id != product.product_id,
                )
                .first()
            )
            if existing:
                action = "merge_into_existing_cleaned_product"
        rows.append(
            {
                "product_id": product.product_id,
                "company_name": company_name,
                "old_normalized_product_name": product.normalized_product_name,
                "old_raw_product_name": product.raw_product_name,
                "cleaned_product_name": result.cleaned_name,
                "removed_prefixes": "|".join(result.removed_prefixes),
                "current_status": product.product_status,
                "suggested_action": action,
                "target_product_id": existing.product_id if existing else "",
                "reason": validation.reason or result.reason,
            }
        )
    return rows


def write_plan(rows: list[dict[str, object]]) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "product_id",
        "company_name",
        "old_normalized_product_name",
        "old_raw_product_name",
        "cleaned_product_name",
        "removed_prefixes",
        "current_status",
        "suggested_action",
        "target_product_id",
        "reason",
    ]
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def apply_plan(db, rows: list[dict[str, object]]) -> dict[str, int]:
    updated = 0
    rejected = 0
    for row in rows:
        product = db.get(DimProduct, int(row["product_id"]))
        if not product:
            continue
        company_name = _company_name(db, product)
        aliases = _company_aliases(company_name)
        old_raw = product.raw_product_name
        cleaned = str(row["cleaned_product_name"] or "")
        if row["suggested_action"] == "merge_into_existing_cleaned_product":
            target = db.get(DimProduct, int(row["target_product_id"]))
            if target:
                ProductCanonicalizationService().merge_products(
                    db,
                    target,
                    product,
                    decision_source="deterministic_korean_discourse_prefix_cleanup",
                    confidence=0.95,
                    reason="Leading Korean discourse prefix was removed and the cleaned product already exists for the same insurer.",
                    needs_review=False,
                )
                updated += 1
            continue
        if row["suggested_action"] == "update_cleaned_name":
            normalized = normalize_product_name(cleaned, aliases)
            core_candidates = product_core_key_candidates(normalized, aliases)
            product.normalized_product_name = normalized
            product.raw_product_name = normalized
            product.product_search_key = product_search_key(normalized, company_name)
            product.product_core_key = core_candidates[0] if core_candidates else normalize_product_name_core(normalized, aliases)
            product.product_identity_key = build_product_identity_key(product.company_id, normalized, aliases)
            repository.record_product_alias(
                db,
                product,
                old_raw,
                normalized,
                product.product_core_key,
                source_type="prefix_cleanup",
            )
            updated += 1
        else:
            product.product_status = "rejected"
            product.needs_review = True
            repository.record_product_alias(
                db,
                product,
                old_raw,
                cleaned,
                normalize_product_name_core(cleaned, aliases),
                source_type="prefix_cleanup_rejected",
            )
            rejected += 1
    db.commit()
    return {"updated": updated, "rejected": rejected}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    with SessionLocal() as db:
        rows = build_plan(db)
        write_plan(rows)
        result = {"rows": len(rows), "output": str(OUTPUT), "applied": False}
        if args.apply:
            result.update(apply_plan(db, rows))
            result["applied"] = True
        print(result)


if __name__ == "__main__":
    main()
