from __future__ import annotations

from app.db.models import DimCompany, DimProduct, FactProductMergeDecision
from app.services.product_consolidation_service import ProductConsolidationService


def _company(db_session) -> DimCompany:
    row = DimCompany(
        company_name_normalized="한화손해보험",
        company_name_raw="한화손해보험",
        alias="한화손보",
        insurance_type="손해보험",
        include_in_product_news_default="Y",
        active_yn="Y",
    )
    db_session.add(row)
    db_session.flush()
    return row


def _product(db_session, company: DimCompany, name: str, *, month: str = "2026-04") -> DimProduct:
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


def test_birth_benefit_variants_merge_as_same_component_family(db_session):
    company = _company(db_session)
    names = [
        "출산하면 보험료 지원 특약",
        "출산지원금 보장 특약",
        "출산 혜택 보험료 유예 특약",
    ]
    for name in names:
        _product(db_session, company, name)
    db_session.commit()

    result = ProductConsolidationService().run(db_session, mode="rule_only_apply", target="all", limit=0)
    decisions = db_session.query(FactProductMergeDecision).all()

    assert result["auto_merge_count"] == 2
    assert db_session.query(DimProduct).filter(DimProduct.product_status != "merged").count() == 1
    assert {row.decision_source for row in decisions} == {"deterministic_same_company_birth_benefit_component"}


def test_birth_benefit_component_does_not_merge_into_signature_body_product(db_session):
    company = _company(db_session)
    _product(db_session, company, "시그니처 여성건강보험 4.0")
    _product(db_session, company, "출산지원금 보장 특약")
    db_session.commit()

    result = ProductConsolidationService().run(db_session, mode="rule_only_apply", target="all", limit=0)

    assert result["auto_merge_count"] == 0
    assert db_session.query(DimProduct).filter(DimProduct.product_status != "merged").count() == 2
