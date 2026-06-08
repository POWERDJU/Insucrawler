from __future__ import annotations

from pathlib import Path

from scripts.audit_major_coverage_duplicates import write_csv


def test_major_coverage_duplicate_audit_writes_expected_columns(tmp_path):
    output = write_csv(
        [
            {
                "product_id": "1",
                "product_name": "테스트",
                "coverage_group_key": "family:pregnancy_support",
                "canonical_coverage_name": "임신지원금",
                "duplicate_coverage_ids": "2",
                "duplicate_coverage_names": "임신지원금 | 임신 지원금",
                "family": "pregnancy_support",
                "merge_reason": "same normalized coverage identity",
                "action": "display_dedupe_only",
                "review_reason": "",
            }
        ],
        tmp_path / "audit.csv",
    )

    text = Path(output).read_text(encoding="utf-8-sig")
    assert "coverage_group_key" in text
    assert "display_dedupe_only" in text
