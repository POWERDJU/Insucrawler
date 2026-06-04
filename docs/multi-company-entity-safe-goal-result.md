# Multi-Company Entity-Safe Goal Result

GOAL status: PASS

Validated policy:
- Multi-company articles are excluded at article/source level.
- Mixed-source products remain visible when non-multi evidence exists.
- Only-multi-source products are marked but not physically deleted.
- Mixed-source exclusive-right events remain visible when non-multi evidence exists.
- Only-multi-source exclusive-right events are marked but not physically deleted.
- Raw articles are preserved.
- Batch import guard skips multi-company article output.

pytest output:
```
....                                                                     [100%]
============================== warnings summary ===============================
tests/test_multi_company_cleanup_entity_safe.py::test_multi_company_article_filter_counts_only_known_insurers
tests/test_multi_company_cleanup_entity_safe.py::test_product_mixed_source_is_kept_and_only_multi_is_marked
tests/test_multi_company_cleanup_entity_safe.py::test_exclusive_mixed_source_is_kept_and_only_multi_is_marked
tests/test_multi_company_cleanup_entity_safe.py::test_batch_import_guard_skips_multi_company_article
  C:\Users\User\OneDrive\바탕 화면\보험상품 업계조사 자동화\tests\conftest.py:21: SAWarning: Can't sort tables for DROP; an unresolvable foreign key dependency exists between tables: fact_crawl_job, fact_llm_batch_job; and backend does not support ALTER.  To restore at least a partial sort, apply use_alter=True to ForeignKey and ForeignKeyConstraint objects involved in the cycle to mark these as known cycles that will be ignored.
    Base.metadata.drop_all(engine)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html

```
