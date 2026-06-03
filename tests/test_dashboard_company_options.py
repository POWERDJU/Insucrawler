from app.services.dashboard_service import DashboardService


def test_dashboard_options_return_company_status_fields(db_session):
    options = DashboardService().options(db_session)
    companies = {item["company_name"]: item for item in options["companies"]}

    assert "MG손해보험" in companies
    assert "예별손해보험" in companies
    assert "캐롯손해보험" in companies
    assert "마이브라운반려동물전문보험" in companies
    assert "신한EZ손해보험" in companies
    assert "insurance_type" in companies["MG손해보험"]
    assert companies["iM라이프생명"]["display_label"] == "iM라이프생명 (구 DGB생명)"
    assert companies["라이나손해보험"]["display_label"] == "라이나손해보험 (구 에이스손해보험)"
    assert companies["예별손해보험"]["display_label"] == "예별손해보험 (MG손보 계약관리)"
    assert companies["캐롯손해보험"]["display_label"] == "캐롯손해보험 (한화손해보험 합병)"
    assert companies["마이브라운반려동물전문보험"]["display_label"] == "마이브라운반려동물전문보험 (신규)"


def test_dashboard_options_exclude_and_include_reinsurers(db_session):
    default_options = DashboardService().options(db_session)
    default_names = {item["company_name"] for item in default_options["companies"]}
    assert "코리안리재보험" not in default_names
    assert "미쓰이스미토모해상화재보험 한국지점" not in default_names

    expanded = DashboardService().options(db_session, include_reinsurers=True)
    expanded_names = {item["company_name"] for item in expanded["companies"]}
    assert "코리안리재보험" in expanded_names

    foreign_branch_expanded = DashboardService().options(db_session, include_foreign_branches=True)
    foreign_branch_names = {item["company_name"] for item in foreign_branch_expanded["companies"]}
    assert "미쓰이스미토모해상화재보험 한국지점" in foreign_branch_names
