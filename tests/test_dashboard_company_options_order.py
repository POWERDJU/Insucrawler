from app.services.dashboard_service import DashboardService


def test_dashboard_company_options_keep_establishment_order(db_session):
    options = DashboardService().options(db_session)
    companies = options["companies"]
    nonlife = [item["company_name"] for item in companies if item["insurance_type"] == "손해보험"]
    life = [item["company_name"] for item in companies if item["insurance_type"] == "생명보험"]

    assert nonlife[:3] == ["메리츠화재", "한화손해보험", "롯데손해보험"]
    assert life[0] == "한화생명"
    assert "전체" not in {item["company_name"] for item in companies}


def test_dashboard_company_options_include_establishment_info(db_session):
    options = DashboardService().options(db_session)
    meritz = next(item for item in options["companies"] if item["company_name"] == "메리츠화재")

    assert meritz["company_name_normalized"] == "메리츠화재"
    assert meritz["establishment_year"] == 1922
    assert meritz["establishment_sort_date"] == "1922-10"
    assert meritz["display_order_established"] == 1
    assert meritz["establishment_source_note"] == "조선화재해상보험 설립 기준"
