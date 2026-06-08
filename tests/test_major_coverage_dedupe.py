from __future__ import annotations

from app.services.coverage_dedupe_service import build_coverage_identity_key, dedupe_major_coverages


def test_childbirth_support_coverages_share_component_family_key():
    first = {
        "coverage_name_normalized": "출산지원금",
        "risk_area": "출산",
        "benefit_type": "지원금",
        "max_amount_krw": 1000000,
        "coverage_summary": "출산 시 지원금을 지급한다.",
        "confidence": 0.7,
    }
    second = {
        "coverage_name_normalized": "출산하면 보험료 지원",
        "risk_area": "산모",
        "benefit_type": "보험금",
        "max_amount_krw": 1000000,
        "coverage_summary": "출산하면 보험료 지원금을 제공하는 담보다.",
        "confidence": 0.9,
    }

    assert build_coverage_identity_key(first) == build_coverage_identity_key(second)
    deduped, summary = dedupe_major_coverages([first, second])

    assert len(deduped) == 1
    assert summary["duplicate_count"] == 1
    assert deduped[0]["coverage_name_normalized"] == "출산하면 보험료 지원"


def test_legal_cost_coverages_share_component_family_key():
    deduped, summary = dedupe_major_coverages(
        [
            {"coverage_name_normalized": "법률비용", "benefit_type": "실손", "coverage_summary": "법률비용 보장"},
            {"coverage_name_normalized": "변호사 비용", "benefit_type": "실손", "coverage_summary": "변호사 비용을 보장한다."},
        ]
    )

    assert len(deduped) == 1
    assert summary["raw_count"] == 2
