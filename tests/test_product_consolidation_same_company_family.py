from __future__ import annotations

from app.db.models import DimCompany, DimProduct, FactLLMRun, FactProductMergeDecision
from app.normalizers.product_name_normalizer import (
    build_product_family_tokens,
    normalize_product_family_signature,
)
from app.services.product_consolidation_service import ProductConsolidationService


def _company(db, name: str, insurance_type: str = "생명보험") -> DimCompany:
    company = DimCompany(
        company_name_normalized=name,
        company_name_raw=name,
        alias=name,
        insurance_type=insurance_type,
        insurance_type_default=insurance_type,
        include_in_product_news_default="Y",
        active_yn="Y",
    )
    db.add(company)
    db.flush()
    return company


def _product(
    db,
    *,
    company: DimCompany,
    raw_name: str,
    normalized_name: str | None = None,
    status: str = "active",
    product_type_code: str = "HEALTH_COMPREHENSIVE",
    release_year_month: str = "2026-01",
) -> DimProduct:
    normalized = normalized_name or raw_name
    item = DimProduct(
        raw_product_name=raw_name,
        normalized_product_name=normalized,
        product_search_key=f"{company.company_id}:{raw_name}",
        product_core_key=f"{company.company_id}:{raw_name}",
        company_id=company.company_id,
        insurance_type=company.insurance_type,
        release_year_month=release_year_month,
        primary_product_type_code=product_type_code,
        confidence_total=0.9,
        needs_review=False,
        product_status=status,
    )
    db.add(item)
    db.flush()
    item.canonical_product_id = item.product_id
    return item


def test_product_family_signature_normalizes_tontine_and_health_refund():
    assert normalize_product_family_signature("신한톤틴 연금보험 [무배당, (사망·해지) 일부지급형]") == "톤틴연금"
    assert normalize_product_family_signature("톤틴(Tontine) 연금") == "톤틴연금"
    assert "건강환급" in build_product_family_tokens("(무)우리WON건강환급보험")
    assert normalize_product_family_signature("연금") == ""


def test_same_company_tontine_annuity_family_merges_without_llm(db_session):
    company = _company(db_session, "신한라이프생명")
    products = [
        _product(
            db_session,
            company=company,
            raw_name="신한톤틴 연금보험 [무배당, (사망·해지) 일부지급형]",
            normalized_name="톤틴연금보험 무배당 사망 해지 일부지급형",
            status="provisional",
            product_type_code="ANNUITY_SAVINGS",
        ),
        _product(
            db_session,
            company=company,
            raw_name="신한톤틴연금보험",
            normalized_name="톤틴연금보험",
            status="active",
            product_type_code="ANNUITY_SAVINGS",
        ),
        _product(
            db_session,
            company=company,
            raw_name="톤틴(Tontine) 연금",
            normalized_name="톤틴 tontine 형 연금보험",
            status="active",
            product_type_code="ANNUITY_SAVINGS",
        ),
        _product(
            db_session,
            company=company,
            raw_name="한국형 톤틴연금 보험",
            normalized_name="한국형 톤틴연금보험",
            status="provisional",
            product_type_code="ANNUITY_SAVINGS",
        ),
    ]
    db_session.commit()

    result = ProductConsolidationService().run(db_session, mode="rule_only_apply", target="all", limit=0)
    active_products = db_session.query(DimProduct).filter(DimProduct.product_status != "merged").all()
    decisions = db_session.query(FactProductMergeDecision).all()

    assert result["auto_merge_count"] == 3
    assert len(active_products) == 1
    assert active_products[0].raw_product_name in {product.raw_product_name for product in products}
    assert all(product.product_status == "merged" for product in products if product.product_id != active_products[0].product_id)
    assert {decision.decision_source for decision in decisions} <= {
        "deterministic_same_company_family_signature",
        "deterministic_same_company_family_tokens",
        "deterministic_same_company_alias_overlap",
        "deterministic_same_company_active_provisional_merge",
    }
    assert db_session.query(FactLLMRun).count() == 0


def test_same_company_abl_health_refund_family_merges_to_official_name(db_session):
    company = _company(db_session, "ABL생명")
    official = _product(
        db_session,
        company=company,
        raw_name="(무)우리WON건강환급보험",
        normalized_name="우리WON건강환급보험",
        status="active",
    )
    duplicates = [
        _product(db_session, company=company, raw_name="건강환급보험", normalized_name="건강환급보험", status="active"),
        _product(db_session, company=company, raw_name="보험료 환급해주는 건강환급보험", status="provisional"),
        _product(db_session, company=company, raw_name="납입 특약보험료 건강환급금 지급 상품", status="provisional"),
    ]
    db_session.commit()

    result = ProductConsolidationService().run(db_session, mode="rule_only_apply", target="all", limit=0)
    db_session.refresh(official)

    assert result["auto_merge_count"] == 3
    assert official.product_status == "active"
    assert official.normalized_product_name == "우리WON건강환급보험"
    assert all(product.product_status == "merged" for product in duplicates)
    assert db_session.query(DimProduct).filter(DimProduct.product_status != "merged").count() == 1
    assert db_session.query(FactLLMRun).count() == 0


def test_family_consolidation_does_not_merge_different_company_or_version(db_session):
    first = _company(db_session, "신한라이프생명")
    second = _company(db_session, "다른생명")
    _product(db_session, company=first, raw_name="톤틴연금보험 3.0", product_type_code="ANNUITY_SAVINGS")
    _product(db_session, company=first, raw_name="톤틴연금보험 4.0", product_type_code="ANNUITY_SAVINGS")
    _product(db_session, company=second, raw_name="톤틴연금보험 3.0", product_type_code="ANNUITY_SAVINGS")
    db_session.commit()

    result = ProductConsolidationService().run(db_session, mode="rule_only_apply", target="all", limit=0)

    assert result["auto_merge_count"] == 0
    assert db_session.query(DimProduct).filter(DimProduct.product_status != "merged").count() == 3
