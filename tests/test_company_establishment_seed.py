from sqlalchemy import inspect

from app.db.models import DimCompany


def company_by_name(db_session, name: str) -> DimCompany:
    return db_session.query(DimCompany).filter(DimCompany.company_name_normalized == name).one()


def test_dim_company_establishment_columns_exist(db_session):
    columns = {column["name"] for column in inspect(db_session.bind).get_columns("dim_company")}

    assert "establishment_year" in columns
    assert "establishment_sort_date" in columns
    assert "establishment_basis" in columns
    assert "current_brand_year" in columns
    assert "display_order_established" in columns


def test_company_seed_uses_predecessor_establishment_years(db_session):
    expected_years = {
        "메리츠화재": 1922,
        "한화손해보험": 1946,
        "롯데손해보험": 1947,
        "MG손해보험": 1947,
        "흥국화재": 1948,
        "삼성화재": 1952,
        "현대해상": 1955,
        "KB손해보험": 1959,
        "DB손해보험": 1962,
        "iM라이프생명": 1988,
        "하나손해보험": 2003,
        "신한EZ손해보험": 2004,
        "예별손해보험": 2025,
    }

    for company_name, establishment_year in expected_years.items():
        assert company_by_name(db_session, company_name).establishment_year == establishment_year


def test_current_brand_year_is_preserved_but_not_establishment_year(db_session):
    im_life = company_by_name(db_session, "iM라이프생명")
    hana_nonlife = company_by_name(db_session, "하나손해보험")
    shinhan_ez = company_by_name(db_session, "신한EZ손해보험")

    assert im_life.current_brand_year == 2024
    assert im_life.establishment_year == 1988
    assert hana_nonlife.current_brand_year == 2020
    assert hana_nonlife.establishment_year == 2003
    assert shinhan_ez.current_brand_year == 2022
    assert shinhan_ez.establishment_year == 2004
