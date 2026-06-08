from __future__ import annotations

from app.services.coverage_dedupe_service import (
    build_coverage_identity_key,
    dedupe_major_coverages,
    group_duplicate_coverages,
)


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
        "confidence": kwargs.pop("confidence", 0.8),
        **kwargs,
    }


def test_pregnancy_support_variants_display_once():
    coverages = [
        _coverage("임신지원금", coverage_id=1, benefit_type="CASH_PAYMENT"),
        _coverage("임신 지원금", coverage_id=2, benefit_type="SUPPORT_PAYMENT"),
        _coverage("임신지원금 특약", coverage_id=3, risk_area="PREGNANCY_CHILDBIRTH"),
        _coverage("임신 관련 지원금", coverage_id=4, coverage_summary="임신 관련 지원금을 제공"),
    ]

    deduped, summary = dedupe_major_coverages(coverages)

    assert len(deduped) == 1
    assert summary["duplicate_count"] == 3
    assert summary["deduped_group_count"] == 1


def test_birth_support_variants_display_once():
    deduped, _ = dedupe_major_coverages(
        [
            _coverage("출산지원금", coverage_id=1),
            _coverage("출산 지원금", coverage_id=2),
            _coverage("출산 축하금", coverage_id=3),
            _coverage("출산하면 지급", coverage_id=4, coverage_summary="출산 시 지원금을 지급"),
        ]
    )

    assert len(deduped) == 1


def test_legal_expense_component_family_merges_variants():
    deduped, summary = dedupe_major_coverages(
        [
            _coverage("가정폭력 법률비용", coverage_id=1, benefit_type="LEGAL_EXPENSE"),
            _coverage("가정폭력으로 인한 법률비용", coverage_id=2, benefit_type="LEGAL_RISK"),
            _coverage("변호사 상담 서비스", coverage_id=3, coverage_summary="가정폭력 피해자의 법률 상담 비용 보장"),
        ]
    )

    assert len(deduped) == 1
    assert summary["raw_count"] == 3


def test_group_duplicate_coverages_reports_duplicate_ids():
    groups = group_duplicate_coverages(
        [
            _coverage("임신지원금", coverage_id=10),
            _coverage("임신지원금 담보", coverage_id=11, confidence=0.95),
        ]
    )

    assert len(groups) == 1
    assert groups[0].source_count == 2
    assert groups[0].duplicate_coverage_ids == [10]
    assert "family:pregnancy_support" in build_coverage_identity_key(groups[0].canonical_coverage)


def test_pregnancy_support_ignores_article_context_condition_noise_but_keeps_birth_separate():
    coverages = [
        _coverage("임신지원금", coverage_id=1, risk_area="PREGNANCY_CHILDBIRTH", benefit_type="CASH_PAYMENT"),
        _coverage(
            "임신지원금",
            coverage_id=2,
            risk_area="WOMEN_HEALTH",
            benefit_type="SUPPORT_PAYMENT",
            condition_text="배타적사용권",
        ),
        _coverage(
            "임신지원금 특약",
            coverage_id=3,
            risk_area="Maternity pregnancy",
            benefit_type="LUMP_SUM",
            condition_text="1년 배타적사용권 획득",
        ),
        _coverage("출산지원금", coverage_id=4, risk_area="Maternity childbirth", benefit_type="CASH_PAYMENT"),
    ]

    deduped, summary = dedupe_major_coverages(coverages)

    assert len(deduped) == 2
    assert summary["duplicate_count"] == 2
    names = {item["coverage_name_normalized"] for item in deduped}
    assert len([name for name in names if "임신지원금" in name]) == 1
    assert "출산지원금" in names
