from types import SimpleNamespace

from sqlalchemy import text

from app.services.extract_service import ExtractService


TITLE = "신한EZ손해보험, '신한SOL 다이렉트' 할인 확대 및 신규 상품 출시"

TEXT = """
신한EZ손해보험은 2026년 새해를 맞아 고객 혜택을 대폭 강화한 '신한SOL 다이렉트' 보험의 할인 구조 개편과 함께 신규 상품을 선보였다고 밝혔다.

해당 할인 혜택은 운전자보험(티맵 안전운전 점수 연계 '쏠Drive' 서비스), 건강보험(애플·삼성헬스 걸음 수 연동 '쏠Walk' 서비스), 주택화재보험(소화설비 구비 주택 할인) 등 주요 상품 라인업에 적용된다.

또한 신한EZ손해보험은 최근 건강 관리에 대한 사회적 관심이 높아지는 트렌드를 반영해 '면역질환보험'을 신규 출시했다.

해당 상품은 특정 자가면역질환을 비롯해 대상포진, 통풍, 갑상선 기능 저하 등 현대인에게 발병률이 높은 주요 면역 관련 질환을 집중적으로 보장한다.
"""


def bad_extraction_payload():
    return {
        "article_relevance": {"is_relevant": True, "relevance_type": "new_product", "reason": "신규 상품 출시"},
        "products": [
            {
                "identity": {
                    "raw_product_name": "신한SOL",
                    "normalized_product_name_candidate": "신한SOL",
                    "company_name_raw": "신한EZ손해보험",
                    "company_name_candidate": "신한EZ손해보험",
                    "insurance_type": "손해보험",
                    "release_year_month": None,
                    "release_year_month_basis": "unknown",
                },
                "product_type_classification": {
                    "primary_product_type": {"code": "HEALTH_COMPREHENSIVE", "name_ko": "건강(종합)", "basis": "llm", "evidence_text": "건강보험", "confidence": 0.6},
                    "secondary_product_types": [],
                    "needs_human_review": False,
                },
                "structured_features": {"sales_channels": ["신한SOL 다이렉트"]},
                "narrative_insights": {
                    "marketing_summary": "신한SOL 다이렉트 할인 구조 개편",
                    "channel_summary": "쏠Drive/쏠Walk 연계 할인",
                    "coverage_summary": "특정 자가면역질환, 대상포진, 통풍, 갑상선 기능 저하 등 면역 관련 질환 보장",
                },
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
                        "confidence": 0.9,
                        "needs_human_review": False,
                    }
                ],
                "sales_metrics": [],
                "evidence": {
                    "product_name_evidence": "신한SOL 다이렉트",
                    "company_evidence": "신한EZ손해보험은",
                    "coverage_evidence": "해당 상품은 특정 자가면역질환을 비롯해 대상포진, 통풍, 갑상선 기능 저하 등 현대인에게 발병률이 높은 주요 면역 관련 질환을 집중적으로 보장한다.",
                },
                "confidence": {"identity": 0.6, "product_type": 0.6, "features": 0.5, "coverage": 0.9, "sales": 0.0, "narrative": 0.7},
                "needs_human_review": False,
            }
        ],
    }


def verifier_payload():
    return {
        "verification_status": "partial",
        "field_checks": [
            {
                "field_path": "products[0].identity.raw_product_name",
                "extracted_value": "신한SOL",
                "verdict": "incorrect",
                "reason": "신한SOL은 다이렉트 할인 브랜드/채널명이며 본문에서 신규 출시된 상품명은 면역질환보험이다.",
                "suggested_value": "면역질환보험",
                "suggested_basis": "launch_sentence_candidate",
                "evidence_text": "신한EZ손해보험은 최근 건강 관리에 대한 사회적 관심이 높아지는 트렌드를 반영해 '면역질환보험'을 신규 출시했다.",
                "severity": "high",
            }
        ],
        "unsupported_fields": [],
        "inferred_fields": [],
        "corrected_fields": ["products[0].identity.raw_product_name"],
        "overall_confidence": 0.8,
        "needs_human_review": False,
        "recommended_action": "save",
    }


class FakeRouter:
    def run_pipeline(self, input_text):
        return {
            "extractor": SimpleNamespace(
                output_json=bad_extraction_payload(),
                task_type="extract",
                provider="fake",
                model_name="fake-extractor",
                token_input=0,
                token_output=0,
                latency_ms=0,
                cost_estimate=0.0,
            ),
            "verifier": SimpleNamespace(
                output_json=verifier_payload(),
                task_type="verify",
                provider="fake",
                model_name="fake-verifier",
                token_input=0,
                token_output=0,
                latency_ms=0,
                cost_estimate=0.0,
            ),
        }


def test_shinhanez_immune_product_is_saved_after_reconciliation(db_session):
    service = ExtractService(router=FakeRouter())
    result = service._run_and_save(db_session, f"{TITLE}\n\n{TEXT}")
    product_id = result["product_ids"][0]

    product = db_session.execute(
        text(
            """
            SELECT p.raw_product_name, p.normalized_product_name, p.primary_product_type_code,
                   c.company_name_normalized, c.insurance_type
            FROM dim_product p
            LEFT JOIN dim_company c ON c.company_id = p.company_id
            WHERE p.product_id = :product_id
            """
        ),
        {"product_id": product_id},
    ).mappings().one()
    assert product["raw_product_name"] == "면역질환보험"
    assert product["normalized_product_name"] == "면역질환보험"
    assert product["primary_product_type_code"] == "SPECIFIC_DISEASE"
    assert product["company_name_normalized"] == "신한EZ손해보험"
    assert product["insurance_type"] == "손해보험"

    assignment_codes = {
        row[0]
        for row in db_session.execute(
            text("SELECT product_type_code FROM fact_product_type_assignment WHERE product_id = :product_id"),
            {"product_id": product_id},
        ).all()
    }
    assert "SPECIFIC_DISEASE" in assignment_codes

    audits = db_session.execute(
        text(
            """
            SELECT field_path, suggested_value, final_value, final_basis
            FROM fact_extraction_field_audit
            ORDER BY field_audit_id
            """
        )
    ).mappings().all()
    assert any(row["field_path"] == "products[0].identity.raw_product_name" and "면역질환보험" in (row["final_value"] or "") for row in audits)
