from __future__ import annotations

from app.normalizers.exclusive_right_subject_normalizer import (
    component_set_overlap,
    exclusive_subject_component_set,
    split_exclusive_subject_components,
)


def test_component_set_parser_splits_legal_cost_subjects():
    components = split_exclusive_subject_components("가정폭력 법률비용 담보 및 Lady 변호사 상담 서비스")

    assert components == ["가정폭력 법률비용 담보", "Lady 변호사 상담 서비스"]


def test_component_set_overlap_treats_legal_cost_coverages_as_same_event_components():
    left = exclusive_subject_component_set("가정폭력 법률비용 담보 및 Lady 변호사 상담 서비스")
    right = exclusive_subject_component_set("가정폭력 법률비용 담보 및 변호사 상담 서비스, 가사소송 법률비용 보장")

    assert component_set_overlap(left, right) >= 0.5
