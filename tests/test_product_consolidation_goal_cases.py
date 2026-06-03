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
    release_year_month: str = "2026-01",
    status: str = "active",
) -> DimProduct:
    row = DimProduct(
        raw_product_name=name,
        normalized_product_name=name,
        product_search_key=f"{company.company_id}:{name}",
        product_core_key=name.replace(" ", "").casefold(),
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


def _alias_names(db_session, product_id: int) -> set[str]:
    return {
        row.raw_product_name
        for row in db_session.query(DimProductAlias).filter(DimProductAlias.product_id == product_id).all()
    }


def test_goal_rule_only_consolidates_tontine_without_crawl_or_llm(db_session):
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
    for idx, name in enumerate(names):
        _product(
            db_session,
            company,
            name,
            product_type="ANNUITY_SAVINGS" if idx % 3 else "UNKNOWN",
            release_year_month="2026-01",
            status="active" if idx % 2 else "provisional",
        )
    db_session.commit()

    before = ProductDuplicateGuardService().find_duplicate_family_groups(db_session)
    assert any(set(group["product_names"]).intersection(names) for group in before)

    result = ProductConsolidationService().run(db_session, mode="rule_only_apply", target="all", limit=0)
    active = _active_products(db_session, company)

    assert result["auto_merge_count"] == len(names) - 1
    assert len(active) == 1
    assert all(name in _alias_names(db_session, active[0].product_id) or name == active[0].raw_product_name for name in names)
    assert ProductDuplicateGuardService().find_duplicate_family_groups(db_session) == []
    assert db_session.query(FactLLMRun).count() == 0


def test_goal_rule_only_consolidates_hanwha_signature_women_4_and_rejects_conflicts(db_session):
    hanwha = _company(db_session, "한화손해보험", insurance_type="손해보험")
    other = _company(db_session, "다른손해보험", insurance_type="손해보험")
    merge_names = [
        "시그니처 여성 건강보험 4.0",
        "시그니처 여성보험 4.0",
        "한화 시그니처 여성 건강보험 4.0 무배당",
        "시그니처 여성 건강 보험 4.0",
        "한화손해보험 시그니처 여성건강보험 4.0",
    ]
    for idx, name in enumerate(merge_names):
        _product(
            db_session,
            hanwha,
            name,
            product_type="HEALTH_COMPREHENSIVE" if idx % 2 else "UNKNOWN",
            status="active" if idx == 0 else "provisional",
        )
    _product(db_session, hanwha, "시그니처 여성보험 3.0")
    _product(db_session, other, "시그니처 여성보험 4.0")
    db_session.commit()

    ProductConsolidationService().run(db_session, mode="rule_only_apply", target="all", limit=0)
    hanwha_active = _active_products(db_session, hanwha)
    decisions = db_session.query(FactProductMergeDecision).all()

    assert len([item for item in hanwha_active if "4.0" in item.normalized_product_name]) == 1
    assert len([item for item in hanwha_active if "3.0" in item.normalized_product_name]) == 1
    assert db_session.query(DimProduct).filter(DimProduct.company_id == other.company_id, DimProduct.product_status != "merged").count() == 1
    assert "deterministic_same_company_optional_modifier_identity" in {row.decision_source for row in decisions}
    assert db_session.query(FactLLMRun).count() == 0


def test_goal_rule_only_consolidates_abl_health_refund_but_keeps_surgery_separate(db_session):
    company = _company(db_session, "ABL생명")
    health_names = [
        "(무)우리WON건강환급보험",
        "우리WON건강환급보험",
        "건강환급보험",
        "보험료 환급해주는 건강환급보험",
        "납입 특약보험료 환급 상품",
        "특약보험료 환급형 건강보험",
        "환급보험",
    ]
    for idx, name in enumerate(health_names):
        _product(
            db_session,
            company,
            name,
            product_type="HEALTH_COMPREHENSIVE" if idx % 2 else "UNKNOWN",
            status="active" if idx == 1 else "provisional",
        )
    _product(db_session, company, "우리WON전신마취수술보험")
    _product(db_session, company, "전신마취수술보험")
    db_session.commit()

    ProductConsolidationService().run(db_session, mode="rule_only_apply", target="all", limit=0)
    active = _active_products(db_session, company)
    health_active = [item for item in active if "건강환급" in item.normalized_product_name or "환급" in item.normalized_product_name]
    surgery_active = [item for item in active if "전신마취수술" in item.normalized_product_name]

    assert len(health_active) == 1
    assert len(surgery_active) >= 1
    alias_names = ProductDuplicateGuardService().compatible_alias_names(
        health_active[0],
        [*health_names, "우리WON전신마취수술보험", "전신마취수술보험"],
        [company.company_name_normalized],
    )
    assert "우리WON전신마취수술보험" not in alias_names
    assert "전신마취수술보험" not in alias_names
    assert db_session.query(FactLLMRun).count() == 0
