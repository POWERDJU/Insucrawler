from app.services.product_final_adjudication_service import ProductFinalAdjudicationService


class CorrectingProvider:
    def adjudicate_product(self, payload):
        return {
            "decision": "accept",
            "canonical_product_name": "시그니처 여성건강보험 4.0",
            "company_name": "한화손해보험",
            "product_type_code": "HEALTH_COMPREHENSIVE",
            "release_year_month": "2026-04",
            "release_year_month_basis": "explicit_in_article",
            "partner_company_name": "테스트은행",
            "partner_role": "distribution_partner",
            "article_suitability": "product_launch_supported",
            "correction_summary": "release month and partner structure corrected",
            "reason": "local article context supports the corrected fields",
            "evidence_quote": "한화손해보험은 2026년 4월 시그니처 여성건강보험 4.0을 테스트은행과 제휴해 출시했다.",
            "confidence": 0.91,
        }


def test_product_final_adjudication_can_correct_release_month_and_combination(db_session):
    service = ProductFinalAdjudicationService(provider=CorrectingProvider())

    payload = service.build_input(
        db_session,
        product_name="이에 손해보험",
        company_name="한화손해보험",
        product_type_code="UNKNOWN",
        release_year_month=None,
        release_year_month_basis="unknown",
        partner_company_name=None,
        partner_role=None,
        partner_context_summary="은행 제휴 판매 기사",
        context_text="한화손해보험은 2026년 4월 시그니처 여성건강보험 4.0을 테스트은행과 제휴해 출시했다.",
    )
    decision = service.adjudicate(db_session, payload)

    assert decision.provider_called is True
    assert decision.decision == "accept"
    assert decision.canonical_product_name == "시그니처 여성건강보험 4.0"
    assert decision.release_year_month == "2026-04"
    assert decision.release_year_month_basis == "explicit_in_article"
    assert decision.partner_company_name == "테스트은행"
    assert decision.article_suitability == "product_launch_supported"
