from __future__ import annotations

from scripts.run_exclusive_right_consolidation_goal_check import run_goal_check


def test_exclusive_right_consolidation_goal_runner_passes(tmp_path):
    report_path = tmp_path / "exclusive-right-consolidation-goal-result.md"

    result = run_goal_check(report_path)

    assert result["status"] == "PASS"
    assert result["kyobo_export_row_count"] == 1
    assert result["hanwha_export_row_count"] == 1
    assert result["duplicate_groups_after"] == 0
    assert result["article_level_llm_calls"] == 0
    assert result["export_render_llm_calls"] == 0
    assert "GOAL status = PASS" in report_path.read_text(encoding="utf-8")
