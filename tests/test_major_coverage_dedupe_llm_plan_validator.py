from __future__ import annotations

from app.services.major_coverage_llm_dedupe_service import MajorCoverageLLMDedupeService


def test_llm_plan_validator_accepts_only_rule_compatible_high_confidence_merges(monkeypatch):
    monkeypatch.delenv("MAJOR_COVERAGE_LLM_DEDUPE_ENABLED", raising=False)
    service = MajorCoverageLLMDedupeService()
    coverages = [
        {"coverage_id": 1, "coverage_name_normalized": "임신지원금", "benefit_type": "CASH_PAYMENT"},
        {"coverage_id": 2, "coverage_name_normalized": "임신지원금 특약", "benefit_type": "SUPPORT_PAYMENT"},
        {"coverage_id": 3, "coverage_name_normalized": "출산지원금", "benefit_type": "SUPPORT_PAYMENT"},
    ]

    result = service.validate_merge_plan(
        coverages,
        {
            "merge_groups": [
                {"canonical_coverage_id": 2, "merge_ids": [1], "confidence": 0.91},
                {"canonical_coverage_id": 2, "merge_ids": [3], "confidence": 0.95},
                {"canonical_coverage_id": 2, "merge_ids": [999], "confidence": 0.99},
            ]
        },
    )

    assert service.enabled() is False
    assert len(result["accepted_merge_groups"]) == 1
    assert result["accepted_merge_groups"][0]["merge_ids"] == [1]
    assert len(result["review_items"]) == 1
    assert len(result["rejected_merge_groups"]) == 1
