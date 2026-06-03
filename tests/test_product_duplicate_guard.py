from __future__ import annotations

from pathlib import Path

from app.db.models import DimCompany, DimProduct
from app.services.product_duplicate_guard_service import ProductDuplicateGuardService


def _company(db_session, name: str) -> DimCompany:
    row = DimCompany(company_name_normalized=name, insurance_type="life", include_in_product_news_default="Y")
    db_session.add(row)
    db_session.flush()
    return row


def _product(db_session, company: DimCompany, name: str, *, product_id: int, product_type: str = "ANNUITY_SAVINGS") -> DimProduct:
    row = DimProduct(
        product_id=product_id,
        normalized_product_name=name,
        raw_product_name=name,
        product_search_key=f"{company.company_id}:{name}:{product_id}",
        product_core_key=name.replace(" ", "").casefold(),
        company_id=company.company_id,
        insurance_type=company.insurance_type,
        release_year_month="2026-01",
        primary_product_type_code=product_type,
        product_status="active",
        confidence_total=0.9,
        needs_review=False,
    )
    db_session.add(row)
    db_session.flush()
    return row


def test_duplicate_guard_finds_same_company_family_and_exports_csv(db_session, tmp_path):
    company = _company(db_session, "Shinhan Life")
    _product(db_session, company, "Tontine annuity insurance", product_id=1)
    _product(db_session, company, "Korean Tontine annuity", product_id=2)

    service = ProductDuplicateGuardService()
    groups = service.find_duplicate_family_groups(db_session)
    summary = service.summarize_duplicate_risk(groups)

    assert summary["duplicate_group_count"] >= 1
    assert any({1, 2}.issubset(set(group["product_ids"])) for group in groups)

    output = service.export_groups_csv(groups, tmp_path / "duplicates.csv")
    assert Path(output).exists()


def test_duplicate_guard_alias_compatibility_excludes_contaminated_alias(db_session):
    company = _company(db_session, "ABL Life")
    product = _product(db_session, company, "WON health refund insurance", product_id=1, product_type="HEALTH_COMPREHENSIVE")
    service = ProductDuplicateGuardService()

    aliases = service.compatible_alias_names(
        product,
        [
            "premium refund health insurance",
            "whole body anesthesia surgery insurance",
        ],
    )

    assert "premium refund health insurance" in aliases
    assert "whole body anesthesia surgery insurance" not in aliases

