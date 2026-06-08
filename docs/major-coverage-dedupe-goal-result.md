# Major Coverage Dedupe Goal Result

- GOAL status: PASS
- pytest exit code: 0

## Counts
- pregnancy_support: raw 2 -> deduped 1
- birth_support: raw 2 -> deduped 1
- cancer_no_overmerge: raw 3 -> deduped 3
- surgery_no_overmerge: raw 3 -> deduped 3
- driver_no_overmerge: raw 3 -> deduped 3

## Assertions
- PASS: pregnancy_support displayed once
- PASS: birth_support displayed once
- PASS: cancer diagnosis does not merge minor/high/general
- PASS: surgery classes do not overmerge
- PASS: driver legal components do not overmerge

## Pytest Output
```
...............                                                          [100%]
============================== warnings summary ===============================
tests/test_product_detail_coverage_api_deduped.py::test_product_detail_returns_deduped_coverages_and_hides_raw_by_default
tests/test_product_detail_coverage_api_deduped.py::test_product_detail_debug_includes_raw_coverages
tests/test_dashboard_export_coverage_deduped.py::test_dashboard_export_uses_deduped_major_coverages
  C:\Users\User\OneDrive\바탕 화면\보험상품 업계조사 자동화\tests\conftest.py:21: SAWarning: Can't sort tables for DROP; an unresolvable foreign key dependency exists between tables: fact_crawl_job, fact_llm_batch_job; and backend does not support ALTER.  To restore at least a partial sort, apply use_alter=True to ForeignKey and ForeignKeyConstraint objects involved in the cycle to mark these as known cycles that will be ignored.
    Base.metadata.drop_all(engine)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
15 passed, 3 warnings in 4.13s
```
