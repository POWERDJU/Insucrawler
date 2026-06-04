from pathlib import Path


JS = Path("app/static/dashboard.js").read_text(encoding="utf-8")


def test_selected_filter_values_empty_or_all_means_no_filter():
    assert "if (values.length === inputs.length) return [];" in JS
    assert "return values;" in JS
    assert "return values.length ? values : [NO_SELECTION];" not in JS


def test_dashboard_request_keeps_product_type_filter_independent():
    assert 'const productTypeCodes = selectedFilterValues("productTypeCodes");' in JS
    assert "product_type_codes: productTypeCodes" in JS
    assert 'company_names: selectedInsuranceType ? selectedFilterValues("companyNames") : []' in JS


def test_mobile_filter_summary_displays_product_type_names():
    assert "optionLabelsForValues(state.options?.product_types, productTypes, \"code\", \"name\")" in JS
    assert 'compactFilterLabel(productTypeLabels, "상품군 전체")' in JS
