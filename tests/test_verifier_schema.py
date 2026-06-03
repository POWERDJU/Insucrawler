from app.db import repository
from app.extractors.extraction_schema import validate_verification_payload


def test_verifier_schema_and_field_audit_storage(db_session):
    payload = {
        "verification_status": "conflict",
        "field_checks": [
            {
                "field_path": "products[0].identity.release_year_month",
                "extracted_value": "2026-05",
                "verdict": "unsupported",
                "reason": "기사에는 출시월이 없다",
                "suggested_value": None,
                "suggested_basis": "unknown",
                "evidence_text": None,
                "severity": "critical",
            },
            {
                "field_path": "products[0].identity.company_name",
                "extracted_value": "삼성화재",
                "verdict": "inferred",
                "reason": "문맥상 추정",
                "suggested_value": "삼성화재",
                "suggested_basis": "company_dictionary",
                "evidence_text": "삼성화재",
                "severity": "medium",
            },
            {
                "field_path": "products[0].major_coverages[0].max_amount_krw",
                "extracted_value": 10000000,
                "verdict": "incorrect",
                "reason": "단위 오류",
                "suggested_value": 100000000,
                "suggested_basis": "deterministic_normalizer",
                "evidence_text": "1억원",
                "severity": "high",
            },
        ],
        "unsupported_fields": ["products[0].identity.release_year_month"],
        "inferred_fields": ["products[0].identity.company_name"],
        "corrected_fields": ["products[0].major_coverages[0].max_amount_krw"],
        "overall_confidence": 0.4,
        "needs_human_review": True,
        "recommended_action": "adjudicate",
    }
    verification = validate_verification_payload(payload)
    assert verification.needs_human_review is True
    run = repository.create_llm_run(
        db_session,
        task_type="extract",
        provider="gemini",
        model_name="fake",
        input_hash="x",
        validation_status="pass",
    )
    comparison = repository.create_comparison(
        db_session,
        extractor_run_id=run.llm_run_id,
        agreement_score=0.4,
        conflict_count=3,
        critical_conflict_count=1,
        final_status="conflict",
        needs_human_review=True,
    )
    for check in verification.field_checks:
        repository.create_field_audit(db_session, comparison.comparison_id, check.model_dump())
    db_session.commit()
    assert len(verification.unsupported_fields) == 1
    assert len(verification.inferred_fields) == 1
    assert len(verification.corrected_fields) == 1
