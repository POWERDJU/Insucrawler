from app.normalizers.company_normalizer import CompanyNormalizer


def test_company_alias_normalizer_maps_key_renames_and_brands():
    normalizer = CompanyNormalizer()
    cases = {
        "DGB생명": "iM라이프생명",
        "iM라이프": "iM라이프생명",
        "MG손보": "MG손해보험",
        "예별손보": "예별손해보험",
        "캐롯손보": "캐롯손해보험",
        "마이브라운": "마이브라운반려동물전문보험",
        "에이스손해보험": "라이나손해보험",
        "BNP카디프손보": "신한EZ손해보험",
        "동부화재": "DB손해보험",
        "LIG손해보험": "KB손해보험",
    }
    for raw, expected in cases.items():
        match = normalizer.normalize(raw)
        assert match is not None
        assert match.company_name_normalized == expected
        assert match.match_type in {"alias", "normalized"}


def test_company_detect_all_returns_multiple_candidates():
    matches = CompanyNormalizer().detect_all("DGB생명과 캐롯손보가 상품 관련 뉴스를 냈다")
    names = {item.company_name_normalized for item in matches}
    assert {"iM라이프생명", "캐롯손해보험"} <= names
