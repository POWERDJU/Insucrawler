from app.classifiers.product_type_classifier import ProductTypeClassifier


def classify(name):
    return ProductTypeClassifier().classify(name)


def assert_primary(name, code):
    assert classify(name).primary.code == code


def test_existing_classifications_remain_supported():
    result = classify("간편암보험")
    assert result.primary.code == "CANCER"
    assert any(item.code == "SIMPLIFIED_IMPAIRED" for item in result.secondary)

    result = classify("어린이 종합보험")
    assert result.primary.code == "CHILD_ADULT_CHILD"
    assert any(item.code == "HEALTH_COMPREHENSIVE" for item in result.secondary)

    assert_primary("운전자보험", "ACCIDENT_DRIVER")
    assert_primary("치매간병보험", "DEMENTIA_CARE")
    assert_primary("종신보험", "DEATH_WHOLELIFE")
    assert_primary("화재보험", "PROPERTY_EXPENSE")


def test_new_market_product_type_classifications():
    examples = {
        "면역질환보험": "SPECIFIC_DISEASE",
        "심뇌혈관보험": "SPECIFIC_DISEASE",
        "실손의료보험": "MEDICAL_INDEMNITY",
        "실비보험": "MEDICAL_INDEMNITY",
        "자동차보험": "AUTO",
        "펫보험": "PET",
        "반려동물보험": "PET",
        "치아보험": "DENTAL",
        "여행자보험": "TRAVEL_LEISURE",
        "골프보험": "TRAVEL_LEISURE",
        "정기보험": "DEATH_WHOLELIFE",
        "연금보험": "ANNUITY_SAVINGS",
        "저축보험": "ANNUITY_SAVINGS",
        "보증보험": "GUARANTEE_CREDIT",
        "전세금보장보험": "GUARANTEE_CREDIT",
        "단체보험": "CORPORATE_GROUP_SPECIALTY",
    }
    for name, code in examples.items():
        assert_primary(name, code)


def test_auto_and_driver_are_separate():
    assert_primary("자동차보험", "AUTO")
    assert_primary("운전자보험", "ACCIDENT_DRIVER")


def test_variable_products_use_secondary_modifier():
    result = classify("변액종신보험")
    assert result.primary.code == "DEATH_WHOLELIFE"
    assert any(item.code == "VARIABLE_UL" for item in result.secondary)

    result = classify("변액연금보험")
    assert result.primary.code == "ANNUITY_SAVINGS"
    assert any(item.code == "VARIABLE_UL" for item in result.secondary)
