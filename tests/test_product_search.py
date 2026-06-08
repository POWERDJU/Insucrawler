from app.services.ingestion_service import IngestionService
from app.services.search_service import SearchService


def seed_search_product(db, release_year_month=None, name="무배당 간편 암보험", product_status="active"):
    IngestionService().upsert_structured_product(
        db,
        {
            "product": {
                "raw_product_name": name,
                "normalized_product_name": name,
                "company_name": "삼성화재",
                "insurance_type": "손해보험",
                "primary_product_type_code": "CANCER",
                "release_year_month": release_year_month,
                "product_status": product_status,
                "confidence_total": 0.95,
                "needs_review": False,
            },
            "product_type_assignments": [
                {"product_type_code": "CANCER", "assignment_role": "primary", "confidence": 0.95},
                {"product_type_code": "SIMPLIFIED_IMPAIRED", "assignment_role": "secondary", "confidence": 0.9},
            ],
            "narrative_insights": {"coverage_summary": "암진단비 중심 보장"},
        },
    )


def seed_special_clause_product(db):
    IngestionService().upsert_structured_product(
        db,
        {
            "product": {
                "raw_product_name": "입원일당 특별약관",
                "normalized_product_name": "입원일당 특별약관",
                "company_name": "삼성화재",
                "insurance_type": "손해보험",
                "primary_product_type_code": "HEALTH_COMPREHENSIVE",
                "confidence_total": 0.95,
                "needs_review": False,
            },
            "product_type_assignments": [
                {"product_type_code": "HEALTH_COMPREHENSIVE", "assignment_role": "primary", "confidence": 0.95},
            ],
        },
    )


def seed_rider_product(db):
    IngestionService().upsert_structured_product(
        db,
        {
            "product": {
                "raw_product_name": "입원일당 특약",
                "normalized_product_name": "입원일당 특약",
                "company_name": "삼성화재",
                "insurance_type": "손해보험",
                "primary_product_type_code": "HEALTH_COMPREHENSIVE",
                "confidence_total": 0.95,
                "needs_review": False,
            },
            "product_type_assignments": [
                {"product_type_code": "HEALTH_COMPREHENSIVE", "assignment_role": "primary", "confidence": 0.95},
            ],
        },
    )


def test_partial_product_search_absorbs_space(db_session):
    seed_search_product(db_session)
    result = SearchService().search_products(db_session, q="간편암", include_review=False)
    assert len(result) == 1
    assert result[0]["company_name"] == "삼성화재"


def test_product_search_excludes_special_clause_products(db_session):
    seed_search_product(db_session)
    seed_special_clause_product(db_session)
    seed_rider_product(db_session)

    result = SearchService().search_products(db_session, include_review=False)

    names = {item["normalized_product_name"] for item in result}
    assert "입원일당 특별약관" not in names
    assert "입원일당 특약" not in names
    assert len(result) == 1


def test_product_search_excludes_review_status_even_when_review_flag_included(db_session):
    seed_search_product(db_session, name="검색 정상 암보험", product_status="active")
    seed_search_product(db_session, name="검색 상태 리뷰 암보험", product_status="review")

    result = SearchService().search_products(db_session, include_review=True)

    names = {item["normalized_product_name"] for item in result}
    assert names == {"검색 정상 암보험"}


def test_company_filter(db_session):
    seed_search_product(db_session)
    result = SearchService().search_products(db_session, company_name="삼성", include_review=False)
    assert len(result) == 1


def test_product_type_filter_primary(db_session):
    seed_search_product(db_session)
    result = SearchService().search_products(db_session, product_type_code="CANCER", include_review=False)
    assert len(result) == 1


def test_product_type_filter_ignores_secondary_flag(db_session):
    seed_search_product(db_session)
    result = SearchService().search_products(db_session, product_type_code="SIMPLIFIED_IMPAIRED", include_secondary_types=True, include_review=False)
    assert len(result) == 0


def test_product_search_hides_release_month_outside_visible_period(db_session):
    seed_search_product(db_session, release_year_month="2022-12")

    result = SearchService().search_products(db_session, include_review=False)

    assert len(result) == 1
    assert result[0]["release_year_month"] == ""
