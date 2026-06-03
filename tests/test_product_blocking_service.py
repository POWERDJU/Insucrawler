from app.db.models import DimCompany, DimProduct
from app.services.product_blocking_service import ProductBlockingService


def _company(db, name: str):
    item = DimCompany(company_name_normalized=name, insurance_type="nonlife", include_in_product_news_default="Y")
    db.add(item)
    db.flush()
    return item


def _product(db, *, name: str, company_id: int, product_type: str = "HEALTH_COMPREHENSIVE", month: str = "2026-01", core: str | None = None):
    item = DimProduct(
        raw_product_name=name,
        normalized_product_name=name,
        product_search_key=f"{company_id}:{name}",
        product_core_key=core or name.replace(" ", "").casefold(),
        company_id=company_id,
        insurance_type="nonlife",
        release_year_month=month,
        primary_product_type_code=product_type,
        confidence_total=0.9,
        needs_review=False,
        product_status="provisional",
    )
    db.add(item)
    db.flush()
    item.canonical_product_id = item.product_id
    return item


def test_blocking_groups_same_company_similar_product_type_and_month(db_session):
    company = _company(db_session, "Alpha Insurance")
    first = _product(db_session, name="Mini Care Insurance", company_id=company.company_id, core="minicareinsurance")
    second = _product(db_session, name="Alpha Mini Care Insurance", company_id=company.company_id, core="alphaminicareinsurance")
    db_session.commit()

    blocks = ProductBlockingService().build_blocks(db_session, target="all_provisional", limit=20)

    assert any({first.product_id, second.product_id}.issubset(set(block.candidate_product_ids)) for block in blocks)


def test_blocking_does_not_group_different_known_company_or_conflicting_type(db_session):
    alpha = _company(db_session, "Alpha Insurance")
    beta = _company(db_session, "Beta Insurance")
    first = _product(db_session, name="Mini Care Insurance", company_id=alpha.company_id)
    other_company = _product(db_session, name="Mini Care Insurance", company_id=beta.company_id)
    other_type = _product(db_session, name="Mini Care Insurance Dental", company_id=alpha.company_id, product_type="DENTAL")
    db_session.commit()

    blocks = ProductBlockingService().build_blocks(db_session, target="all_provisional", limit=20)
    grouped = [set(block.candidate_product_ids) for block in blocks]

    assert not any({first.product_id, other_company.product_id}.issubset(group) for group in grouped)
    assert not any({first.product_id, other_type.product_id}.issubset(group) for group in grouped)
