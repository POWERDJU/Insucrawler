from __future__ import annotations

from app.db.models import DimCompany, DimProduct, FactLLMRun, FactProductMergeDecision
from app.services.product_consolidation_service import ProductConsolidationService
from app.services.product_duplicate_guard_service import ProductDuplicateGuardService


def _company(db_session, name: str, insurance_type: str = "생명보험") -> DimCompany:
    row = DimCompany(
        company_name_normalized=name,
        company_name_raw=name,
        alias=name,
        insurance_type=insurance_type,
        include_in_product_news_default="Y",
        active_yn="Y",
    )
    db_session.add(row)
    db_session.flush()
    return row


def _product(
    db_session,
    company: DimCompany,
    name: str,
    *,
    product_type: str,
    release_year_month: str = "2026-01",
    status: str = "active",
) -> DimProduct:
    row = DimProduct(
        raw_product_name=name,
        normalized_product_name=name,
        product_search_key=f"real-export:{company.company_id}:{name}",
        product_core_key="".join(ch for ch in name.casefold() if ch.isalnum()),
        company_id=company.company_id,
        insurance_type=company.insurance_type,
        release_year_month=release_year_month,
        primary_product_type_code=product_type,
        product_status=status,
        confidence_total=0.9,
        needs_review=False,
    )
    db_session.add(row)
    db_session.flush()
    row.canonical_product_id = row.product_id
    return row


def _active_products(db_session, company: DimCompany) -> list[DimProduct]:
    return (
        db_session.query(DimProduct)
        .filter(DimProduct.company_id == company.company_id, DimProduct.product_status != "merged")
        .order_by(DimProduct.product_id)
        .all()
    )


def test_real_export_rows_46_138_stepup_700_variants_merge_without_llm(db_session):
    company = _company(db_session, "NH농협생명")
    _product(db_session, company, "스텝업700 종신보험", product_type="DEATH_WHOLELIFE", status="active")
    _product(db_session, company, "스텝업 700 NH 종신보험", product_type="DEATH_WHOLELIFE", status="provisional")
    _product(db_session, company, "트루라이프NH종신보험", product_type="DEATH_WHOLELIFE", status="active")
    db_session.commit()

    before = ProductDuplicateGuardService().find_duplicate_family_groups(db_session)
    assert any("스텝업" in "\n".join(group["product_names"]) for group in before)

    result = ProductConsolidationService().run(db_session, mode="rule_only_apply", target="all", limit=0)
    active = _active_products(db_session, company)
    active_names = [item.normalized_product_name for item in active]
    decisions = {row.decision_source for row in db_session.query(FactProductMergeDecision).all()}

    assert result["auto_merge_count"] >= 1
    assert len([name for name in active_names if "스텝업" in name]) == 1
    assert len([name for name in active_names if "트루라이프" in name]) == 1
    assert "deterministic_same_company_family_tokens" in decisions or "deterministic_high_similarity" in decisions
    assert db_session.query(FactLLMRun).count() == 0


def test_real_export_rows_115_116_117_120_pet_alias_variants_merge_without_llm(db_session):
    company = _company(db_session, "KB손해보험", insurance_type="손해보험")
    variants = [
        "KB 금쪽같은 펫보험",
        "금쪽같은 펫보험",
        "KB 금쪽같은 펫 보험 개정",
        "펫보험",
    ]
    for index, name in enumerate(variants):
        _product(
            db_session,
            company,
            name,
            product_type="PET",
            status="active" if index == 0 else "provisional",
        )
    db_session.commit()

    ProductConsolidationService().run(db_session, mode="rule_only_apply", target="all", limit=0)
    active = _active_products(db_session, company)

    assert len(active) == 1
    assert "금쪽같은" in (active[0].normalized_product_name or "")
    assert db_session.query(FactLLMRun).count() == 0
