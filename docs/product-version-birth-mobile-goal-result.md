# Product Version/Birth/Mobile Goal Check

- status: PASS
- checked_at: 2026-06-04T00:08:52
- command: `C:\Users\User\AppData\Local\Programs\Python\Python313\python.exe -m pytest -q tests/test_product_signature_series_version_policy.py tests/test_product_birth_benefit_consolidation.py tests/test_product_release_month_resolver_version_aware.py tests/test_product_detail_coverage_dedupe_shared.py`

## Scope

- Signature Women 3.0/4.0 remain separate.
- Same-version Signature Women variants merge without LLM.
- Birth/pregnancy benefit component variants merge together.
- Birth benefit components do not merge into the body product.
- Release month prefers version-compatible direct launch articles.
- Product detail coverage rows are deduplicated for PC and mobile views.

## Pytest Output

```text
........                                                                 [100%]
============================== warnings summary ===============================
tests/test_product_signature_series_version_policy.py::test_signature_women_same_version_variants_merge_without_llm
tests/test_product_signature_series_version_policy.py::test_signature_women_versionless_name_does_not_bridge_3_and_4
tests/test_product_birth_benefit_consolidation.py::test_birth_benefit_variants_merge_as_same_component_family
tests/test_product_birth_benefit_consolidation.py::test_birth_benefit_component_does_not_merge_into_signature_body_product
tests/test_product_release_month_resolver_version_aware.py::test_release_month_ignores_other_version_and_followup_articles
tests/test_product_release_month_resolver_version_aware.py::test_release_month_uses_earliest_direct_launch_article_for_same_product
tests/test_product_detail_coverage_dedupe_shared.py::test_product_detail_dedupes_major_coverages_before_response
  C:\Users\User\OneDrive\바탕 화면\보험상품 업계조사 자동화\tests\conftest.py:21: SAWarning: Can't sort tables for DROP; an unresolvable foreign key dependency exists between tables: fact_crawl_job, fact_llm_batch_job; and backend does not support ALTER.  To restore at least a partial sort, apply use_alter=True to ForeignKey and ForeignKeyConstraint objects involved in the cycle to mark these as known cycles that will be ignored.
    Base.metadata.drop_all(engine)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html

```
