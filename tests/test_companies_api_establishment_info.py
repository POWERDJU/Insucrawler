from fastapi.testclient import TestClient

from app.api.main import app
from app.db.database import get_db


def test_companies_api_returns_establishment_info_and_order(db_session):
    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    try:
        client = TestClient(app)
        response = client.get("/api/companies", params={"insurance_type": "손해보험"})
        assert response.status_code == 200
        companies = response.json()

        assert [item["company_name_normalized"] for item in companies[:3]] == ["메리츠화재", "한화손해보험", "롯데손해보험"]
        assert companies[0]["establishment_year"] == 1922
        assert companies[0]["display_order_established"] == 1
        assert "코리안리재보험" not in {item["company_name_normalized"] for item in companies}

        expanded = client.get("/api/companies", params={"insurance_type": "손해보험", "include_reinsurers": True}).json()
        korean_re = next(item for item in expanded if item["company_name_normalized"] == "코리안리재보험")
        assert korean_re["establishment_year"] == 1963
    finally:
        app.dependency_overrides.clear()
