from app.db import repository


def test_upsert_product_uses_company_dictionary_insurance_type_when_llm_unknown(db_session):
    product = repository.upsert_product(
        db_session,
        {
            "raw_product_name": "현대해상 간편 건강보험",
            "normalized_product_name": "현대해상 간편 건강보험",
            "company_name": "현대해상",
            "insurance_type": "unknown",
            "primary_product_type_code": "HEALTH_COMPREHENSIVE",
        },
    )

    assert product.insurance_type == "손해보험"
