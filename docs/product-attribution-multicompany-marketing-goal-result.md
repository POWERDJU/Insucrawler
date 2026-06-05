# Product Attribution Multi-Company Marketing Guard Goal Result

- status: PASS
- realtime_llm_calls: 0
- article_level_same_product_llm_calls: 0
- diagnosis_report: docs\product-150-company-attribution-diagnosis.md
- rebuild_plan: data\exports\product_company_attribution_rebuild_plan_product_150.csv

## Checks

### Regression tests
- exit_code: 0

```text
........                                                                 [100%]
============================== warnings summary ===============================
tests/test_product_attribution_marketing_guard.py::test_marketing_only_generic_product_is_observation_only
tests/test_product_attribution_marketing_guard.py::test_multi_company_filter_uses_saved_snippets
tests/test_product_attribution_marketing_guard.py::test_cluster_company_candidates_are_not_final_company_when_no_local_evidence
tests/test_product_attribution_marketing_guard.py::test_ineligible_foreign_branch_is_not_product_company
tests/test_multi_company_cleanup_entity_safe.py::test_multi_company_article_filter_counts_only_known_insurers
tests/test_multi_company_cleanup_entity_safe.py::test_product_mixed_source_is_kept_and_only_multi_is_marked
tests/test_multi_company_cleanup_entity_safe.py::test_exclusive_mixed_source_is_kept_and_only_multi_is_marked
tests/test_multi_company_cleanup_entity_safe.py::test_batch_import_guard_skips_multi_company_article
  C:\Users\User\OneDrive\���� ȭ��\�����ǰ �������� �ڵ�ȭ\tests\conftest.py:21: SAWarning: Can't sort tables for DROP; an unresolvable foreign key dependency exists between tables: fact_crawl_job, fact_llm_batch_job; and backend does not support ALTER.  To restore at least a partial sort, apply use_alter=True to ForeignKey and ForeignKeyConstraint objects involved in the cycle to mark these as known cycles that will be ignored.
    Base.metadata.drop_all(engine)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html

```

### Product 150 diagnosis
- exit_code: 0

```text
C:\Users\User\OneDrive\���� ȭ��\�����ǰ �������� �ڵ�ȭ\docs\product-150-company-attribution-diagnosis.md

```

### Product 150 rebuild dry-run
- exit_code: 0

```text
DB ��� �� ������ �����մϴ�. �⺻�� dry-run�̸� LLM/API ȣ���� ���� �ʽ��ϴ�.
plan_rows=1 changed=0 csv=C:\Users\User\OneDrive\���� ȭ��\�����ǰ �������� �ڵ�ȭ\data\exports\product_company_attribution_rebuild_plan_product_150.csv

```
