# Product Consolidation

## Problem

Product extraction is article-grained. The extractor sees one article or one snippet bundle at a time, so it does not know the full product catalog already stored in the database. When the same product appears as `Mini Care Insurance`, `Alpha Mini Care Insurance`, or a descriptive phrase in different articles, article-level extraction can create multiple `dim_product` rows.

This cannot be fixed reliably by prompt wording alone:

1. The article extractor only receives the current article context.
2. It does not receive all existing DB products or all near-duplicate candidates.
3. The save path has historically relied on exact `company_id + product_core_key` matches.
4. Small differences in product names, partner phrases, version text, or weak mentions can produce different core keys.
5. Same-article weak mentions can be handled deterministically, but cross-article entity resolution needs a global job.
6. Unknown insurer or partner-only contexts weaken exact matching.

Therefore product entity resolution is handled by `ProductConsolidationJob`, not by per-article LLM calls.

## Concepts

- `fact_product_observation`: every extracted product-name candidate or alias occurrence, with article, partner, product type, release month, candidate type, and context.
- `provisional product`: a product row that is useful for review/search but still needs global consolidation.
- `canonical product`: the product row shown in the dashboard and Excel export.
- `merged product`: an audit row linked to a canonical product through `merged_into_product_id`.
- `fact_product_consolidation_job`: one global consolidation run.
- `fact_product_consolidation_block`: a reduced candidate set produced by deterministic blocking.

## Pipeline

1. Article extraction stores product observations and creates or links products.
2. Weak mentions and pronoun-like names are not allowed to become independent active products.
3. A consolidation job runs after a crawl, when enough observations have accumulated, or when an admin runs it manually.
4. Blocking groups only plausible candidates using company, partner, product type, release month, core key, and local similarity.
5. Rule merge applies deterministic cases first.
6. LLM block judge is optional and budget-gated. It is off by default.

## Blocking Rules

Candidates can be in the same block when:

- known company is the same,
- product type is same or one side is unknown,
- release month is close enough,
- product core key matches or local name similarity is high,
- or partner/context is shared when company is unknown.

The blocking step is intentionally broader than the merge step. It now uses
product names, product aliases, observations, article titles, article
descriptions, source URLs, release month, product type, and inferred partner
phrases to create a context signature. This lets candidates with missing
`company_id` or missing `partner_company_name` still land in the same review
block when their release month, product type, name tokens, and article context
are close.

Soft type compatibility is used only for blocking. `UNKNOWN` and `OTHER` are
compatible with known product types, and modifier-like groups such as
`SIMPLIFIED_IMPAIRED` or `VARIABLE_UL` can block with their natural primary
types. Clear conflicts such as `AUTO` versus `DENTAL` are still blocked from
merging.

Context tokens deliberately remove generic words such as "보험", "상품", "고객",
"대상", "전용", "특화", "출시", and "보장" while preserving more informative
tokens from the product name and article context. Partner names may be inferred
from article context, but they are not inserted into `dim_company`.

Candidates are not blocked when:

- known companies differ,
- product types clearly conflict,
- release months are too far apart,
- version signatures differ,
- or either side is a rejected service/app/discount phrase.

## Same-Company Product Family Signature

Some insurers publish the same product under several short and descriptive
names across articles. The consolidation job now computes a deterministic
`product_family_signature` and `family_tokens` from product-name sources only:

- `dim_product.raw_product_name`
- `dim_product.normalized_product_name`
- `dim_product.product_core_key`
- `dim_product_alias.raw_product_name`
- `dim_product_alias.normalized_product_name_candidate`
- `fact_product_observation.raw_product_name`
- `fact_product_observation.normalized_product_name_candidate`

Article titles, article descriptions, article bodies, snippets, narrative
summaries, and coverage summaries are not used to calculate
`product_family_signature` or `version_signature`. They remain available for
context similarity and block explanations only. This prevents article phrases
such as dates, amounts, disease names, and general coverage words from
polluting the product identity signature.

When a product row already has a clean product-name signature, incompatible
alias/observation signatures are not allowed to override it. For example,
`우리WON전신마취수술보험` is not shown as a user-facing alias of
`우리WON건강환급보험`; the source observation is preserved for audit, but the
Excel/dashboard alias list filters it out.

The family signature is intentionally broader than `product_core_key` and is
used only for blocking and deterministic consolidation.

Examples that should block and merge without LLM when company, product type,
release month, and version checks pass:

- `신한톤틴 연금보험`, `신한톤틴연금보험`, `톤틴(Tontine) 연금`, `톤틴연금보험`, `한국형 톤틴연금보험`
- `(무)우리WON건강환급보험`, `우리WON건강환급보험`, `건강환급보험`, `보험료 환급해주는 건강환급보험`, `납입 특약보험료 건강환급`

Generic signatures such as `연금`, `건강보험`, or `암보험` are not enough for
automatic merge. They may participate in a wider block only when stronger
tokens, aliases, or article context make the candidate meaningful. Different
known companies are never auto-merged, and conflicting version signatures such
as `3.0` versus `4.0` are blocked from deterministic merge.

Versionless names are guarded too. When one same-company product family contains
multiple explicit versions, a versionless alias such as `시그니처 여성건강보험`
must not bridge `3.0` and `4.0`; it remains a separate review/alias candidate
unless deterministic evidence can attach it to exactly one version.

`version_signature` is also calculated only from product-name fields. It accepts
explicit product-version markers such as `4.0`, `3.0`, `V2`, and `2세대`. It
does not treat article dates, ranking numbers, periods, or money amounts such as
`12일`, `1월`, `130만원`, or `6개월` as versions.

Same-company optional modifier identity is handled deterministically. If the
company, explicit version, product type compatibility, and at least two
high-information family tokens match, middle modifiers such as `건강`, `종합`,
and `보험` may be ignored for identity comparison. This lets
`시그니처 여성 건강보험 4.0` and `시그니처 여성보험 4.0` merge into one canonical
product, while `3.0` and `4.0` remain separate.

Birth/pregnancy benefit components use their own family token. Variants such as
`출산하면 보험료 지원 특약`, `출산지원금 보장 특약`, and `출산 혜택 보험료 유예
특약` can merge together when company and release window are compatible. The
same token is also a conflict guard, so those component rows do not merge into a
body product such as `시그니처 여성건강보험 4.0`.

Canonical selection prefers official or launch-like product names with more
specific family tokens and brand tokens. Descriptive fragments such as
`보험료 환급해주는 ...`, `납입 ... 지급 상품`, and weak mentions remain aliases or
merged duplicates instead of becoming the canonical display row.

## Rule Merge

Automatic merge does not call LLM. It applies when:

- same company and same `product_core_key`,
- same company and same non-generic `product_family_signature`,
- same company and strong family-token overlap with compatible product type and
  close release month,
- same company and alias/observation family overlap,
- same company, same/compatible type, close release month, and high name similarity,
- one name is a weak mention attached to a stronger canonical candidate in the same block,
- or same partner context plus strong local similarity.
- context similarity is high enough and version/product-type/company conflict
  checks pass.
- one candidate is a descriptive expansion or containment of another with
  shared high-information tokens.

All applied merges are recorded in `fact_product_merge_decision`. Duplicate products remain in `dim_product` with `product_status='merged'`.

## LLM Policy

LLM is not used for pairwise comparison. If enabled, it only judges a gray block once using minimal JSON: candidate ids, names, candidate types, company/partner, release window, product type, and short context. Default environment:

- `PRODUCT_CONSOLIDATION_LLM_ENABLED=false`
- `PRODUCT_CONSOLIDATION_LLM_MAX_CALLS_PER_JOB=10`
- `PRODUCT_CONSOLIDATION_LLM_MAX_COST_USD_PER_JOB=1.0`

List-level LLM consolidation is a separate administrator-only path for cases
where deterministic family/context rules still leave duplicate rows. It sends a
compact block payload, not full article bodies or raw DB dumps, and the LLM only
returns a merge plan. The plan is applied only after deterministic validation:

- every product in an auto-merge group must belong to the same known insurer,
- product type must be compatible,
- version signatures must not conflict,
- release month distance must be within the accepted range,
- canonical names must not be generic weak names,
- returned product ids must be inside the original block,
- confidence must be at least `0.85`.

Rejected validation items are written to the plan CSV as review rows. The LLM is
off by default:

- `PRODUCT_LLM_CONSOLIDATION_ENABLED=false`
- `PRODUCT_LLM_CONSOLIDATION_MAX_COMPANIES_PER_JOB=50`
- `PRODUCT_LLM_CONSOLIDATION_MAX_PRODUCTS_PER_PROMPT=60`
- `PRODUCT_LLM_CONSOLIDATION_MAX_CALLS_PER_JOB=30`
- `PRODUCT_LLM_CONSOLIDATION_MAX_COST_USD_PER_JOB=3.0`
- `PRODUCT_LLM_CONSOLIDATION_MODEL=gemini-2.5-flash`

The newer full-list path groups active/provisional/review products by insurer
and sends only compact catalog rows for that insurer. It is designed for cases
where same-company product variants remain split even after block-level
consolidation, such as tontine annuity variants or health-refund product
variants. It still does not send full article bodies and it does not run during
article extraction or Excel export.

The LLM may also return `alias_cleanup` items when a product alias clearly
belongs to another product family. Because raw observations are audit data,
alias cleanup does not delete source rows. User-facing export filters
incompatible aliases out of the alias list, and the plan CSV marks cleanup
items for review.

## Operations

CLI:

```bash
python scripts/backfill_product_observations.py
python scripts/run_product_consolidation.py --mode dry-run --target all_provisional
python scripts/run_product_consolidation.py --mode rule-only-apply --target all_provisional
```

For existing data cleanup, do not rely on the newest product-id window. Run an
all-pages dry run first, inspect the exported CSV, then apply deterministic
rules:

```bash
python scripts/run_product_consolidation.py --mode dry-run --target all --all-pages
python scripts/run_product_consolidation.py --mode rule-only-apply --target all --all-pages
```

The dry-run/all-pages path exports `data/exports/product_consolidation_blocks.csv`
with candidate ids, names, product types, inferred partner candidates, release
month windows, and context similarity samples. LLM gray-block judgement remains
off by default; enable it only after reviewing deterministic blocks and with a
strict cost/call budget.

Run the version/birth/mobile regression gate after changing consolidation or
product-detail rendering:

```bash
python scripts/run_product_version_birth_mobile_goal_check.py
```

It does not crawl, reparse, or call Gemini/Qwen. The report is written to
`docs/product-version-birth-mobile-goal-result.md`.

To include family-signature diagnostics in the dry-run CSV:

```bash
python scripts/run_product_consolidation.py --mode dry-run --target all --all-pages --include-family-signature
```

The additional columns expose `family_signature`, `family_tokens`,
`same_company_family_reason`, `canonical_candidate`, `duplicate_product_ids`,
and `merge_confidence`, which are useful when checking why Excel rows were or
were not collapsed into a canonical product.

Optional LLM-assisted list-level review:

```bash
set PRODUCT_LLM_CONSOLIDATION_ENABLED=true
python scripts/check_product_duplicates.py --target all --output data/exports/product_duplicate_check.csv
python scripts/run_llm_product_consolidation.py --mode dry-run --target all --max-companies 20 --max-blocks 20 --output data/exports/product_full_list_llm_merge_plan.csv
python scripts/run_llm_product_consolidation.py --mode dry-run --target company --company-name "Shinhan Life" --max-blocks 5
python scripts/run_llm_product_consolidation.py --mode apply --target all --max-companies 20 --max-blocks 20
```

`check_product_duplicates.py` is read-only and never calls an LLM. The LLM plan
CSV defaults to `data/exports/product_full_list_llm_merge_plan.csv`. `dry-run`
does not change the DB. `apply` mutates only validator-approved merge groups
and records them in `fact_product_merge_decision`.

Recommended quality gate before a large Excel export:

```bash
python scripts/run_product_consolidation.py --mode rule-only-apply --target all --all-pages
python scripts/check_product_duplicates.py --target all --output data/exports/product_duplicate_check.csv
# Optional, administrator-approved only:
set PRODUCT_LLM_CONSOLIDATION_ENABLED=true
python scripts/run_llm_product_consolidation.py --mode dry-run --target all --max-companies 20 --max-blocks 20
python scripts/run_llm_product_consolidation.py --mode apply --target all --max-companies 20 --max-blocks 20
python scripts/check_product_duplicates.py --target all --output data/exports/product_duplicate_check_after.csv
```

The export path itself never calls an LLM. It only reports remaining duplicate
risk through the `duplicate_warnings` sheet when the selected canonical rows
still look split.

Admin API:

- `POST /api/admin/product-consolidation/run`
- `GET /api/admin/product-consolidation/jobs`
- `GET /api/admin/product-consolidation/jobs/{job_id}`
- `POST /api/admin/product-consolidation/merge`
- `POST /api/admin/product-consolidation/reject-merge`
- `GET /api/admin/product-consolidation/cost-summary`
- `GET /api/admin/product-consolidation/duplicate-check`
- `POST /api/admin/product-consolidation/llm-review`

Dashboard and Excel export hide `product_status='merged'` products by default
and include compatible alias/observation names on the canonical product row.
Excel export does not call an LLM. If the selected products still contain
possible duplicate canonical rows, export adds a `duplicate_warnings` sheet so
operators know to run duplicate check or full-list consolidation.

## Consolidation-Only GOAL Check

Before treating a large crawl/export result as final, run the consolidation-only
quality gate. This does not crawl news, does not reparse articles, and does not
call Gemini/Qwen in the rule-only path. It seeds a synthetic product catalog,
runs deterministic product consolidation, checks duplicate guard before/after,
and verifies the dashboard/export dataset has only canonical rows for the target
families.

```powershell
python scripts/run_product_consolidation_goal_check.py
```

The script writes `docs/product-consolidation-goal-result.md`. The current goal
cases are:

- Shinhan Life Tontine annuity variants collapse to one canonical product.
- Hanwha General Insurance Signature Women 4.0 variants collapse to one
  canonical product.
- Signature Women 3.0 and another insurer's Signature Women 4.0 remain separate.
- ABL Life health-refund variants collapse to one canonical product.
- ABL whole-body anesthesia surgery insurance remains a separate product and is
  not shown as a health-refund alias.
- Real Excel row 46/138-style StepUp 700 variants collapse to one canonical
  product without LLM.
- Real Excel row 115/116/117/120-style pet product variants collapse to one
  canonical product without LLM.

The real-export diagnosis is documented in
`docs/product-consolidation-real-export-diagnosis.md`. In short, the StepUp 700
case was caused by spacing/company-token/numeric-token differences in product
names, and the pet-product case was caused by a short generic alias (`펫보험`)
being split from a stronger branded product name. The fix is generalized: family
and version signatures still use product-name sources only, while deterministic
merge remains guarded by same company, compatible product type, close release
month, and non-conflicting version checks.

For the live operating DB remediation completed on 2026-06-03, run:

```powershell
python scripts/check_product_duplicates.py --output data/exports/product_duplicate_check_real_final_after_all_fixes.csv
```

The expected final result is `duplicate_group_count=0`,
`high_risk_group_count=0`, and `export_warning=false`. The process used
rule-only consolidation and recorded no `product_consolidation` LLM runs.
Sentence fragments or weak standalone product names such as `지키면보험`,
`다만건강보험`, and standalone `종합보험` are not canonical products. Existing
rows are kept for audit with `product_status='rejected'`, and the dashboard and
Excel views exclude both `merged` and `rejected` products.

Optional LLM-assisted list-level consolidation is only a fallback for duplicate
groups that deterministic rules cannot resolve. It is disabled by default and
uses compact same-company product lists only. It is never allowed during article
extraction, dashboard rendering, or Excel export, and it never performs pairwise
product comparisons. CI tests use mock providers only.

```powershell
set PRODUCT_LLM_CONSOLIDATION_ENABLED=true
python scripts/run_llm_product_consolidation.py --mode dry-run --target all --max-companies 20 --max-blocks 20
```

For an explicitly requested live smoke test, set both
`ENABLE_LIVE_LLM_CONSOLIDATION_TEST=true` and `GEMINI_API_KEY`; the script runs a
single dry-run block and writes
`docs/product-consolidation-live-llm-smoke-result.md`.

```powershell
python scripts/run_live_llm_product_consolidation_smoke.py
```

## Company Attribution Prerequisite

Product consolidation assumes company attribution has already been resolved by `CompanyAttributionService`. Before large all-pages consolidation, run the company attribution guard and review dry-run plans if mixed-company articles are suspected:

```powershell
python scripts/run_company_attribution_goal_check.py
python scripts/rebuild_product_company_attribution.py
```

Consolidation should not merge products across different resolved insurers, and short-alias-only company matches should remain review items.
