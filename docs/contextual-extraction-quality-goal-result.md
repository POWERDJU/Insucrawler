# Contextual Extraction Quality Goal Result

PASS: `True`

## Success Conditions

- fixture regression tests: `PASS`
- product/exclusive final adjudication mock path: covered by tests
- article-level same-product LLM calls: `0` in goal runner
- export/render LLM calls: `0` in goal runner
- cleanup scripts: dry-run by default

## Command Results

### `C:\Users\User\AppData\Local\Programs\Python\Python313\python.exe -m pytest tests/test_product_name_discourse_prefix_cleaning_extended.py tests/test_article_eligibility_non_insurance_cases.py tests/test_extraction_quality_product_errors.py tests/test_extraction_quality_exclusive_errors.py tests/test_product_final_adjudication_service.py tests/test_exclusive_right_final_adjudication_service.py tests/test_reinsurer_company_exclusion.py tests/test_sales_metric_validation.py tests/test_batch_import_quality_guard.py`

returncode: `0`

```text
.................                                                        [100%]
============================== warnings summary ===============================
tests/test_article_eligibility_non_insurance_cases.py: 3 warnings
tests/test_extraction_quality_product_errors.py: 2 warnings
tests/test_extraction_quality_exclusive_errors.py: 2 warnings
tests/test_product_final_adjudication_service.py: 1 warning
tests/test_exclusive_right_final_adjudication_service.py: 2 warnings
tests/test_reinsurer_company_exclusion.py: 1 warning
tests/test_batch_import_quality_guard.py: 1 warning
  C:\Users\User\OneDrive\바탕 화면\보험상품 업계조사 자동화\tests\conftest.py:21: SAWarning: Can't sort tables for DROP; an unresolvable foreign key dependency exists between tables: fact_crawl_job, fact_llm_batch_job; and backend does not support ALTER.  To restore at least a partial sort, apply use_alter=True to ForeignKey and ForeignKeyConstraint objects involved in the cycle to mark these as known cycles that will be ignored.
    Base.metadata.drop_all(engine)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
17 passed, 12 warnings in 18.98s
```

### `C:\Users\User\AppData\Local\Programs\Python\Python313\python.exe scripts/diagnose_extraction_quality_errors.py --products C:\Users\User\Downloads\insurance_product_comparison (26).xlsx --exclusive-rights C:\Users\User\Downloads\exclusive_rights (5).xlsx --output docs/extraction-quality-error-diagnosis.md`

returncode: `0`

```text
{"output": "docs\\extraction-quality-error-diagnosis.md", "fixture": "data\\exports\\extraction_quality_error_fixtures.json"}
```

### `C:\Users\User\AppData\Local\Programs\Python\Python313\python.exe scripts/audit_extraction_quality_errors.py`

returncode: `0`

```text
{
  "crawl_job_id": null,
  "articles": {
    "total": 66492,
    "excluded_article_eligibility": 16574,
    "multi_company_flagged": 16574
  },
  "queues": {
    "pending": 1,
    "running": 0,
    "failed": 111,
    "completed": 12853
  },
  "products": {
    "active": 1054,
    "review": 22
  },
  "exclusive_rights": {
    "active": 517,
    "review": 406
  },
  "sales_metrics_needing_review": 1
}
```

### `C:\Users\User\AppData\Local\Programs\Python\Python313\python.exe scripts/cleanup_invalid_product_extractions.py`

returncode: `0`

```text
{'apply': False, 'count': 159, 'output': 'data\\exports\\invalid_product_extractions.csv'}
```

### `C:\Users\User\AppData\Local\Programs\Python\Python313\python.exe scripts/cleanup_invalid_exclusive_rights.py`

returncode: `0`

```text
{'apply': False, 'count': 94, 'output': 'data\\exports\\invalid_exclusive_rights.csv'}
```

### `C:\Users\User\AppData\Local\Programs\Python\Python313\python.exe scripts/rebuild_company_attribution_excluding_reinsurers.py`

returncode: `0`

```text
{'apply': False, 'count': 95, 'output': 'data\\exports\\reinsurer_attribution_audit.csv'}
```

### `C:\Users\User\AppData\Local\Programs\Python\Python313\python.exe scripts/rebuild_sales_metrics.py`

returncode: `0`

```text
{'apply': False, 'count': 310, 'output': 'data\\exports\\sales_metric_validation_audit.csv'}
```
