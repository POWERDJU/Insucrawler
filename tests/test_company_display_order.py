from app.db.models import DimCompany
from app.services.company_service import CompanyService


def names(rows):
    return [row["company_name_normalized"] for row in rows]


def test_nonlife_display_order_uses_establishment_order(db_session):
    rows = CompanyService().list_companies(db_session, insurance_type="손해보험")

    assert names(rows)[:9] == [
        "메리츠화재",
        "한화손해보험",
        "롯데손해보험",
        "MG손해보험",
        "흥국화재",
        "삼성화재",
        "현대해상",
        "KB손해보험",
        "DB손해보험",
    ]


def test_life_display_order_uses_establishment_order(db_session):
    rows = CompanyService().list_companies(db_session, insurance_type="생명보험")

    assert names(rows)[:5] == ["한화생명", "흥국생명", "ABL생명", "삼성생명", "교보생명"]


def test_current_brand_year_is_not_sort_key(db_session):
    life_rows = names(CompanyService().list_companies(db_session, insurance_type="생명보험"))
    nonlife_rows = names(CompanyService().list_companies(db_session, insurance_type="손해보험"))
    carrot = db_session.query(DimCompany).filter(DimCompany.company_name_normalized == "캐롯손해보험").one()

    assert life_rows.index("iM라이프생명") < life_rows.index("BNP파리바카디프생명")
    assert nonlife_rows.index("하나손해보험") < nonlife_rows.index("신한EZ손해보험")
    assert nonlife_rows.index("신한EZ손해보험") < nonlife_rows.index("NH농협손해보험")
    assert carrot.status_2024_2026 == "merged"
    assert carrot.establishment_year == 2019
    assert nonlife_rows.index("캐롯손해보험") < nonlife_rows.index("카카오페이손해보험")
