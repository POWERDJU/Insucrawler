from app.db.models import DimCompany, DimProduct, FactProductMergeDecision
from app.services.product_consolidation_service import ProductConsolidationService


def _company(db):
    item = DimCompany(company_name_normalized="Alpha Insurance", insurance_type="nonlife", include_in_product_news_default="Y")
    db.add(item)
    db.flush()
    return item


def _product(db, *, name: str, company_id: int, core: str):
    item = DimProduct(
        raw_product_name=name,
        normalized_product_name=name,
        product_search_key=f"{company_id}:{name}",
        product_core_key=core,
        company_id=company_id,
        insurance_type="nonlife",
        release_year_month="2026-01",
        primary_product_type_code="HEALTH_COMPREHENSIVE",
        confidence_total=0.9,
        needs_review=False,
        product_status="provisional",
    )
    db.add(item)
    db.flush()
    item.canonical_product_id = item.product_id
    return item


def test_rule_only_consolidation_merges_same_company_core_key_without_llm(db_session):
    company = _company(db_session)
    canonical = _product(db_session, name="Mini Care Insurance", company_id=company.company_id, core="minicareinsurance")
    duplicate = _product(db_session, name="Alpha Mini Care Insurance", company_id=company.company_id, core="minicareinsurance")
    db_session.commit()

    result = ProductConsolidationService().run(db_session, mode="rule_only_apply", target="all_provisional", limit=20)
    db_session.refresh(canonical)
    db_session.refresh(duplicate)

    assert result["auto_merge_count"] == 1
    assert duplicate.product_status == "merged"
    assert duplicate.merged_into_product_id == canonical.product_id
    decision = db_session.query(FactProductMergeDecision).one()
    assert decision.decision_source == "deterministic_core_key"
