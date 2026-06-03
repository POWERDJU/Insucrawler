from app.extractors.extraction_schema import validate_extraction_payload
from app.extractors.product_name_reconciliation import reconcile_extraction


TEXT = """
신한EZ손해보험은 2026년 새해를 맞아 고객 혜택을 대폭 강화한 '신한SOL 다이렉트' 보험의 할인 구조 개편과 함께 신규 상품을 선보였다고 밝혔다.
또한 신한EZ손해보험은 최근 건강 관리에 대한 사회적 관심이 높아지는 트렌드를 반영해 '면역질환보험'을 신규 출시했다.
해당 상품은 특정 자가면역질환을 비롯해 대상포진, 통풍, 갑상선 기능 저하 등 현대인에게 발병률이 높은 주요 면역 관련 질환을 집중적으로 보장한다.
"""


def extraction_payload(product_name="신한SOL", product_type="HEALTH_COMPREHENSIVE"):
    return {
        "article_relevance": {"is_relevant": True, "relevance_type": "new_product", "reason": "신규 상품 출시"},
        "products": [
            {
                "identity": {
                    "raw_product_name": product_name,
                    "normalized_product_name_candidate": product_name,
                    "company_name_raw": "신한EZ손해보험",
                    "company_name_candidate": "신한EZ손해보험",
                    "insurance_type": "손해보험",
                    "release_year_month": None,
                    "release_year_month_basis": "unknown",
                },
                "product_type_classification": {
                    "primary_product_type": {"code": product_type, "name_ko": "건강(종합)", "basis": "llm", "evidence_text": product_name, "confidence": 0.6},
                    "secondary_product_types": [],
                    "needs_human_review": False,
                },
                "structured_features": {},
                "narrative_insights": {},
                "missing_fields": [],
                "major_coverages": [
                    {
                        "coverage_name_raw": "면역 관련 질환",
                        "coverage_name_normalized": "면역 관련 질환",
                        "risk_area": "면역",
                        "benefit_type": "unknown",
                        "coverage_summary": "특정 자가면역질환, 대상포진, 통풍, 갑상선 기능 저하 등 면역 관련 질환 보장",
                        "detail_level": "coverage_group",
                        "is_main_coverage": True,
                        "display_order": 1,
                        "evidence_text": "해당 상품은 특정 자가면역질환을 비롯해 대상포진, 통풍, 갑상선 기능 저하 등 현대인에게 발병률이 높은 주요 면역 관련 질환을 집중적으로 보장한다.",
                        "confidence": 0.85,
                        "needs_human_review": False,
                    }
                ],
                "sales_metrics": [],
                "evidence": {"product_name_evidence": "신한SOL 다이렉트", "company_evidence": "신한EZ손해보험"},
                "confidence": {"identity": 0.6, "product_type": 0.6, "features": 0.0, "coverage": 0.8, "sales": 0.0, "narrative": 0.0},
                "needs_human_review": False,
            }
        ],
    }


def test_reconciliation_replaces_negative_service_name_with_launch_product():
    extraction = validate_extraction_payload(extraction_payload())
    reconciled, corrections = reconcile_extraction(extraction, TEXT)
    product = reconciled.products[0]

    assert product.identity.raw_product_name == "면역질환보험"
    assert product.identity.normalized_product_name_candidate == "면역질환보험"
    assert product.evidence.product_name_evidence and "면역질환보험" in product.evidence.product_name_evidence
    assert any(item["field_path"] == "products[0].identity.raw_product_name" for item in corrections)


def test_reconciliation_overrides_health_comprehensive_for_immune_product():
    extraction = validate_extraction_payload(extraction_payload(product_name="면역질환보험", product_type="HEALTH_COMPREHENSIVE"))
    reconciled, corrections = reconcile_extraction(extraction, TEXT)

    product = reconciled.products[0]
    assert product.product_type_classification.primary_product_type.code == "SPECIFIC_DISEASE"
    assert any(item["field_path"] == "products[0].product_type_classification.primary_product_type.code" for item in corrections)


def test_negative_service_name_without_launch_candidate_is_not_kept_as_product():
    extraction = validate_extraction_payload(extraction_payload(product_name="신한SOL", product_type="UNKNOWN"))
    reconciled, _ = reconcile_extraction(extraction, "신한SOL 다이렉트 할인 혜택을 확대했다.")

    product = reconciled.products[0]
    assert product.identity.raw_product_name is None
    assert product.identity.normalized_product_name_candidate is None
    assert product.needs_human_review is True
