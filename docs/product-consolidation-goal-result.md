# Product Consolidation GOAL Result

- GOAL: GOAL_PRODUCT_CONSOLIDATION_REAL_EXPORT_DUPLICATE_FIX_V2
- status: PASS
- seeded_product_count: 30
- duplicate_groups_before: 6
- duplicate_groups_after_rule_only: 0
- duplicate_groups_final: 0
- rule_only_auto_merge_count: 21
- llm_assisted_status: not_needed
- llm_run_count: 0
- cached_run_count: 0

## Export Row Counts
- tontine: 1
- signature_4_hanwha: 1
- signature_4_other_company: 1
- signature_3: 1
- health_refund: 1
- surgery: 1
- stepup_700: 1
- pet_brand: 1

## Assertions
- PASS: tontine export row count == 1
- PASS: Hanwha signature 4.0 export row count == 1
- PASS: other company signature 4.0 remains separate
- PASS: signature 3.0 remains separate
- PASS: health refund export row count == 1
- PASS: whole body anesthesia surgery remains separate
- PASS: real export row 46/138 StepUp 700 count == 1
- PASS: real export row 115/116/117/120 pet product count == 1
- PASS: critical duplicate groups cleared
- PASS: rule-only path did not call LLM

## Real DB Follow-Up

- run date: 2026-06-03
- backup before remediation: `backups/insurance_news_before_real_product_duplicate_finish_20260603_172357.db`
- final duplicate report: `data/exports/product_duplicate_check_real_final_after_all_fixes.csv`
- duplicate_group_count: 0
- duplicate_product_count: 0
- high_risk_group_count: 0
- export_warning: false
- visible canonical/provisional products in `vw_product_search`: 325
- merged products retained for audit: 165
- rejected weak/bad product rows: 7
- `fact_llm_run.task_type='product_consolidation'`: 0

Rejected weak or bad product fragments are retained in `dim_product` for audit but
excluded from dashboard/export views: `지키면보험`, `다만건강보험`, `종합보험`.
