from app.services.product_type_industry_validation_service import ProductTypeIndustryValidationService


def test_invalid_nonlife_representative_types_are_excluded():
    service = ProductTypeIndustryValidationService()

    for code in ["DEATH_WHOLELIFE", "VARIABLE_UL"]:
        result = service.validate(insurance_type="손해보험", primary_product_type_code=code, product_name="테스트 상품")
        assert result.valid is False
        assert result.proposed_status == "excluded_invalid_industry_product_type"
        assert result.exclusion_reason == "invalid_industry_product_type"


def test_invalid_life_representative_types_are_excluded():
    service = ProductTypeIndustryValidationService()

    for code in ["AUTO", "TRAVEL_LEISURE", "PET", "PROPERTY_EXPENSE"]:
        result = service.validate(insurance_type="생명보험", primary_product_type_code=code, product_name="테스트 상품")
        assert result.valid is False
        assert result.proposed_status == "excluded_invalid_industry_product_type"


def test_unknown_industry_is_review_not_auto_excluded():
    result = ProductTypeIndustryValidationService().validate(insurance_type="unknown", primary_product_type_code="AUTO")
    assert result.valid is True
    assert result.needs_review is True
