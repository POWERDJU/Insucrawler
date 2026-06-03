from app.extractors.extraction_schema import extraction_save_issues, validate_extraction_payload


def valid_payload():
    return {
        "article_relevance": {"is_relevant": True, "relevance_type": "new_product", "reason": "상품 출시"},
        "products": [
            {
                "identity": {
                    "raw_product_name": "간편암보험",
                    "normalized_product_name_candidate": "간편암보험",
                    "company_name_raw": "삼성화재",
                    "company_name_candidate": "삼성화재",
                    "insurance_type": "손해보험",
                    "release_year_month": "2026-05",
                    "release_year_month_basis": "explicit_in_article",
                },
                "product_type_classification": {
                    "primary_product_type": {"code": "CANCER", "name_ko": "암보험", "basis": "상품명", "evidence_text": "간편암보험", "confidence": 0.9},
                    "secondary_product_types": [],
                    "needs_human_review": False,
                },
                "evidence": {"product_name_evidence": "간편암보험", "company_evidence": "삼성화재"},
                "confidence": {"identity": 0.9, "product_type": 0.9, "features": 0.5, "coverage": 0.5, "sales": 0.5, "narrative": 0.6},
            }
        ],
    }


def test_llm_json_schema_validation_passes():
    result = validate_extraction_payload(valid_payload())
    assert result.products[0].identity.raw_product_name == "간편암보험"


def test_missing_evidence_marks_review_or_issue():
    payload = valid_payload()
    payload["products"][0]["evidence"] = {}
    result = validate_extraction_payload(payload)
    assert result.products[0].needs_human_review is True
    assert extraction_save_issues(result)
