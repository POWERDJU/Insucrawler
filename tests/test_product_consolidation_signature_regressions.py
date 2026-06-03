from __future__ import annotations

from app.db.models import DimCompany, DimProduct, DimProductAlias, FactLLMRun, FactProductMergeDecision
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
    product_type: str = "HEALTH_COMPREHENSIVE",
    month: str = "2026-01",
    status: str = "active",
) -> DimProduct:
    row = DimProduct(
        raw_product_name=name,
        normalized_product_name=name,
        product_search_key=f"{company.company_id}:{name}",
        product_core_key=name.replace(" ", "").casefold(),
        company_id=company.company_id,
        insurance_type=company.insurance_type,
        release_year_month=month,
        primary_product_type_code=product_type,
        product_status=status,
        confidence_total=0.9,
        needs_review=False,
    )
    db_session.add(row)
    db_session.flush()
    row.canonical_product_id = row.product_id
    return row


def test_rule_only_merges_tontine_annuity_variants_without_llm(db_session):
    company = _company(db_session, "신한라이프생명")
    names = [
        "신한톤틴 연금보험 [무배당, (사망·해지) 일부지급형]",
        "신한톤틴연금보험",
        "톤틴(Tontine) 연금",
        "한국형 톤틴연금보험",
        "톤틴연금보험",
        "톤틴 연금보험 일부지급형",
        "톤틴 tontine 형 연금보험",
    ]
    for name in names:
        _product(db_session, company, name, product_type="ANNUITY_SAVINGS", status="provisional")
    db_session.commit()

    result = ProductConsolidationService().run(db_session, mode="rule_only_apply", target="all", limit=0)

    assert result["auto_merge_count"] == len(names) - 1
    assert db_session.query(DimProduct).filter(DimProduct.product_status != "merged").count() == 1
    assert db_session.query(FactLLMRun).count() == 0


def test_rule_only_merges_hanwha_signature_women_4_optional_modifier(db_session):
    company = _company(db_session, "한화손해보험", insurance_type="손해보험")
    first = _product(db_session, company, "시그니처 여성 건강보험 4.0")
    second = _product(db_session, company, "시그니처 여성보험 4.0")
    third = _product(db_session, company, "한화 시그니처 여성 건강보험 4.0 무배당")
    db_session.commit()

    result = ProductConsolidationService().run(db_session, mode="rule_only_apply", target="all", limit=0)
    decisions = db_session.query(FactProductMergeDecision).all()

    assert result["auto_merge_count"] == 2
    assert db_session.query(DimProduct).filter(DimProduct.product_status != "merged").count() == 1
    assert "deterministic_same_company_optional_modifier_identity" in {row.decision_source for row in decisions}
    assert all(product.product_status == "merged" for product in (first, second, third) if product.merged_into_product_id)
    assert db_session.query(FactLLMRun).count() == 0


def test_signature_women_3_and_4_do_not_auto_merge(db_session):
    company = _company(db_session, "한화손해보험", insurance_type="손해보험")
    _product(db_session, company, "시그니처 여성보험 3.0")
    _product(db_session, company, "시그니처 여성보험 4.0")
    db_session.commit()

    result = ProductConsolidationService().run(db_session, mode="rule_only_apply", target="all", limit=0)

    assert result["auto_merge_count"] == 0
    assert db_session.query(DimProduct).filter(DimProduct.product_status != "merged").count() == 2


def test_abl_health_refund_alias_cleanup_keeps_surgery_product_separate(db_session):
    company = _company(db_session, "ABL생명")
    health = _product(db_session, company, "우리WON건강환급보험")
    _product(db_session, company, "(무)우리WON건강환급보험")
    _product(db_session, company, "건강환급보험")
    surgery = _product(db_session, company, "우리WON전신마취수술보험")
    db_session.add(
        DimProductAlias(
            product_id=health.product_id,
            raw_product_name="우리WON전신마취수술보험",
            normalized_product_name_candidate="우리WON전신마취수술보험",
            company_id=company.company_id,
        )
    )
    db_session.commit()

    ProductConsolidationService().run(db_session, mode="rule_only_apply", target="all", limit=0)
    aliases = ProductDuplicateGuardService().compatible_alias_names(
        health,
        ["(무)우리WON건강환급보험", "보험료 환급해주는 건강환급보험", "우리WON전신마취수술보험"],
        [company.company_name_normalized],
    )
    db_session.refresh(surgery)

    assert "(무)우리WON건강환급보험" in aliases
    assert "우리WON전신마취수술보험" not in aliases
    assert surgery.product_status != "merged"
