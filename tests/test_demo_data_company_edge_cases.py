from app.db.models import DimCompany, DimProduct, FactArticle
from scripts.seed_demo_data import seed_demo_data


def test_demo_data_contains_company_edge_cases(db_session):
    result = seed_demo_data(db_session)
    assert result["inserted_products"] >= 6

    rows = (
        db_session.query(DimProduct, DimCompany)
        .join(DimCompany, DimCompany.company_id == DimProduct.company_id)
        .all()
    )
    by_company = {}
    for product, company in rows:
        by_company.setdefault(company.company_name_normalized, []).append(product)

    assert "MG손해보험" in by_company
    assert "예별손해보험" in by_company
    assert "캐롯손해보험" in by_company
    assert "마이브라운반려동물전문보험" in by_company

    im_products = by_company["iM라이프생명"]
    assert any(product.company_name_raw == "DGB생명" for product in im_products)

    lina_products = by_company["라이나손해보험"]
    assert any(product.company_name_raw == "에이스손해보험" for product in lina_products)

    titles = {row.title for row in db_session.query(FactArticle).all()}
    assert "예별손보 MG손보 계약 이전 관련 기사 예시" in titles
    assert "마이브라운 반려동물 전문보험사 관련 기사 예시" in titles


def test_demo_data_seed_is_idempotent(db_session):
    first = seed_demo_data(db_session)
    second = seed_demo_data(db_session)
    assert first["inserted_products"] > 0
    assert second["inserted_products"] == 0
