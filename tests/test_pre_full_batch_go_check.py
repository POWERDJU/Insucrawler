from __future__ import annotations

from scripts.pre_full_batch_go_check import run_checks


def test_pre_full_batch_go_check_returns_go():
    checks = run_checks()
    failed = [item for item in checks if not item["passed"]]

    assert failed == []
    assert len(checks) >= 10


def test_pre_full_batch_go_check_covers_required_guardrails():
    names = {str(item["name"]) for item in run_checks()}

    assert "exclusive_keyword:배타적 사용권" in names
    assert "exclusive_keyword:독점 사용권" in names
    assert "local_context_uses_scored_window" in names
    assert "subject_reference_validation" in names
    assert "exclusive_type_master_removed" in names
    assert "exclusive_right_export_columns_simplified" in names
    assert "dashboard_product_table_columns_simplified" in names
    assert "product_detail_internal_fields_hidden" in names
    assert "major_coverage_columns_simplified" in names
    assert "recent_exclusive_rights_route_simplified" in names
