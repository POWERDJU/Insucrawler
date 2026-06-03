from __future__ import annotations

from app.db.models import DimCompany, DimProduct, FactLLMRun
from app.services.product_consolidation_service import ProductConsolidationService


def _company(db_session, name: str = "한화손해보험") -> DimCompany:
    row = DimCompany(
        company_name_normalized=name,
        company_name_raw=name,
        alias=name,
        insurance_type="손해보험",
        include_in_product_news_default="Y",
        active_yn="Y",
    )
    db_session.add(row)
    db_session.flush()
    return row


def _product(db_session, company: DimCompany, name: str, month: str = "2026-04") -> DimProduct:
    row = DimProduct(
        raw_product_name=name,
        normalized_product_name=name,
        product_search_key=f"{company.company_id}:{name}",
        product_core_key=name.replace(" ", "").casefold(),
        company_id=company.company_id,
        insurance_type=company.insurance_type,
        release_year_month=month,
        primary_product_type_code="HEALTH_COMPREHENSIVE",
        product_status="active",
        confidence_total=0.9,
        needs_review=False,
    )
    db_session.add(row)
    db_session.flush()
    row.canonical_product_id = row.product_id
    return row


def test_signature_women_same_version_variants_merge_without_llm(db_session):
    company = _company(db_session)
    _product(db_session, company, "시그니처 여성 건강보험 4.0")
    _product(db_session, company, "한화 시그니처 여성건강보험4.0 무배당")
    _product(db_session, company, "시그니처 여성보험 4.0")
    db_session.commit()

    result = ProductConsolidationService().run(db_session, mode="rule_only_apply", target="all", limit=0)

    assert result["auto_merge_count"] == 2
    assert db_session.query(DimProduct).filter(DimProduct.product_status != "merged").count() == 1
    assert db_session.query(FactLLMRun).count() == 0


def test_signature_women_versionless_name_does_not_bridge_3_and_4(db_session):
    company = _company(db_session)
    _product(db_session, company, "시그니처 여성건강보험 3.0", month="2025-10")
    _product(db_session, company, "시그니처 여성건강보험 4.0", month="2026-04")
    _product(db_session, company, "시그니처 여성건강보험", month="2026-04")
    db_session.commit()

    result = ProductConsolidationService().run(db_session, mode="rule_only_apply", target="all", limit=0)

    assert result["auto_merge_count"] == 0
    assert db_session.query(DimProduct).filter(DimProduct.product_status != "merged").count() == 3
    assert db_session.query(FactLLMRun).count() == 0
