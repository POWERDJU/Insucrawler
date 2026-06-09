from app.normalizers.korean_description_normalizer import is_english_like, koreanize_description_text


def test_koreanize_common_product_summary_sentence():
    text = "This is a discount rider for automobile insurance that offers a 2% discount."

    result = koreanize_description_text(text, "feature_summary")

    assert result == "자동차보험 가입자가 조건을 충족하면 보험료 2% 할인을 받을 수 있는 특약입니다."
    assert not is_english_like(result)


def test_koreanize_qwen_correction_summary():
    text = "Corrected canonical_product_name and release_year_month based on explicit article evidence."

    result = koreanize_description_text(text, "partner_context_summary")

    assert result == "상품명, 출시월을 기사 근거에 맞춰 보정했습니다. 보정 근거는 기사 내 명시 표현입니다."
    assert not is_english_like(result)


def test_strip_duplicate_english_parenthetical_when_korean_exists():
    text = "업계 최초로 배타적사용권을 취득한 담보입니다. (Industry-first exclusive-use-right coverage.)"

    result = koreanize_description_text(text, "feature_summary")

    assert result == "업계 최초로 배타적사용권을 취득한 담보입니다."
    assert not is_english_like(result)


def test_koreanize_missing_info_summary():
    text = "Specific coverage details, benefit amounts, and sales performance are not provided in the snippet."

    result = koreanize_description_text(text, "missing_info_summary")

    assert result == "구체적인 보장 세부내용, 보험금액, 판매 실적 등은 기사 요약문에서 확인되지 않습니다."
    assert not is_english_like(result)
