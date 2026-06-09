from app.extractors.extraction_schema import validate_extraction_payload, validate_verification_payload
from app.services.extract_service import normalize_extraction_payload, normalize_verification_payload


def test_normalize_qwen_field_verdict_map_to_verification_result():
    payload = {
        "article_relevance": {"is_relevant": "supported"},
        "products": [
            {
                "identity": {
                    "raw_product_name": "supported",
                    "release_year_month": "inferred",
                },
                "major_coverages": "unsupported",
            }
        ],
    }

    normalized = normalize_verification_payload(payload)
    result = validate_verification_payload(normalized)

    assert result.verification_status == "partial"
    assert result.needs_human_review is True
    assert "products[0].major_coverages" in result.unsupported_fields
    assert "products[0].identity.release_year_month" in result.inferred_fields
    assert {check.field_path for check in result.field_checks} >= {
        "article_relevance.is_relevant",
        "products[0].identity.raw_product_name",
        "products[0].identity.release_year_month",
        "products[0].major_coverages",
    }


def test_normalize_extraction_payload_handles_common_llm_shape_drift():
    payload = {
        "article_relevance": {"is_relevant": True, "relevance_type": "new_product | product_feature"},
        "products": [
            {
                "identity": {
                    "raw_product_name": "테스트보험",
                    "company_name_candidate": "테스트손해보험",
                    "insurance_type": "손해보험",
                    "release_year_month": "2026년 1월",
                },
                "product_type_classification": {
                    "primary_product_type": {"code": "OTHER", "name_ko": "기타"},
                    "secondary_product_types": [],
                },
                "structured_features": {"sales_channels": [123]},
                "major_coverages": [{"coverage_name_raw": "치료비", "detail_level": "detailed", "benefit_type": {"kind": "fixed"}}],
                "evidence": {"product_name_evidence": "테스트보험", "company_evidence": "테스트손해보험"},
            }
        ],
    }

    normalized = normalize_extraction_payload(payload)
    result = validate_extraction_payload(normalized)

    assert result.article_relevance.relevance_type == "new_product"
    assert result.products[0].identity.release_year_month == "2026-01"
    assert result.products[0].structured_features.sales_channels == ["123"]
    assert result.products[0].major_coverages[0].detail_level == "unknown"
    assert result.products[0].major_coverages[0].benefit_type == "unknown"


def test_normalize_extraction_payload_coerces_sales_metric_values():
    payload = {
        "article_relevance": {"is_relevant": True, "relevance_type": "sales_performance"},
        "products": [
            {
                "identity": {
                    "raw_product_name": "Test Product",
                    "company_name_candidate": "Test Company",
                    "insurance_type": "unknown",
                    "release_year_month": None,
                },
                "product_type_classification": {
                    "primary_product_type": {"code": "OTHER", "name_ko": "Other"},
                    "secondary_product_types": [],
                },
                "sales_metrics": [
                    {"metric_name": "prescriptions", "metric_value": "300만", "metric_unit": "건", "evidence_text": "300만건"},
                    {"metric_name": "premium", "metric_value": None, "metric_unit": "원", "evidence_text": "premium mentioned"},
                ],
                "evidence": {"product_name_evidence": "Test Product", "company_evidence": "Test Company"},
            }
        ],
    }

    normalized = normalize_extraction_payload(payload)
    result = validate_extraction_payload(normalized)

    assert result.products[0].sales_metrics[0].metric_value == 3000000
    assert result.products[0].sales_metrics[1].metric_value == 0
    assert result.products[0].sales_metrics[1].needs_human_review is True
