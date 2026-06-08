from __future__ import annotations

from app.db.models import DimCompany, DimProduct, FactQwenReviewAudit
from app.normalizers.product_name_normalizer import build_product_identity_key, normalize_product_name_core, product_search_key
from app.services.product_company_brand_rule_service import (
    PRODUCT_COMPANY_BRAND_RULE_TASK_TYPE,
    ProductCompanyBrandRuleService,
)


def _company(db, name: str) -> DimCompany:
    return db.query(DimCompany).filter(DimCompany.company_name_normalized == name).one()


def _aliases(company: DimCompany) -> list[str]:
    values = [company.company_name_normalized, company.company_name_raw]
    values.extend(item.strip() for item in (company.alias or "").split("|") if item.strip())
    return [item for item in values if item]


def _product(db, *, name: str, company_name: str) -> DimProduct:
    company = _company(db, company_name)
    aliases = _aliases(company)
    product = DimProduct(
        normalized_product_name=name,
        raw_product_name=name,
        company_name_raw=company.company_name_normalized,
        company_id=company.company_id,
        insurance_type=company.insurance_type,
        product_search_key=product_search_key(name, company.company_name_normalized),
        product_core_key=normalize_product_name_core(name, aliases),
        product_identity_key=build_product_identity_key(company.company_id, name, aliases),
        confidence_total=0.9,
        needs_review=False,
        product_status="active",
        consolidation_status="done",
    )
    db.add(product)
    db.commit()
    return product


def test_unique_product_name_brand_reassigns_company(db_session):
    product = _product(db_session, name="AXA나를지켜주는암보험II", company_name="메리츠화재")

    service = ProductCompanyBrandRuleService()
    rows = service.build_plan(db_session, product_id=product.product_id)

    assert len(rows) == 1
    assert rows[0].action == "update_company"
    assert rows[0].new_company_name == "AXA손해보험"

    summary = service.apply_plan(db_session, rows)
    db_session.commit()
    db_session.refresh(product)
    axa = _company(db_session, "AXA손해보험")

    assert summary["update_company"] == 1
    assert product.company_id == axa.company_id
    assert product.company_name_raw == "AXA손해보험"
    assert product.product_search_key == product_search_key("AXA나를지켜주는암보험II", "AXA손해보험")
    assert product.needs_review is False
    audit = db_session.query(FactQwenReviewAudit).filter(FactQwenReviewAudit.target_id == product.product_id).one()
    assert audit.task_type == PRODUCT_COMPANY_BRAND_RULE_TASK_TYPE
    assert audit.provider == "rule"
    assert audit.apply_status == "applied"


def test_ambiguous_life_nonlife_brand_marks_review_for_qwen(db_session):
    product = _product(db_session, name="삼성 든든한 암보험", company_name="메리츠화재")

    service = ProductCompanyBrandRuleService()
    rows = service.build_plan(db_session, product_id=product.product_id)

    assert len(rows) == 1
    assert rows[0].action == "mark_review_for_qwen"
    assert set(rows[0].candidates) == {"삼성생명", "삼성화재"}

    summary = service.apply_plan(db_session, rows)
    db_session.commit()
    db_session.refresh(product)

    assert summary["mark_review_for_qwen"] == 1
    assert product.company_name_raw == "메리츠화재"
    assert product.needs_review is True
    assert product.consolidation_status == "review"


def test_full_company_name_in_product_name_overrides_ambiguous_brand(db_session):
    product = _product(db_session, name="삼성화재 든든한 암보험", company_name="메리츠화재")

    rows = ProductCompanyBrandRuleService().build_plan(db_session, product_id=product.product_id)

    assert len(rows) == 1
    assert rows[0].action == "update_company"
    assert rows[0].new_company_name == "삼성화재"
