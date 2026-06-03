# Company Attribution Diagnosis

This project resolves insurer attribution through a deterministic shared layer,
not through article-level LLM comparison.

## Why Misattribution Happened

Mixed news articles often mention several insurers. If extraction picks the
first insurer in the title or article body, a product or exclusive-use-right can
be assigned to the wrong company. A typical failure is a title mentioning one
insurer while the local product launch or exclusive-use-right sentence names a
different insurer.

Short aliases are another risk. Names such as `Hanwha`, `Samsung`, `KB`, `DB`,
`NH`, `Nonghyup`, `Shinhan`, `Kyobo`, `Heungkuk`, `Meritz`, `Lotte`, and `Hana`
can point to life and non-life insurers. A short alias alone must not force a
company assignment.

## Policy

- Prefer company names found in the local product or exclusive-right evidence
  window.
- Treat article title and full article text as weaker context than the local
  window.
- Prefer full company names and long aliases over short aliases.
- Mark short-alias-only matches as review instead of assigning a company.
- Use company master and aliases before any LLM output.
- For exclusive-use-right records, association hints such as non-life or life
  insurance association text must be consistent with the resolved insurer type.
- Company attribution rebuilds must not call Gemini, Qwen, Naver, or any other
  external API.

## Shared Service

`app/services/company_attribution_service.py` is the common entry point for
product and exclusive-use-right company attribution. It returns:

- resolved `company_id`
- normalized company name
- insurance type
- confidence
- attribution basis
- review flag and reason

The service is now used by:

- product upsert in `app/db/repository.py`
- product candidate cluster creation
- exclusive-use-right save/review observation paths

## Rebuild Scripts

Use dry-run first:

```powershell
python scripts/rebuild_product_company_attribution.py
python scripts/rebuild_exclusive_right_company_attribution.py
```

The scripts write CSV plans under `data/exports/` with these columns:

- `entity_type`
- `entity_id`
- `old_company`
- `new_company`
- `old_insurance_type`
- `new_insurance_type`
- `product_or_subject_name`
- `confidence`
- `reason`
- `article_url`
- `action`

Apply only after reviewing the plan:

```powershell
python scripts/rebuild_product_company_attribution.py --apply
python scripts/rebuild_exclusive_right_company_attribution.py --apply
```

The scripts update company attribution only. They do not delete source data and
do not perform product/exclusive-right consolidation.

## Goal Check

Run:

```powershell
python scripts/run_company_attribution_goal_check.py
```

The report is written to `docs/company-attribution-goal-result.md`. Passing
criteria include zero product misattributions, zero exclusive-right
misattributions, no forced short-alias match, detection of a known wrong-row
rebuild candidate, and zero LLM runs.
