from fastapi.testclient import TestClient

from app.api.main import app


def test_dashboard_root_renders_html():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "보험상품 뉴스 자동조사봇" in response.text
    assert "/static/dashboard.css" in response.text


def test_dashboard_root_uses_simplified_filter_ui():
    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    assert "pivotPreset" not in response.text
    assert "피벗 preset" not in response.text
    assert "보험종류 적용방식" not in response.text
    assert "classificationMode" not in response.text
    assert "customColumns" not in response.text
    assert "열 기준" not in response.text
    assert "rowDimensionButtons" not in response.text
    assert "피벗 행 기준" not in response.text
    assert "피벗 요약" not in response.text
    assert "pivotTable" not in response.text
    assert "minConfidence" not in response.text
    assert "releaseMonth" not in response.text
    assert 'id="insuranceType"' in response.text
    assert "업종 선택" in response.text
    assert "releaseYearAll" in response.text
    assert 'id="releaseYearAll" type="button"' in response.text
    assert 'id="releaseYearAll" type="checkbox"' not in response.text
    assert "releaseYearOptions" in response.text
    assert "companyNamesAll" in response.text
    assert 'id="companyNamesAll" type="button"' in response.text
    assert 'id="companyNamesAll" type="checkbox"' not in response.text
    assert 'id="companyNames"' in response.text
    assert "productTypeCodesAll" in response.text
    assert 'id="productTypeCodesAll" type="button"' in response.text
    assert 'id="productTypeCodesAll" type="checkbox"' not in response.text
    assert 'id="productTypeCodes"' in response.text
    assert "전체선택" in response.text
    assert "업종을 먼저 선택하세요." in response.text
    assert "includeReinsurersForeign" not in response.text
    assert "재보험/외국지점 포함" not in response.text
    assert "downloadExcel" in response.text
    assert "엑셀 다운로드" in response.text
    assert "button-icon" in response.text
    assert "exclusiveRightCompanyNamesAll" in response.text
    assert "exclusiveRightCompanyNames" in response.text
    assert "상품 비교표" in response.text
    assert "monthlyNewProductBoard" in response.text
    assert "monthlyBoardCard" in response.text
    assert "monthlyPrev" in response.text
    assert "monthlyNext" in response.text
    assert "recentExclusiveRightsBoard" in response.text
    assert "exclusiveBoardCard" in response.text
    assert "exclusivePrev" in response.text
    assert "exclusiveNext" in response.text
    assert "이달의 신상품" in response.text
    assert "toggleAdminPanel" in response.text
    assert "관리자 업데이트" in response.text
    assert "adminPassword" in response.text
    assert "runTestCrawl" in response.text
    assert "runBackfillCrawl" in response.text
    assert "runIncrementalCrawl" in response.text
    assert "includeChangedCompanies" not in response.text
    assert "합병/소멸/가교회사 포함" not in response.text
    assert "includeShortTermInsurers" not in response.text
    assert "신규/소액단기보험사 포함" not in response.text
    assert "detail-panel-full" in response.text
