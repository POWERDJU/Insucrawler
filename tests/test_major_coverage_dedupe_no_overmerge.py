from __future__ import annotations

from app.services.coverage_dedupe_service import dedupe_major_coverages


def _coverage(name: str, **kwargs):
    return {
        "coverage_id": kwargs.pop("coverage_id", None),
        "coverage_name_raw": name,
        "coverage_name_normalized": name,
        "risk_area": kwargs.pop("risk_area", ""),
        "benefit_type": kwargs.pop("benefit_type", ""),
        "max_amount_krw": kwargs.pop("max_amount_krw", None),
        "condition_text": kwargs.pop("condition_text", ""),
        "coverage_summary": kwargs.pop("coverage_summary", f"{name} 보장"),
        **kwargs,
    }


def test_cancer_minor_high_value_and_general_are_not_overmerged():
    deduped, _ = dedupe_major_coverages(
        [
            _coverage("암진단비", coverage_id=1),
            _coverage("유사암진단비", coverage_id=2),
            _coverage("고액암진단비", coverage_id=3),
        ]
    )

    assert len(deduped) == 3


def test_surgery_classes_are_not_overmerged():
    deduped, _ = dedupe_major_coverages(
        [
            _coverage("수술비", coverage_id=1),
            _coverage("1종 수술비", coverage_id=2),
            _coverage("2종 수술비", coverage_id=3),
            _coverage("상해수술비", coverage_id=4),
        ]
    )

    assert len(deduped) == 4


def test_hospitalization_general_icu_and_care_hospital_are_not_overmerged():
    deduped, _ = dedupe_major_coverages(
        [
            _coverage("입원일당", coverage_id=1),
            _coverage("중환자실 입원일당", coverage_id=2),
            _coverage("요양병원 입원일당", coverage_id=3),
        ]
    )

    assert len(deduped) == 3


def test_driver_legal_cost_components_are_not_overmerged():
    deduped, _ = dedupe_major_coverages(
        [
            _coverage("벌금", coverage_id=1, risk_area="운전자"),
            _coverage("변호사선임비용", coverage_id=2, risk_area="운전자"),
            _coverage("교통사고처리지원금", coverage_id=3, risk_area="운전자"),
        ]
    )

    assert len(deduped) == 3


def test_premium_waiver_and_deferral_are_not_overmerged():
    deduped, _ = dedupe_major_coverages(
        [
            _coverage("보험료 납입면제", coverage_id=1),
            _coverage("보험료 납입유예", coverage_id=2),
        ]
    )

    assert len(deduped) == 2
