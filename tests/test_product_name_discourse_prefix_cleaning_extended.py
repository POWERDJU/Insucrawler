from app.normalizers.product_name_normalizer import clean_product_name_candidate, validate_product_name_before_save
from app.services.product_name_validation_service import ProductNameValidationService


def test_extended_discourse_prefixes_are_removed_or_rejected():
    assert clean_product_name_candidate("한편 시그니처 여성건강보험") == "시그니처 여성건강보험"
    assert clean_product_name_candidate("이에 손해보험") == "손해보험"
    assert clean_product_name_candidate("나아가 장기 보장성보험") == "장기 보장성보험"

    assert validate_product_name_before_save("이에 손해보험").accepted is False
    assert validate_product_name_before_save("먼저보험").accepted is False
    assert validate_product_name_before_save("우선보험").accepted is False
    assert validate_product_name_before_save("이밖에보험").accepted is False
    assert validate_product_name_before_save("따라보험").accepted is False
    assert validate_product_name_before_save("결합한보험").accepted is False
    assert validate_product_name_before_save("12일 사망보험").accepted is False


def test_model_person_name_is_not_product():
    decision = ProductNameValidationService().validate(
        "이기우와 반려견보험",
        context_text="DB손해보험은 배우 이기우를 광고 모델로 발탁하고 반려견보험 캠페인 영상을 공개했다.",
    )

    assert decision.accepted is False
    assert decision.reason == "model_person_name_as_product"
