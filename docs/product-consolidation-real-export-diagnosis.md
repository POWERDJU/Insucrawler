# Product Consolidation Real Export Diagnosis

## Scope

This diagnosis covers the real Excel duplicate groups that remained after the
product consolidation work. It does not require news crawling, Naver API calls,
article LLM re-extraction, or full article reparsing. The fixes are applied at
the product catalog consolidation layer.

The rule-only path is the default. Optional LLM consolidation remains limited to
compact same-company product-list merge plans and must pass deterministic
validation before any DB mutation.

## Root Causes

### StepUp 700 rows

The real export row 46/138-style case split one NH Life product into variants
such as `스텝업700 종신보험` and `스텝업 700 NH 종신보험`.

The likely failure mode was not article parsing. The product-name identity layer
treated spacing, the embedded company token `NH`, and the separated number `700`
as different enough that the family signature and token overlap were weaker
than the merge threshold.

Fixes:

- product-name-only family tokens now normalize `스텝업 700` and `스텝업700` to
  the same high-information token,
- company/noise tokens such as `NH`, `보험`, and generic product words do not
  dominate the family signature,
- specific-family conflict checks allow containment between tokens such as
  `스텝업` and `스텝업700`,
- the merge rule still requires same company, compatible type, close release
  month, and no version conflict before it can auto-merge.

### Pet product rows

The real export row 115/116/117/120-style case split KB pet product variants
such as `KB 금쪽같은 펫보험`, `금쪽같은 펫보험`, `KB 금쪽같은 펫 보험 개정`, and
`펫보험`.

The likely failure mode was that `펫보험` is too short and generic to be a safe
standalone family signature, while the branded variants had stronger identity
tokens. Exact core-key and high similarity alone did not reliably attach the
short alias to the stronger canonical row.

Fixes:

- `금쪽같은` and `펫` are retained as product-name high-information tokens,
- `펫보험` alone remains generic and is not allowed to merge across companies,
- a same-company short-generic-alias containment rule can attach the short name
  to a stronger specific product only when company, product type, release month,
  and version checks pass,
- dashboard and Excel export continue to hide merged products and display their
  raw names as canonical aliases.

### Existing goal families

The same rule-only gate still protects the earlier duplicate families:

- Shinhan Life tontine annuity variants collapse to one canonical product.
- Hanwha General Insurance Signature Women 4.0 variants collapse to one
  canonical product.
- Signature Women 3.0 remains separate from 4.0.
- Another insurer's Signature Women 4.0 remains separate from Hanwha's product.
- ABL health-refund variants collapse to one canonical product.
- ABL whole-body anesthesia surgery insurance remains separate and is not shown
  as a health-refund alias.

## Guardrails

The family and version signatures are computed only from product-name sources:

- `dim_product.raw_product_name`
- `dim_product.normalized_product_name`
- `dim_product.product_core_key`
- `dim_product_alias.raw_product_name`
- `dim_product_alias.normalized_product_name_candidate`
- `fact_product_observation.raw_product_name`
- `fact_product_observation.normalized_product_name_candidate`

Article title, article description, article body, snippets, narrative summaries,
coverage summaries, and sales metrics are not used to calculate product identity
signatures. They can still be used for context diagnostics and blocking
explanations.

The following are still blocked from deterministic auto-merge:

- different known insurers,
- clear product type conflicts,
- conflicting explicit product versions such as `3.0` versus `4.0`,
- weak generic names with no stronger same-company product context.

## Verification

Run the consolidation-only quality gate:

```powershell
python scripts/run_product_consolidation_goal_check.py
```

The script writes `docs/product-consolidation-goal-result.md`. The current
passing result confirms:

- `stepup_700: 1`
- `pet_brand: 1`
- all prior target families collapse correctly,
- rule-only consolidation made zero LLM calls.

Focused regression tests:

```powershell
py -3 -m pytest tests/test_product_consolidation_real_export_rows.py tests/test_dashboard_export_after_consolidation_real_export_rows.py -q
```

Broader consolidation/export regression tests:

```powershell
py -3 -m pytest tests/test_product_consolidation_goal_cases.py tests/test_product_duplicate_guard_goal_cases.py tests/test_dashboard_export_after_consolidation_goal_cases.py tests/test_product_consolidation_real_export_rows.py tests/test_dashboard_export_after_consolidation_real_export_rows.py -q
```
