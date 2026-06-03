# Company Attribution Goal Result

Status: PASS

This check uses a temporary SQLite database and does not call Naver, Gemini, Qwen, or any other external API.

## Metrics

- `article_level_same_product_llm_calls`: 0
- `cluster_company_misattribution_count`: 0
- `exclusive_company_misattribution_count`: 0
- `product_company_misattribution_count`: 0
- `rebuild_candidates_detected`: 1
- `short_alias_forced_match_count`: 0
- `total_llm_runs`: 0

## Evidence

- Product upsert resolves company from local product context before article title or raw LLM candidate.
- Product candidate clusters pass title, description, and local launch text separately into the shared attribution service.
- Exclusive-right extraction resolves company from the local exclusive-right evidence window and association hint.
- Short aliases such as `삼성` do not force a company without stronger local evidence.
- Rebuild dry-run detects an existing wrong exclusive-right company attribution candidate without LLM calls.
