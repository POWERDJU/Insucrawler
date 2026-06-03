from app.normalizers.product_name_normalizer import (
    build_product_identity_key,
    normalize_product_name,
    normalize_product_name_core,
    product_core_key_candidates,
)


HANWHA_ALIASES = ["한화손해보험", "한화손보", "한화화재"]


def test_company_prefix_and_spacing_share_same_product_core_key():
    names = [
        "한화손해보험 시그니처 여성건강 보험 4.0",
        "한화손보 시그니처 여성건강보험 4.0",
        "시그니처 여성건강 보험 4.0",
        "시그니처 여성건강보험 4.0",
    ]

    keys = {normalize_product_name_core(name, HANWHA_ALIASES) for name in names}

    assert keys == {"시그니처여성건강보험4.0"}


def test_spacing_difference_does_not_change_core_key():
    assert normalize_product_name_core("시그니처 여성건강 보험 4.0", HANWHA_ALIASES) == normalize_product_name_core(
        "시그니처여성건강보험 4.0",
        HANWHA_ALIASES,
    )


def test_company_id_is_part_of_product_identity_key():
    raw_name = "간편건강보험"

    assert build_product_identity_key(1, raw_name, []) != build_product_identity_key(2, raw_name, [])


def test_version_dot_is_preserved():
    assert normalize_product_name_core("보험 4.0", []) != normalize_product_name_core("보험 40", [])


def test_samsung_internet_channel_prefix_does_not_change_core_key():
    aliases = ["삼성생명", "삼성생명보험"]
    names = [
        "삼성인터넷(신간편)뇌심건강보험",
        "삼성 인터넷 (신간편) 뇌심건강보험",
        "(신간편)뇌심 건강보험",
        "신간편 뇌심 건강보험",
    ]

    assert {normalize_product_name(name, aliases) for name in names} == {"신간편 뇌심건강보험", "신간편 뇌심 건강보험"}
    assert {normalize_product_name_core(name, aliases) for name in names} == {"신간편뇌심건강보험"}


def test_samsung_new_simple_modifier_can_match_short_snippet_name():
    aliases = ["삼성생명", "삼성생명보험"]

    full_keys = set(product_core_key_candidates("삼성 인터넷 (신간편) 뇌심건강보험", aliases))
    short_keys = set(product_core_key_candidates("뇌심 건강보험", aliases))

    assert "신간편뇌심건강보험" in full_keys
    assert full_keys.intersection(short_keys) == {"뇌심건강보험"}
