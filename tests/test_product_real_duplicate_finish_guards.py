from __future__ import annotations

from app.normalizers.product_name_normalizer import (
    build_product_family_tokens,
    validate_product_name_before_save,
)
from app.services.product_blocking_service import ProductBlockCandidate
from app.services.product_consolidation_service import ProductConsolidationService
from app.services.product_duplicate_guard_service import ProductDuplicateGuardService


def _candidate(
    product_id: int,
    name: str,
    *,
    candidate_types: set[str] | None = None,
    product_type_code: str = "HEALTH_COMPREHENSIVE",
    release_year_month: str = "2026-01",
) -> ProductBlockCandidate:
    return ProductBlockCandidate(
        product_id=product_id,
        name=name,
        core_key="".join(ch for ch in name.casefold() if ch.isalnum()),
        company_id=1,
        partner_company_name=None,
        product_type_code=product_type_code,
        release_year_month=release_year_month,
        candidate_types=candidate_types or set(),
        family_tokens=build_product_family_tokens(name),
        high_info_tokens=build_product_family_tokens(name),
    )


def test_bad_sentence_fragments_are_rejected_before_product_save():
    for name in ["지키면보험", "다만 건강보험", "이번 보험", "해당 상품", "신상품", "종합보험"]:
        result = validate_product_name_before_save(name)
        assert result.accepted is False


def test_clean_identity_matches_legal_prefix_suffix_and_small_latin_prefixes():
    service = ProductConsolidationService()
    pairs = [
        ("사망보험 금 유동화 상품", "사망보험 금 유동화"),
        ("H통합건강보험", "통합 건강보험"),
        ("e독서안심보험", "독서안심보험"),
        ("무배당 다이렉트 토스 건상생활 치아보험 갱신형", "무 다이렉트토스건강생활치아보험 갱신형"),
    ]
    for left, right in pairs:
        assert service._clean_identity_match(_candidate(1, left), _candidate(2, right))


def test_official_product_absorbs_safe_descriptive_aliases_only():
    service = ProductConsolidationService()
    canonical = _candidate(1, "골든라이프 딱좋은 간병보험", candidate_types={"official_name", "launch_name"})
    generic = _candidate(2, "간병보험", candidate_types={"launch_name"})
    descriptive = _candidate(3, "치매 치료와 장기 요양을 동시에 보장하는 간병보험", candidate_types={"launch_name"})
    distinct = _candidate(4, "원팀 골프보험", candidate_types={"official_name"}, product_type_code="TRAVEL_LEISURE")

    assert service._official_absorbs_generic_description(canonical, generic, {"간병"})
    assert service._official_absorbs_generic_description(canonical, descriptive, {"간병"})
    assert not service._official_absorbs_generic_description(
        _candidate(5, "골프보험", candidate_types={"official_name"}, product_type_code="TRAVEL_LEISURE"),
        distinct,
        {"골프"},
    )


def test_duplicate_guard_does_not_warn_for_distinct_variant_modifiers():
    guard = ProductDuplicateGuardService()
    assert guard._distinct_variant_modifier("해외여행보험", "365연간해외여행보험")
    assert guard._distinct_variant_modifier("골프보험", "원팀 골프보험")
    assert guard._distinct_variant_modifier("전월세보험", "직거래전월세보험")
    assert not guard._distinct_variant_modifier("사망보험 금 유동화 상품", "사망보험 금 유동화")
