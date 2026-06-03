from app.extractors.exclusive_right_schema import validate_exclusive_right_payload


def test_exclusive_right_extraction_schema_accepts_acquired_payload():
    payload = {
        "exclusive_right_relevance": {"is_relevant": True, "status": "acquired", "reason": "획득 기사"},
        "exclusive_rights": [
            {
                "company_name_raw": "한화손보",
                "company_name_candidate": "한화손해보험",
                "insurance_type_candidate": "손해보험",
                "exclusive_right_type": {
                    "code": "NEW_RISK_COVERAGE",
                    "name_ko": "새로운 위험 담보",
                    "evidence_text": "새로운 위험 담보",
                    "confidence": 0.9,
                },
                "subject": {
                    "subject_type": "product",
                    "raw_subject_name": "OO보험",
                    "normalized_subject_name_candidate": "OO보험",
                    "subject_core_key": "oo보험",
                },
                "exclusivity": {"months": 6, "period_text": "6개월", "evidence_text": "6개월 배타적사용권"},
                "acquired": {"year_month": "2026-01", "basis": "explicit_in_article", "date_text": "2026년 1월"},
                "feature_summary": "새로운 위험 담보",
                "confidence": 0.82,
                "needs_review": False,
            }
        ],
    }

    result = validate_exclusive_right_payload(payload)

    assert result.exclusive_right_relevance.status == "acquired"
    assert result.exclusive_rights[0].exclusivity.months == 6
    assert result.exclusive_rights[0].subject.raw_subject_name == "OO보험"
    assert not hasattr(result.exclusive_rights[0], "exclusive_right_type")
    assert not hasattr(result.exclusive_rights[0].subject, "subject_type")
    assert not hasattr(result.exclusive_rights[0].acquired, "basis")
