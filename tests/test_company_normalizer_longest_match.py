from __future__ import annotations

from app.normalizers.company_normalizer import CompanyNormalizer


def test_full_company_name_beats_short_or_shared_alias():
    normalizer = CompanyNormalizer()

    nonlife = normalizer.normalize("한화손해보험")
    life = normalizer.normalize("한화생명")

    assert nonlife is not None
    assert nonlife.company_name_normalized == "한화손해보험"
    assert nonlife.insurance_type == "손해보험"
    assert life is not None
    assert life.company_name_normalized == "한화생명"
    assert life.insurance_type == "생명보험"


def test_short_alias_alone_is_ambiguous_review():
    match = CompanyNormalizer().normalize("한화")

    assert match is not None
    assert match.company_name_normalized is None
    assert match.needs_review is True
    assert match.match_type == "short_alias"


def test_detect_all_with_positions_prefers_longest_match_per_company():
    matches = CompanyNormalizer().detect_all("한화손해보험과 한화생명이 각각 신상품을 선보였다")
    names = [item.company_name_normalized for item in matches]

    assert "한화손해보험" in names
    assert "한화생명" in names
    assert all(item.company_name_normalized != "한화" for item in matches)
