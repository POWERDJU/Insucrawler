from app.services.qwen_adjudication_service import QwenAdjudicationService


def test_qwen_hard_gate_rejects_invalid_month_and_missing_company():
    errors = QwenAdjudicationService().validate_hard_gates(
        {
            "decision": "accept",
            "release_year_month": "2026-99",
            "article_suitability": "product_launch_supported",
        }
    )

    assert "company_master_absent" in errors
    assert "invalid_release_year_month" in errors


def test_qwen_hard_gate_rejects_reinsurer_accept():
    errors = QwenAdjudicationService().validate_hard_gates(
        {
            "decision": "accept",
            "company_id": 1,
            "company_role": "reinsurer",
            "release_year_month": "2026-05",
        }
    )

    assert "ineligible_company_role" in errors
