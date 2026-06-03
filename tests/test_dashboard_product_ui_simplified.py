from pathlib import Path


def _function_body(script: str, name: str) -> str:
    start = script.index(f"function {name}")
    next_function = script.find("\nfunction ", start + 1)
    return script[start:] if next_function == -1 else script[start:next_function]


def test_dashboard_product_table_columns_are_simplified():
    script = Path("app/static/dashboard.js").read_text(encoding="utf-8")
    body = _function_body(script, "renderProducts")

    assert '"insurance_type"' not in body
    assert '"coverage_summary"' not in body
    assert '"major_coverage_count"' not in body
    assert '"article_count"' not in body
    assert '"needs_review"' not in body
    assert '"normalized_product_name"' in body
    assert '"company_name"' in body
    assert '"release_year_month"' in body
    assert '"primary_product_type"' in body


def test_product_detail_hides_correction_merge_and_review_debug_sections():
    script = Path("app/static/dashboard.js").read_text(encoding="utf-8")
    body = _function_body(script, "detailHtml")

    assert "상품명/분류 보정 이력" not in body
    assert "상품명 통합/원문 등장명" not in body
    assert "상품명 통합 이력" not in body
    assert "추출근거/검수" not in body
    assert "confidence_total" not in body
    assert "product_status" not in body
    assert "company_name_raw" not in body
    assert "needs_review" not in body


def test_major_coverage_table_hides_evidence_confidence_and_review_columns():
    script = Path("app/static/dashboard.js").read_text(encoding="utf-8")
    body = _function_body(script, "detailHtml")
    coverage_section = body[body.index("주요보장 리스트") : body.index("판매실적")]

    assert "detail_level" not in coverage_section
    assert "evidence_text" not in coverage_section
    assert "confidence" not in coverage_section
    assert "needs_human_review" not in coverage_section


def test_exclusive_right_list_hides_count_review_and_type_columns():
    script = Path("app/static/dashboard.js").read_text(encoding="utf-8")
    body = _function_body(script, "renderExclusiveRightList")

    assert '"article_count"' not in body
    assert '"needs_review"' not in body
    assert "exclusive_right_type" not in body
    assert "exclusive_right_type_code" not in body
    assert '"insurance_type"' in body
    assert '"company_name"' in body
    assert '"subject_name"' in body
    assert '"primary_article_title"' in body
