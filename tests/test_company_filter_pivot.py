from app.services.ingestion_service import IngestionService
from app.services.pivot_service import PivotService
from app.services.search_service import SearchService


def seed_company_filter_products(db):
    service = IngestionService()
    service.upsert_structured_product(
        db,
        {
            "product": {
                "raw_product_name": "코리안리 재보험 상품 예시",
                "normalized_product_name": "코리안리 재보험 상품 예시",
                "company_name": "코리안리",
                "insurance_type": "손해보험",
                "primary_product_type_code": "OTHER",
                "confidence_total": 0.9,
                "needs_review": False,
            },
            "product_type_assignments": [{"product_type_code": "OTHER", "assignment_role": "primary", "confidence": 0.8}],
        },
    )
    service.upsert_structured_product(
        db,
        {
            "product": {
                "raw_product_name": "캐롯 합병 전 상품 예시",
                "normalized_product_name": "캐롯 합병 전 상품 예시",
                "company_name": "캐롯손보",
                "insurance_type": "손해보험",
                "primary_product_type_code": "ACCIDENT_DRIVER",
                "confidence_total": 0.9,
                "needs_review": False,
            },
            "product_type_assignments": [{"product_type_code": "ACCIDENT_DRIVER", "assignment_role": "primary", "confidence": 0.85}],
        },
    )
    service.upsert_structured_product(
        db,
        {
            "product": {
                "raw_product_name": "DGB alias 건강보험",
                "normalized_product_name": "DGB alias 건강보험",
                "company_name": "DGB생명",
                "insurance_type": "생명보험",
                "primary_product_type_code": "HEALTH_COMPREHENSIVE",
                "confidence_total": 0.9,
                "needs_review": False,
            },
            "product_type_assignments": [{"product_type_code": "HEALTH_COMPREHENSIVE", "assignment_role": "primary", "confidence": 0.85}],
        },
    )


def test_default_pivot_excludes_reinsurers_and_option_includes_them(db_session):
    seed_company_filter_products(db_session)
    service = PivotService()

    default_result = service.run_pivot(
        db_session,
        "product",
        "primary_only",
        rows=["company_name"],
        columns=[],
        filters={},
        metrics=[{"name": "product_count", "agg": "count_distinct", "field": "product_id"}],
    )
    default_companies = {row["company_name"] for row in default_result["records"]}
    assert "코리안리재보험" not in default_companies

    expanded = service.run_pivot(
        db_session,
        "product",
        "primary_only",
        rows=["company_name"],
        columns=[],
        filters={"_company_include_roles": ["reinsurer"]},
        metrics=[{"name": "product_count", "agg": "count_distinct", "field": "product_id"}],
    )
    expanded_companies = {row["company_name"] for row in expanded["records"]}
    assert "코리안리재보험" in expanded_companies


def test_company_status_filter_and_alias_search(db_session):
    seed_company_filter_products(db_session)

    merged = PivotService().run_pivot(
        db_session,
        "product",
        "primary_only",
        rows=["company_name", "status_2024_2026"],
        columns=[],
        filters={"status_2024_2026": ["merged"]},
        metrics=[{"name": "product_count", "agg": "count_distinct", "field": "product_id"}],
    )
    assert merged["records"] == [{"company_name": "캐롯손해보험", "status_2024_2026": "merged", "product_count": 1}]

    found = SearchService().search_products(db_session, q="DGB생명", include_review=False)
    assert any(item["company_name"] == "iM라이프생명" for item in found)
