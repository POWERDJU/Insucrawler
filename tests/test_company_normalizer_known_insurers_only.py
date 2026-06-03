from app.normalizers.company_normalizer import CompanyNormalizer


def test_regional_nonghyup_is_not_confirmed_as_insurer():
    match = CompanyNormalizer().normalize("경남농협")

    assert match.company_name_normalized is None
    assert match.match_type == "unknown_org_candidate"
    assert match.needs_review is True


def test_known_nonghyup_insurer_aliases_are_confirmed():
    normalizer = CompanyNormalizer()

    assert normalizer.normalize("농협손보").company_name_normalized == "NH농협손해보험"
    assert normalizer.normalize("농협생명").company_name_normalized == "NH농협생명"


def test_context_can_detect_known_insurer_but_not_regional_org():
    normalizer = CompanyNormalizer()

    assert normalizer.detect_all("경남농협이 보험 관련 행사를 진행했다") == []
    matches = normalizer.detect_all("경남농협과 NH농협손해보험이 보험상품을 소개했다")
    assert matches[0].company_name_normalized == "NH농협손해보험"


def test_general_known_insurer_aliases_still_match():
    normalizer = CompanyNormalizer()

    assert normalizer.normalize("삼성화재 신상품 출시").company_name_normalized == "삼성화재"
    assert normalizer.normalize("한화손보 시그니처 여성건강보험").company_name_normalized == "한화손해보험"
