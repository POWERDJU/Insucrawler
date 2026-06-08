from app.services.ingestion_service import IngestionService
from app.services.pivot_service import PivotService


def seed_products(db):
    service = IngestionService()
    service.upsert_structured_product(
        db,
        {
            "product": {
                "raw_product_name": "무배당 간편암보험",
                "normalized_product_name": "무배당 간편암보험",
                "company_name": "삼성화재",
                "insurance_type": "손해보험",
                "release_year_month": "2026-05",
                "primary_product_type_code": "CANCER",
                "confidence_total": 0.9,
                "needs_review": False,
            },
            "product_type_assignments": [
                {"product_type_code": "CANCER", "assignment_role": "primary", "confidence": 0.95},
                {"product_type_code": "SIMPLIFIED_IMPAIRED", "assignment_role": "secondary", "confidence": 0.9},
            ],
            "major_coverages": [
                {"coverage_name_raw": "암진단비", "risk_area": "암", "benefit_type": "진단", "detail_level": "exact_coverage", "evidence_text": "암진단비 최대 1억원", "max_amount_krw": 100000000, "confidence": 0.9},
                {"coverage_name_raw": "항암약물치료비", "risk_area": "암", "benefit_type": "치료", "detail_level": "coverage_group", "evidence_text": "항암약물치료비 보장", "confidence": 0.8},
            ],
            "sales_metrics": [
                {"metric_name": "판매건수", "metric_value": 100, "metric_unit": "건", "evidence_text": "판매건수 100건", "confidence": 0.9},
                {"metric_name": "판매건수", "metric_value": 200, "metric_unit": "건", "evidence_text": "판매건수 200건", "confidence": 0.9},
            ],
        },
    )


def test_primary_only_counts_product_once(db_session):
    seed_products(db_session)
    result = PivotService().run_pivot(
        db_session,
        "product",
        "primary_only",
        rows=["product_type_code"],
        columns=[],
        filters={},
        metrics=[{"name": "product_count", "agg": "count_distinct", "field": "product_id"}],
        include_review=False,
    )
    assert result["records"] == [{"product_type_code": "CANCER", "product_count": 1}]


def test_include_secondary_mode_is_treated_as_primary_only(db_session):
    seed_products(db_session)
    result = PivotService().run_pivot(
        db_session,
        "product",
        "include_secondary",
        rows=["product_type_code"],
        columns=[],
        filters={},
        metrics=[{"name": "product_count", "agg": "count_distinct", "field": "product_id"}],
        include_review=False,
    )
    counts = {row["product_type_code"]: row["product_count"] for row in result["records"]}
    assert counts["CANCER"] == 1
    assert "SIMPLIFIED_IMPAIRED" not in counts


def test_columns_empty_with_company_and_product_type_rows(db_session):
    seed_products(db_session)
    result = PivotService().run_pivot(
        db_session,
        "product",
        "include_secondary",
        rows=["company_name", "product_type_name"],
        columns=[],
        filters={},
        metrics=[
            {"name": "product_count", "agg": "count_distinct", "field": "product_id"},
            {"name": "article_count", "agg": "sum", "field": "article_count"},
        ],
        include_review=False,
    )

    assert result["columns"] == []
    counts = {(row["company_name"], row["product_type_name"]): row["product_count"] for row in result["records"]}
    assert counts[("삼성화재", "암보험")] == 1
    assert ("삼성화재", "간편(유병자)") not in counts


def test_coverage_grain_distinct_product_count(db_session):
    seed_products(db_session)
    result = PivotService().run_pivot(
        db_session,
        "coverage",
        "primary_only",
        rows=["company_name"],
        columns=[],
        filters={},
        metrics=[
            {"name": "product_count", "agg": "count_distinct", "field": "product_id"},
            {"name": "coverage_count", "agg": "count_distinct", "field": "coverage_id"},
        ],
        include_review=False,
    )
    assert result["records"][0]["product_count"] == 1
    assert result["records"][0]["coverage_count"] == 2


def test_coverage_pivot_with_product_type_and_risk_area_rows(db_session):
    seed_products(db_session)
    result = PivotService().run_pivot(
        db_session,
        "coverage",
        "include_secondary",
        rows=["product_type_name", "risk_area"],
        columns=[],
        filters={},
        metrics=[
            {"name": "product_count", "agg": "count_distinct", "field": "product_id"},
            {"name": "coverage_count", "agg": "count_distinct", "field": "coverage_id"},
        ],
        include_review=False,
    )

    assert result["columns"] == []
    counts = {(row["product_type_name"], row["risk_area"]): row for row in result["records"]}
    assert counts[("암보험", "암")]["product_count"] == 1
    assert counts[("암보험", "암")]["coverage_count"] == 2


def test_sales_metric_grain_sum_without_product_duplication(db_session):
    seed_products(db_session)
    result = PivotService().run_pivot(
        db_session,
        "sales",
        "primary_only",
        rows=["company_name"],
        columns=[],
        filters={},
        metrics=[
            {"name": "product_count", "agg": "count_distinct", "field": "product_id"},
            {"name": "sales_metric_sum", "agg": "sum", "field": "metric_value"},
        ],
        include_review=False,
    )
    assert result["records"][0]["product_count"] == 1
    assert result["records"][0]["sales_metric_sum"] == 300
