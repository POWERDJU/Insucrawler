from fastapi.testclient import TestClient

from app.api.main import app
from app.db.database import get_db
from app.db.models import DimCompany, DimProduct
from app.services.admin_auth_service import clear_admin_sessions


def _auth_client(monkeypatch, db_session):
    clear_admin_sessions()
    monkeypatch.setenv("ADMIN_BATCH_PASSWORD", "secret")

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    token = client.post("/api/admin/auth", json={"password": "secret"}).json()["token"]
    return client, {"Authorization": f"Bearer {token}"}


def _seed_products(db):
    company = DimCompany(company_name_normalized="Alpha Insurance", insurance_type="nonlife", include_in_product_news_default="Y")
    db.add(company)
    db.flush()
    for name in ["Mini Care Insurance", "Alpha Mini Care Insurance"]:
        item = DimProduct(
            raw_product_name=name,
            normalized_product_name=name,
            product_search_key=f"{company.company_id}:{name}",
            product_core_key="minicareinsurance",
            company_id=company.company_id,
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
    db.commit()


def test_admin_product_consolidation_run_and_summary(monkeypatch, db_session):
    _seed_products(db_session)
    client, headers = _auth_client(monkeypatch, db_session)
    try:
        response = client.post(
            "/api/admin/product-consolidation/run",
            headers=headers,
            json={"mode": "rule_only_apply", "target": "all_provisional", "limit": 20, "use_llm_for_gray_blocks": False},
        )
        summary = client.get("/api/admin/product-consolidation/cost-summary", headers=headers)
        jobs = client.get("/api/admin/product-consolidation/jobs", headers=headers)

        assert response.status_code == 200
        assert response.json()["auto_merge_count"] == 1
        assert summary.status_code == 200
        assert jobs.status_code == 200
        assert jobs.json()[0]["status"] == "completed"
    finally:
        app.dependency_overrides.clear()
