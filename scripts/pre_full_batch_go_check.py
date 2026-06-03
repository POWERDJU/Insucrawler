from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (ROOT_DIR / relative_path).read_text(encoding="utf-8")


def exists(relative_path: str) -> bool:
    return (ROOT_DIR / relative_path).exists()


def function_body(source: str, function_name: str) -> str:
    marker = f"function {function_name}"
    start = source.find(marker)
    if start < 0:
        return ""
    next_function = source.find("\nfunction ", start + len(marker))
    if next_function < 0:
        return source[start:]
    return source[start:next_function]


def python_function_body(source: str, function_name: str) -> str:
    pattern = re.compile(rf"^(    )?def {re.escape(function_name)}\(", re.MULTILINE)
    match = pattern.search(source)
    if not match:
        return ""
    indent = match.group(1) or ""
    next_pattern = re.compile(rf"^{indent}def |^{indent}@|^class ", re.MULTILINE)
    next_match = next_pattern.search(source, match.end())
    return source[match.start() : next_match.start() if next_match else len(source)]


def check(condition: bool, name: str, detail: str = "") -> dict[str, str | bool]:
    return {"name": name, "passed": bool(condition), "detail": detail}


def run_checks() -> list[dict[str, str | bool]]:
    checks: list[dict[str, str | bool]] = []

    exclusive_service = read_text("app/services/exclusive_right_service.py")
    exclusive_context = read_text("app/services/exclusive_right_local_context.py")
    screening_service = read_text("app/services/screening_service.py")
    snippet_service = read_text("app/services/snippet_service.py")
    dashboard_js = read_text("app/static/dashboard.js")
    dashboard_routes = read_text("app/api/routes_dashboard.py")
    dashboard_service = read_text("app/services/dashboard_service.py")
    exclusive_right_service = read_text("app/services/exclusive_right_service.py")
    env_example = read_text(".env.example")

    keyword_sources = "\n".join([exclusive_service, exclusive_context, screening_service, snippet_service])
    for keyword in ["배타적 사용권", "독점 사용권", "신상품 심의위원회"]:
        checks.append(check(keyword in keyword_sources, f"exclusive_keyword:{keyword}"))

    local_context_body = python_function_body(exclusive_service, "_local_context_text")
    checks.append(
        check(
            "select_best_exclusive_context_window" in local_context_body
            and "windows[0]" not in local_context_body
            and ".append(" not in local_context_body,
            "local_context_uses_scored_window",
            "_local_context_text must select a scored context window, not the first window.",
        )
    )

    checks.append(
        check(
            "validate_exclusive_subject_before_save" in exclusive_service
            and "resolve_subject_reference" in exclusive_context
            and "WEAK_SUBJECT_KEYS" in exclusive_context
            and "해당 상품" in exclusive_context
            and "이번 특약" in exclusive_context,
            "subject_reference_validation",
        )
    )

    removed_master_terms = [
        "DimExclusiveRightType",
        "seed_exclusive_right_types",
        "exclusive_right_type_master.csv",
    ]
    active_sources = "\n".join(
        [
            read_text("app/db/models.py"),
            read_text("app/db/seed_master_data.py"),
            "\n".join(path.name for path in (ROOT_DIR / "config").glob("*")),
            read_text("docs/DATA_SCHEMA.md"),
        ]
    )
    checks.append(
        check(
            not any(term in active_sources for term in removed_master_terms),
            "exclusive_type_master_removed",
            "The migration may still drop old dim_exclusive_right_type, but active model/seed/config/docs must not use it.",
        )
    )

    export_body = python_function_body(exclusive_right_service, "export_workbook")
    removed_export_columns = [
        "원문 회사명",
        "구분",
        "subject_type",
        "기간 원문",
        "획득년월 basis",
        "관련기사 수",
        "confidence",
        "검수필요",
    ]
    checks.append(
        check(
            not any(column in export_body for column in removed_export_columns)
            and all(
                column in export_body
                for column in [
                    "배타적사용권 ID",
                    "업종",
                    "보험회사",
                    "상품/특약/제도명",
                    "배타적사용권 기간 개월 수",
                    "획득년월",
                    "주요 특징",
                    "대표 기사 제목",
                    "대표 기사 URL",
                    "alias 목록",
                    "근거문장",
                ]
            ),
            "exclusive_right_export_columns_simplified",
        )
    )

    render_products = function_body(dashboard_js, "renderProducts")
    checks.append(
        check(
            all(key not in render_products for key in ["insurance_type", "major_coverage_count", "article_count", "needs_review"])
            and all(key in render_products for key in ["normalized_product_name", "company_name", "release_year_month", "primary_product_type"]),
            "dashboard_product_table_columns_simplified",
        )
    )

    detail_html = function_body(dashboard_js, "detailHtml")
    removed_detail_terms = [
        "confidence_total",
        "product_status",
        "상품명/분류 보정이력",
        "상품명 통합/원문 등장명",
        "상품명 통합 이력",
        "추출근거/검수",
        "missing_fields",
        "needs_human_review",
    ]
    checks.append(check(not any(term in detail_html for term in removed_detail_terms), "product_detail_internal_fields_hidden"))

    coverage_section_match = re.search(r"주요보장 리스트.*?\]\), \"coverage-full-section\"", detail_html, re.DOTALL)
    coverage_section = coverage_section_match.group(0) if coverage_section_match else ""
    checks.append(
        check(
            bool(coverage_section)
            and not any(term in coverage_section for term in ["evidence_text", "detail_level", "confidence", "needs_human_review", "검수필요"])
            and all(term in coverage_section for term in ["coverage_name_normalized", "risk_area", "benefit_type", "max_amount_krw"]),
            "major_coverage_columns_simplified",
        )
    )

    render_exclusive_list = function_body(dashboard_js, "renderExclusiveRightList")
    checks.append(
        check(
            not any(
                term in render_exclusive_list
                for term in [
                    "article_count",
                    "needs_review",
                    "exclusive_right_type",
                    "exclusive_right_type_code",
                    "company_name_raw",
                    "subject_type",
                    "acquired_year_month_basis",
                ]
            ),
            "exclusive_right_list_simplified",
        )
    )

    recent_dashboard_body = python_function_body(exclusive_right_service, "recent_dashboard")
    checks.append(
        check(
            "/api/dashboard/recent-exclusive-rights" in dashboard_routes
            and not any(term in recent_dashboard_body for term in ["exclusive_right_type", "article_count", "needs_review", "confidence_total"]),
            "recent_exclusive_rights_route_simplified",
        )
    )

    checks.append(check(exists("tests/test_exclusive_right_actual_error_cases.py"), "actual_error_case_tests_exist"))

    env_required = {
        "ENABLE_ARTICLE_BODY_FETCH": "false",
        "LLM_VERIFY_ONLY_RISKY": "true",
        "LLM_SKIP_LOW_RELEVANCE": "true",
        "LLM_USE_SNIPPETS_ONLY": "true",
        "ENABLE_PRODUCT_CLUSTER_EXTRACTION": "true",
        "ENABLE_GEMINI_GROUNDING": "false",
        "PRODUCT_CONSOLIDATION_LLM_ENABLED": "false",
        "EXCLUSIVE_RIGHT_EXTRACTION_DEFAULT_MODE": "enqueue_only",
        "EXCLUSIVE_RIGHT_USE_SNIPPETS_ONLY": "true",
    }
    env_pairs = dict(
        line.split("=", 1)
        for line in env_example.splitlines()
        if line and not line.strip().startswith("#") and "=" in line
    )
    checks.append(
        check(
            all(env_pairs.get(key) == value for key, value in env_required.items()),
            "cost_saving_env_defaults",
            ", ".join(f"{key}={value}" for key, value in env_required.items()),
        )
    )

    dashboard_export_body = python_function_body(dashboard_service, "_comparison_columns")
    checks.append(
        check(
            "업종" not in dashboard_export_body
            and "검수필요" not in dashboard_export_body
            and "confidence" not in dashboard_export_body,
            "dashboard_export_internal_columns_removed",
        )
    )

    return checks


def main() -> int:
    checks = run_checks()
    failed = [item for item in checks if not item["passed"]]
    result = {
        "status": "NO_GO" if failed else "GO",
        "failed_checks": failed,
        "passed_count": len(checks) - len(failed),
        "total_count": len(checks),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
