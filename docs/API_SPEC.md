## Runtime extraction and batch guard additions

Admin crawl job requests support `extraction_mode`:

- `none`: collect only.
- `screening_only`: run/store screening for the crawl job articles, no provider calls.
- `enqueue_only`: run screening/snippets/clustering and create LLM queue items for the crawl job, no provider calls.
- `batch`: same as `enqueue_only`, but queues are marked `batch_eligible_yn=true`.
- `realtime`: run realtime extraction only for articles whose `crawl_job_id` matches the job.

Example:

```json
{
  "include_llm_extraction": true,
  "extraction_mode": "batch",
  "include_exclusive_right_pipeline": true,
  "exclusive_right_pipeline_mode": "batch",
  "exclusive_right_auto_submit_batch": false,
  "exclusive_right_auto_consolidate": true,
  "exclusive_right_limit": 1000,
  "include_reinsurers": false,
  "include_foreign_branches": false
}
```

Exclusive-use-right crawl pipeline modes are `none`, `screening_only`, `enqueue_only`, `batch`, and `realtime`. The safe operating default is `batch` with `exclusive_right_auto_submit_batch=false`, so crawl completion prepares scoped queues and a Batch job without realtime provider calls. `POST /api/admin/llm-batch-jobs/create` also accepts optional `crawl_job_id`; when supplied, only pending batch-eligible queue items for that crawl job are batched.

`GET /api/admin/llm-execution-guard-summary` includes `cluster_reuse_count` and `batch_eligible_queue_count` in addition to low/skip, article-level same-product, and full-body prompt violation counters.

# API Spec

## Articles

`POST /api/articles/collect`

```json
{"query_group":"new_product","days_back":30,"max_results_per_query":100}
```

`GET /api/articles`

filters: `query`, `source_api`, `pub_date_from`, `pub_date_to`, `extraction_status`.

## Extractions

`POST /api/extractions/article/{article_id}`

`POST /api/extractions/pending?limit=20`

`POST /api/extractions/from-text`

```json
{"title":"선택","text":"보험상품 관련 기사 또는 설명 텍스트","source_note":"선택"}
```

저장 전 후처리는 LLM 추출값, verifier suggested_value, 출시 문장 기반 deterministic 후보, 상품분류 rule을 함께 사용한다. 앱/서비스/할인명으로 판단되는 `신한SOL`, `신한SOL 다이렉트`, `신한SOL EZ손보`, `쏠Drive`, `쏠Walk` 등은 상품명으로 저장하지 않으며, `신규 출시` 문장에 직접 연결된 보험상품명이 있으면 그 값을 우선 저장한다. 보정 이력은 `fact_extraction_field_audit`에 남긴다.

## Structured Ingestion

`POST /api/ingestion/structured-product`

```json
{
  "product": {
    "raw_product_name": "간편암보험",
    "normalized_product_name": "간편암보험",
    "company_name": "삼성화재",
    "insurance_type": "손해보험",
    "release_year_month": "2026-05",
    "primary_product_type_code": "CANCER"
  },
  "product_type_assignments": [],
  "features": {},
  "narrative_insights": {},
  "major_coverages": [],
  "sales_metrics": []
}
```

## Products

`GET /api/products/search`

filters: `q`, `company_name`, `insurance_type`, `product_type_code`, `release_year_month_from`, `release_year_month_to`, `include_secondary_types`, `min_confidence`, `include_review`, `company_role`, `status_2024_2026`, `include_reinsurers`, `include_foreign_branches`, `include_inactive_or_changed_companies`.

`GET /api/products/{product_id}` returns product, type assignments, features, narrative insights, coverages, sales metrics, related articles, release month source fields, and `product_aliases`.

Product detail response includes `release_year_month_basis`, `release_year_month_source_article_id`, `release_year_month_source_type`, `release_year_month_inferred_at`. When the basis is `earliest_related_article_month`, the release month was inferred from the earliest related article month.

`major_coverages` is deduplicated before response by normalized coverage name, risk area, benefit type, amount, and condition. The dashboard applies the same defensive dedupe for both PC table and mobile coverage cards.

`product_aliases` items include `raw_product_name`, `normalized_product_name_candidate`, `product_core_key`, `article_id`, `source_type`, `first_seen_at`, `last_seen_at`, and `observation_count`.

## Companies

`GET /api/companies`

filters: `insurance_type`, `company_role`, `status_2024_2026`, `include_product_news_default_only`, `include_reinsurers`, `include_foreign_branches`, `include_changed_companies`, `include_short_term_insurers`, `include_establishment_info`.

Response items include `company_id`, `company_name_normalized`, `alias`, `insurance_type`, `company_role`, `status_2024_2026`, `include_in_product_news_default`, `display_label`, establishment fields, and `notes`.

Establishment fields: `establishment_year`, `establishment_month`, `establishment_day`, `establishment_sort_date`, `establishment_basis`, `oldest_predecessor_year`, `current_brand_year`, `display_order_established`, `sort_tie_breaker`, `establishment_source_note`.

`/api/companies` 응답은 보험업권별 설립년도 표시순서로 정렬된다. `current_brand_year`는 사명변경/현 브랜드 출범 참고값이며 정렬 기준으로 사용하지 않는다.

`POST /api/companies/normalize`

```json
{"text":"DGB생명은 신상품을 출시했다"}
```

Returns alias matches such as `DGB생명` → `iM라이프생명`.

## Pivots

`POST /api/pivots/run`

```json
{
  "base": "product",
  "classification_mode": "include_secondary",
  "rows": ["company_name", "product_type_name"],
  "columns": ["release_year_month"],
  "filters": {},
  "metrics": [{"name":"product_count","agg":"count_distinct","field":"product_id"}],
  "include_review": false,
  "min_confidence": 0.65
}
```

## Review and LLM Runs

- `GET /api/review/queue`
- `POST /api/review/resolve`
- `GET /api/llm-runs`
- `GET /api/llm-runs/metrics`

## Dashboard

`GET /`

사용자용 대시보드를 렌더링한다.

`GET /api/dashboard/options`

대시보드 초기 필터 옵션을 반환한다.

Query flags: `include_reinsurers`, `include_foreign_branches`, `include_changed_companies`, `include_short_term_insurers`.

`companies` items include `company_id`, `company_name`, `company_name_normalized`, `insurance_type`, `company_role`, `status_2024_2026`, `include_in_product_news_default`, `display_label`, `establishment_year`, `establishment_sort_date`, `display_order_established`, `establishment_source_note`.

대시보드 회사 옵션은 `/api/companies`와 같은 설립년도 표시순서를 따른다. 클라이언트는 회사명을 가나다순으로 다시 정렬하지 않는다.

`product_types`는 sort_order 기준으로 반환하며 시장형 상품군 전체를 포함한다. 신규 포함 코드: `SPECIFIC_DISEASE`, `MEDICAL_INDEMNITY`, `AUTO`, `TRAVEL_LEISURE`, `PET`, `DENTAL`, `ANNUITY_SAVINGS`, `VARIABLE_UL`, `GUARANTEE_CREDIT`, `CORPORATE_GROUP_SPECIALTY`. `DEATH_WHOLELIFE` 표시명은 `사망(종신/정기)`이다.

`GET /api/dashboard/demo-status`

현재 DB에 상품/기사 데이터가 있는지 반환한다.

`GET /api/dashboard/data-status`

대시보드/관리자 패널의 적재 상태를 반환한다.

```json
{
  "article_count": 1234,
  "product_count": 240,
  "last_crawl_started_at": "2026-05-27T10:00:00",
  "last_crawl_finished_at": "2026-05-27T10:15:00",
  "last_successful_job_name": "weekly_incremental",
  "last_failed_job_name": null,
  "pending_extraction_count": 120
}
```

`GET /api/dashboard/monthly-new-products`

첫 화면 상단 `이달의 신상품 현황판`에 표시할 상품 목록을 반환한다. 이 API는 추가 LLM 호출을 하지 않고 기존 DB의 narrative insight, 기사 description, 기사 title만 사용해 요약을 만든다.

Query parameters:

- `year_month` optional, `YYYY-MM` 형식. 없으면 서버 기준 현재월을 사용한다.
- `limit` optional, 기본 `10`.
- `fallback_latest` optional, 기본 `true`. 대상 월 상품이 없으면 가장 최근 출시월 상품을 반환한다.
- `insurance_type` optional. `생명보험`, `손해보험`, `전체` 중 하나.
- `include_review` optional, 기본 `false`.

응답:

```json
{
  "year_month": "2026-05",
  "display_year_month": "2026년 5월",
  "fallback_used": false,
  "items": [
    {
      "product_id": 1,
      "product_name": "시그니처 여성건강보험 4.0",
      "raw_product_name": "한화 시그니처 여성 건강보험4.0 무배당",
      "company_name": "한화손해보험",
      "insurance_type": "손해보험",
      "release_year_month": "2026-05",
      "release_year_month_basis": "explicit_in_article",
      "primary_product_type": "건강(종합)",
      "summary": "여성 주요 질환 보장을 강화한 건강보험 신상품입니다.",
      "article_title": "한화손해보험, '시그니처 여성 건강보험4.0' 출시",
      "article_pub_date": "2026-05-03T09:00:00",
      "article_url": "https://example.com/news",
      "source_label": "원문 기사",
      "confidence_total": 0.86,
      "needs_review": false
    }
  ]
}
```

대표 기사는 `release_year_month_source_article_id`를 우선 사용하고, 없으면 출시/신상품 키워드가 있는 관련기사, 가장 오래된 관련기사 순으로 선택한다. `article_url`은 `original_url`을 우선하고 없으면 `url`을 사용한다.

`POST /api/dashboard/query`

필터 조건을 받아 `summary`, `pivot_result`, `products`를 함께 반환한다. 대시보드 화면은 `products`를 상품 비교표로 표시하며 `pivot_result`는 기존 API 호환을 위해 유지한다.

대시보드 UI는 피벗 요약을 표시하지 않는다. `classification_mode="include_secondary"`, `pivot_preset="custom"`, `custom_columns=[]`, `custom_rows=["company_name", "product_type_name"]`을 고정으로 사용한다.

화면 필터는 출시년도, 업종, 보험회사, 보종군 순서로 제공한다. 보험회사 목록은 업종 선택 전에는 비어 있고, `생명보험` 또는 `손해보험` 선택 후 해당 업종 회사만 체크박스로 표시한다. 출시년도, 보험회사, 보종군은 체크박스형 다중 선택이며 `전체선택` 상태는 request 배열을 빈 배열로 보내 필터 없음으로 표현한다.

기본 request 값:

```json
{
  "release_year": "전체",
  "release_years": [],
  "release_month": "전체",
  "insurance_type": "전체",
  "company_names": [],
  "product_type_codes": [],
  "classification_mode": "include_secondary",
  "pivot_preset": "custom",
  "custom_rows": ["company_name", "product_type_name"],
  "custom_columns": [],
  "custom_metrics": ["product_count", "article_count"],
  "include_review": false,
  "min_confidence": 0,
  "include_reinsurers": false,
  "include_foreign_branches": false,
  "include_changed_companies": true,
  "include_short_term_insurers": true
}
```

`release_years=[]`는 출시년도 전체를 뜻한다. `company_names=[]`는 선택 업종 내 보험회사 전체를 뜻한다. `product_type_codes=[]`는 보종군 전체를 뜻한다. 화면에는 `release_years`, `insurance_type`, `company_names`, `product_type_codes`, `include_reinsurers`, `include_foreign_branches`가 노출된다.

Request flags include `include_reinsurers`, `include_foreign_branches`, `include_changed_companies`, `include_short_term_insurers`. 대시보드 화면에서는 `include_changed_companies=true`, `include_short_term_insurers=true`를 고정으로 보내며, 사용자는 재보험/외국지점 포함 여부만 조정한다.

`POST /api/dashboard/export`

`/api/dashboard/query`와 같은 request body를 받아 현재 필터 조건의 상품 비교표를 Excel 파일로 반환한다.

Response content type:

`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`

다운로드 파일명은 `insurance_product_comparison.xlsx`이다. Excel sheet는 `상품 비교표`이며 상품 1개를 1행으로 두고 항목을 컬럼으로 펼친 가로형 비교표를 반환한다. 기본 컬럼은 상품 ID, 상품명, 원문 상품명, 보험회사, 원문 회사명, 출시년월, 최초 확인월, 대표 보종군, 가입연령, 고지유형, 판매채널, 갱신/비갱신, 납입기간, 보험기간, 요약 항목이다. 주요보장, 판매실적, 관련기사는 `주요보장1 보장명`, `판매실적1 항목`, `관련기사1 제목`처럼 번호 컬럼으로 펼친다. 보조 보종군, 항목 구분, 항목명, 값, 근거/설명, confidence, 검수필요, 관련 URL은 포함하지 않는다.

## Admin Crawl Jobs

관리자 배치 API는 `Authorization: Bearer {token}` 헤더가 필요하다. 토큰은 `POST /api/admin/auth`로 발급받으며, 서버 환경변수 `ADMIN_BATCH_PASSWORD` 또는 `ADMIN_BATCH_PASSWORD_HASH`가 설정되어 있어야 한다.

`POST /api/admin/auth`

```json
{"password": "관리자 비밀번호"}
```

Response:

```json
{"ok": true, "token": "...", "expires_at": "2026-05-27T10:30:00"}
```

`POST /api/admin/crawl-jobs/test-2026-01`

2026-01-01 ~ 2026-01-31 테스트 수집 job을 만든다.

```json
{
  "include_llm_extraction": false,
  "include_exclusive_right_pipeline": true,
  "exclusive_right_pipeline_mode": "batch",
  "exclusive_right_auto_submit_batch": false,
  "exclusive_right_auto_consolidate": true,
  "include_reinsurers": false,
  "include_foreign_branches": false
}
```

`POST /api/admin/crawl-jobs/backfill-2024-2026-05`

2024-01-01 ~ 2026-05-31 전체 Backfill job을 월별 task로 만든다.

`POST /api/admin/crawl-jobs/incremental`

최근 7/14/30일 증분 수집 job을 만든다.

```json
{"days_back": 14, "include_llm_extraction": false, "include_reinsurers": false, "include_foreign_branches": false}
```

`POST /api/admin/crawl-jobs/manual-range`

```json
{"date_from": "2026-01-01", "date_to": "2026-01-31", "include_llm_extraction": false}
```

`GET /api/admin/crawl-jobs`

최근 crawl job 목록을 반환한다.

`GET /api/admin/crawl-jobs/{crawl_job_id}`

job 집계, task 목록, 최근 event log를 반환한다. 진행률은 `completed_tasks / total_tasks`로 계산한다.

배타적사용권 pipeline을 요청한 job은 다음 필드를 함께 반환한다: `include_exclusive_right_pipeline`, `exclusive_right_pipeline_mode`, `exclusive_right_pipeline_status`, `exclusive_right_candidate_count`, `exclusive_right_queue_created_count`, `exclusive_right_batch_job_id`, `exclusive_right_batch_status`, `exclusive_right_imported_count`, `exclusive_right_canonical_count`, `exclusive_right_consolidation_job_id`, `exclusive_right_pipeline_error`.

`POST /api/admin/crawl-jobs/{crawl_job_id}/cancel`

pending/running job에 취소 요청을 남긴다. 이미 진행 중인 task가 끝난 뒤 안전하게 중단된다.

`POST /api/admin/crawl-jobs/{crawl_job_id}/retry-failed`

failed task만 pending으로 되돌리고 다시 실행한다.

`POST /api/admin/search-preview/naver-news`

관리자 진단용 네이버 뉴스 검색 preview다. 임의 검색어를 허용하므로 `"한화손해보험 건강보험 2026년 1월"`처럼 월 키워드가 포함된 query도 직접 테스트할 수 있다. 이 기능은 preview 전용이며 자동 수집 QueryGenerator는 월 키워드를 생성하지 않는다.

```json
{"query": "한화손해보험 건강보험 2026년 1월", "display": 10, "start": 1, "sort": "date"}
```

## Admin LLM Batch Jobs

관리자 Bearer token이 필요하다. 이 API는 대량 백필 추출용이며, 실시간 소량 추출은 기존 extraction API를 사용한다.

`POST /api/admin/llm-batch-jobs/create`

pending 상태의 batch eligible queue를 모아 Gemini Batch 입력 JSONL을 만들고, `submit=true`이면 즉시 provider에 제출한다.

```json
{
  "task_type": "extract",
  "provider": "gemini",
  "model_name": "gemini-2.5-flash",
  "limit": 1000,
  "submit": true
}
```

응답에는 `llm_batch_job_id`, `status`, `provider_batch_id`, `provider_status`, `input_file_path`, `request_count`, `completed_count`, `failed_count`가 포함된다.

`POST /api/admin/llm-batch-jobs/{llm_batch_job_id}/submit`

prepared 상태의 batch job을 Gemini Batch API에 제출한다. 제출 성공 시 provider batch id를 `provider_batch_id`에 저장하고 `submitted_at`을 기록한다.

`GET /api/admin/llm-batch-jobs`

최근 LLM batch job 목록과 현재 pending batch eligible queue 수를 반환한다. `task_type` query parameter를 줄 수 있으며, 배타적사용권 batch 대기 수는 `task_type=exclusive_right_extract`로 조회한다.

```json
{
  "pending_batch_eligible_count": 240,
  "jobs": []
}
```

`GET /api/admin/llm-batch-jobs/{llm_batch_job_id}`

batch job 상세와 연결된 queue 목록을 반환한다.

`POST /api/admin/llm-batch-jobs/{llm_batch_job_id}/refresh-status`

provider batch 상태를 조회해 `provider_status`, `completed_count`, `failed_count`, `error_message`를 갱신한다. 완료 상태이면 `status=provider_completed`, 실패 상태이면 `status=provider_failed`로 표시한다.

`POST /api/admin/llm-batch-jobs/{llm_batch_job_id}/import-results`

완료된 output JSONL을 다운로드 또는 로컬 파일에서 읽어 extraction schema 검증 후 DB에 반영한다. 성공한 output은 queue를 `completed`로, 실패 output은 `failed`로 변경하고 `last_error`를 남긴다. import는 idempotent하며 같은 batch output을 다시 읽어도 같은 queue의 성공 run을 중복 저장하지 않는다.

batch import로 저장된 실행 로그는 `fact_llm_run.batch_yn=true`, 비용 로그는 `fact_llm_cost_log.batch_yn=true`로 기록된다.

## Admin LLM Cost Summary

`GET /api/admin/llm-execution-guard-summary`

Requires administrator bearer token.

Returns runtime guardrail health for the cost-saving extraction path.

```json
{
  "article_count": 1000,
  "screened_high_count": 120,
  "screened_medium_count": 80,
  "screened_low_count": 300,
  "screened_skip_count": 500,
  "llm_queue_count": 180,
  "total_run_count": 70,
  "extract_run_count": 60,
  "verify_run_count": 8,
  "adjudicate_run_count": 2,
  "product_consolidation_run_count": 0,
  "cached_run_count": 20,
  "batch_run_count": 10,
  "cache_hit_rate": 0.2857,
  "low_skip_llm_violation_count": 0,
  "article_level_same_product_llm_violation_count": 0,
  "full_body_prompt_violation_count": 0,
  "verify_only_risky_enabled": true,
  "snippet_only_enabled": true,
  "cluster_extraction_enabled": true,
  "product_consolidation_llm_enabled": false
}
```

The endpoint is intended for operator checks after crawl/extraction runs. A non-zero violation count means a runtime path bypassed the expected screening, snippet-only, or product-consolidation isolation policy.

`GET /api/admin/llm-cost-summary`

관리자 Bearer token이 필요하다.

응답:

```json
{
  "date_from": null,
  "date_to": null,
  "total_estimated_cost_usd": 0.0,
  "by_model": [],
  "by_task_type": [],
  "cache_hit_rate": 0.0,
  "batch_request_count": 0,
  "input_tokens_total": 0,
  "output_tokens_total": 0,
  "cached_tokens_total": 0,
  "run_count": 0,
  "extract_run_count": 0,
  "verify_run_count": 0,
  "adjudicate_run_count": 0,
  "grounded_run_count": 0,
  "estimate_quality": "rough"
}
```

LLM 비용은 `fact_llm_cost_log` 기준으로 집계한다. cache hit은 `fact_llm_run.cached_yn`, batch 요청 수는 `fact_llm_cost_log.batch_yn`으로 계산한다.

`GET /api/admin/llm-cost-savings-summary`

관리자 Bearer token이 필요하다.

Query parameters:

- `date_from` optional
- `date_to` optional
- `baseline_policy` optional, 기본 `all_articles_fulltext_extract_and_verify`
- `include_breakdown` optional, 기본 `true`

지원 baseline policy:

- `all_articles_fulltext_extract_only`
- `all_articles_fulltext_extract_and_verify`
- `candidate_articles_fulltext_extract_only`
- `candidate_articles_fulltext_extract_and_verify`

응답:

```json
{
  "date_from": "2026-01-01",
  "date_to": "2026-01-31",
  "baseline_policy": "all_articles_fulltext_extract_and_verify",
  "estimate_quality": "mixed",
  "baseline_estimated_cost_usd": 124.72,
  "optimized_actual_cost_usd": 18.43,
  "estimated_savings_usd": 106.29,
  "estimated_savings_rate": 0.852,
  "counts": {
    "article_count": 5320,
    "screened_high_count": 480,
    "screened_medium_count": 360,
    "screened_low_count": 900,
    "screened_skip_count": 3580,
    "llm_queue_count": 840,
    "llm_run_count": 312,
    "extract_run_count": 240,
    "verify_run_count": 55,
    "adjudicate_run_count": 17,
    "cluster_count": 180,
    "cache_hit_count": 44,
    "batch_run_count": 190
  },
  "tokens": {
    "baseline_input_tokens": 38000000,
    "optimized_input_tokens": 4200000,
    "baseline_output_tokens": 9300000,
    "optimized_output_tokens": 730000
  },
  "breakdown": {
    "screening_saved_usd": 62.1,
    "snippet_saved_usd": 21.4,
    "cluster_saved_usd": 11.7,
    "selective_verification_saved_usd": 8.3,
    "cache_saved_usd": 1.9,
    "batch_saved_usd": 0.89
  },
  "by_model": [],
  "by_task_type": []
}
```

절감률은 `1 - optimized_actual_cost_usd / baseline_estimated_cost_usd`로 계산한다. 실제 token이 없으면 입력 텍스트 길이 기준 rough estimate를 사용하며, `input_hash`는 token 추정에 사용하지 않는다. 가격표에 없는 provider/model은 `estimate_quality=missing_price`로 표시된다.
## Dashboard Keyword Search And Canonical Products

`DashboardQueryRequest` supports:

- `keyword: string | null`
- `keyword_fields: string[]`

When `keyword` is provided, `/api/dashboard/query` and `/api/dashboard/export` filter products by product name, raw product name, product alias, product summaries, coverage names/summaries, and related article title/description. The export endpoint uses the same request body and therefore the same keyword condition.

Product detail responses may include canonicalization fields:

- `product_status`: `active`, `merged`, or `review`
- `canonical_product_id`
- `merged_into_product_id`
- `product_aliases`
- `product_partners`
- `merge_decisions`

Dashboard query/export hides `product_status='merged'` products by default and returns the canonical product row. Excel export includes alias list, canonical product id, merge reason summary, partner company, and source article URLs.
The product Excel export does not call an LLM. It filters clearly incompatible
aliases from the canonical alias list and, when possible duplicate canonical
rows remain in the exported result, adds a `duplicate_warnings` sheet.

## Product Consolidation Admin APIs

All product consolidation endpoints require the same administrator bearer token used by the crawl and LLM admin APIs.

### POST `/api/admin/product-consolidation/run`

Runs a ProductConsolidationJob. Article-level extraction is not performed here; this job consumes already saved products and `fact_product_observation` rows.

Request:

```json
{
  "mode": "dry_run",
  "target": "all_provisional",
  "limit": 500,
  "use_llm_for_gray_blocks": false
}
```

Supported `mode` values:

- `dry_run`: create blocks and decisions without applying merges.
- `rule_only_apply`: apply deterministic merge rules only.
- `apply_with_llm_gray_blocks`: apply deterministic rules and, when enabled by environment and request option, send eligible gray blocks to a block-level LLM judge.

Supported `target` values:

- `new_since_last_job`
- `all_provisional`
- `all`
- `selected`

Response contains job counters and block details, including `consolidation_job_id`, `status`, `block_count`, `auto_merge_count`, `manual_review_count`, `llm_call_count`, and `estimated_cost_usd`.

### GET `/api/admin/product-consolidation/jobs`

Returns recent ProductConsolidationJob records.

### GET `/api/admin/product-consolidation/jobs/{job_id}`

Returns one job and its consolidation blocks.

### POST `/api/admin/product-consolidation/merge`

Manually merges duplicate products into a canonical product.

Request:

```json
{
  "canonical_product_id": 1,
  "duplicate_product_ids": [2, 3],
  "reason": "manual review"
}
```

### POST `/api/admin/product-consolidation/reject-merge`

Marks a consolidation block as not merged.

Request:

```json
{
  "block_id": 10,
  "reason": "different products"
}
```

### GET `/api/admin/product-consolidation/cost-summary`

Returns product consolidation operating metrics:

```json
{
  "observation_count": 1200,
  "block_count": 85,
  "deterministic_auto_merge_count": 760,
  "llm_call_count": 3,
  "llm_cache_hit_count": 1,
  "review_count": 20,
  "estimated_pairwise_comparison_avoided": 50000,
  "estimated_call_reduction_rate": 0.999
}
```
## Exclusive Use Rights

### `GET /api/exclusive-rights`

배타적사용권 목록을 조회한다. 응답 item에는 업종과 보험회사 필드가 항상 포함된다.

Query parameters:

- `insurance_type`: `생명보험`, `손해보험`, `unknown`, `전체`
- `company_id`
- `company_name`: 표준 회사명 또는 alias
- `company_names`: 반복 query 또는 comma-separated 값
- `acquired_year_month_from`, `acquired_year_month_to`
- `months_back`
- `include_review`
- `keyword`

Response item 주요 필드:

```json
{
  "exclusive_right_id": 1,
  "insurance_type": "손해보험",
  "company_id": 10,
  "company_name": "한화손해보험",
  "company_name_normalized": "한화손해보험",
  "subject_name": "OO보험",
  "exclusivity_months": 6,
  "acquired_year_month": "2026-05",
  "feature_summary": "...",
  "primary_article_url": "https://example.com"
}
```

### `GET /api/exclusive-rights/{exclusive_right_id}`

목록 필드에 더해 observation별 표준 회사명, 업종, 원문 subject, 정규화 subject 후보, 근거문장, 상태 후보를 반환한다. 원문 회사명, 구분, subject type, 기간 원문, 획득년월 basis는 기본 응답에 포함하지 않는다.

### `POST /api/exclusive-rights/export`

목록과 같은 필터를 request body로 받으며 Excel 파일을 반환한다. 컬럼 순서는 `배타적사용권 ID`, `업종`, `보험회사`, `상품/특약/제도명`, `배타적사용권 기간 개월 수`, `획득년월`, `주요 특징`, `대표 기사 제목`, `대표 기사 URL`, `alias 목록`, `근거문장`이다.

### `GET /api/dashboard/recent-exclusive-rights`

최근 1년 배타적사용권 현황판용 API다. `insurance_type` 필터를 지원하며 item에는 `insurance_type`, `company_id`, `company_name`을 포함한다.

## Exclusive Use Rights Admin APIs

### POST /api/admin/exclusive-rights/llm-consolidation-review

Runs optional list-level LLM review for exclusive-use-right consolidation
blocks.

Request:

```json
{
  "mode": "dry_run",
  "target": "all",
  "limit": 1000,
  "max_blocks": 20
}
```

### GET `/api/admin/product-consolidation/duplicate-check`

Read-only duplicate risk check. It does not call an LLM and does not mutate the
database.

Query parameters:

- `company_id`
- `company_name`
- `export_csv`: when true, writes `data/exports/product_duplicate_check.csv`

Response:

```json
{
  "duplicate_group_count": 2,
  "duplicate_product_count": 6,
  "high_risk_group_count": 1,
  "export_warning": true,
  "csv_path": "data/exports/product_duplicate_check.csv",
  "groups": []
}
```

### POST `/api/admin/product-consolidation/llm-review`

Runs optional company full-list LLM product consolidation. It is disabled unless
`PRODUCT_LLM_CONSOLIDATION_ENABLED=true`. The request sends compact product
catalog rows only, never full article bodies, and applies only
validator-approved merge groups when `mode=apply`.

Request:

```json
{
  "mode": "dry_run",
  "target": "all",
  "company_name": null,
  "limit": 1000,
  "max_companies": 20,
  "max_blocks": 20
}
```

Use `target="company"` with `company_name` to review one insurer first. The plan
CSV defaults to `data/exports/product_full_list_llm_merge_plan.csv`.

Response:

```json
{
  "job_id": null,
  "block_count": 5,
  "llm_call_count": 2,
  "auto_apply_count": 6,
  "review_count": 2,
  "reject_count": 1,
  "estimated_cost_usd": 0.12,
  "plan_file": "data/exports/exclusive_right_llm_merge_plan.csv"
}
```

The LLM returns a merge/reject/review plan only. DB changes happen only in
`mode=apply` and only after deterministic validation. The endpoint is disabled
unless `EXCLUSIVE_RIGHT_LLM_CONSOLIDATION_ENABLED=true`.

### `POST /api/admin/exclusive-rights/extract-pending`

관리자 토큰이 필요하다. `fact_content_screening.exclusive_right_candidate_yn=true`인 기사만 대상으로 배타적사용권 정형화 작업을 만든다. 상품 관련성이 낮아도 배타적사용권 후보이면 처리 대상이 될 수 있다.

Request:

```json
{
  "crawl_job_id": 1,
  "limit": 100,
  "mode": "enqueue_only",
  "date_from": "2026-01-01",
  "date_to": "2026-12-31"
}
```

`mode`:

- `none`: no screening or queue creation.
- `screening_only`: run screening and save `exclusive_right_candidate_yn`; no queue/provider call.
- `enqueue_only`: `fact_llm_queue`에 `task_type='exclusive_right_extract'`만 생성하고 provider를 호출하지 않는다.
- `batch`: `batch_eligible_yn=true` queue를 생성한다. 이후 `POST /api/admin/llm-batch-jobs/create`에서 `task_type='exclusive_right_extract'`로 Batch job을 만든다.
- `realtime`: exclusive snippet bundle을 사용해 즉시 정형화한다. 소량 진단용이며 `EXCLUSIVE_RIGHT_REALTIME_LIMIT`를 넘으면 400을 반환한다.

Response:

```json
{
  "mode": "batch",
  "candidate_count": 10,
  "processed": 10,
  "queued": 10,
  "queued_count": 10,
  "saved": 0,
  "batch_eligible": 10,
  "batch_eligible_count": 10,
  "skipped_existing_queue_count": 0,
  "skipped_existing_observation_count": 0
}
```

### `GET /api/admin/exclusive-rights/extract-queue-status`

관리자 토큰이 필요하다. `date_from`, `date_to` query parameter를 받을 수 있으며, 배타적사용권 후보 기사 수, pending queue 수, batch eligible queue 수, completed queue 수, observation/canonical event 수를 반환한다.

`crawl_job_id` query parameter가 있으면 해당 crawl job 기사와 queue만 집계한다.

### `POST /api/admin/exclusive-rights/consolidate`

관리자 토큰이 필요하다. Request body:

```json
{
  "crawl_job_id": 1,
  "mode": "dry_run",
  "date_from": "2026-01-01",
  "date_to": "2026-01-31"
}
```

`mode`는 `dry_run` 또는 `rule_only_apply`이다. 기간 충돌은 자동 병합하지 않고 review로 남긴다.

### `POST /api/admin/llm-batch-jobs/create` with `exclusive_right_extract`

배타적사용권 Batch 추출은 기존 Batch API를 재사용한다.

```json
{
  "task_type": "exclusive_right_extract",
  "provider": "gemini",
  "model_name": "gemini-2.5-flash",
  "limit": 1000,
  "submit": false,
  "crawl_job_id": 1
}
```

Batch input JSONL은 `custom_id=exclusive_right_extract:queue:{queue_id}:article:{article_id}:crawl:{crawl_job_id}`와 `metadata.queue_id`, `metadata.target_id`, `metadata.crawl_job_id`를 포함한다. Batch output import 시 `exclusive_right_extraction_schema`를 검증하고, `acquired` 상태는 observation/canonical/article mapping/alias에 저장한다. `applied_or_planned` 상태는 active canonical event로 확정하지 않고 review observation으로만 남긴다. Import는 idempotent하며 같은 output을 다시 읽어도 canonical/observation/article/alias가 중복 생성되지 않는다. `crawl_job_id`가 연결된 batch import는 crawl job의 `exclusive_right_imported_count`, `exclusive_right_canonical_count`, `exclusive_right_pipeline_status`도 갱신한다.

## Dashboard Data Status Additions

`GET /api/dashboard/data-status`는 배타적사용권 운영 상태를 함께 반환한다.

```json
{
  "exclusive_right_count": 12,
  "recent_exclusive_right_count_12m": 7,
  "pending_exclusive_right_extraction_count": 3,
  "last_exclusive_right_acquired_year_month": "2026-05"
}
```
## Dashboard UI 보강 API

### `GET /api/dashboard/recent-exclusive-rights`

최근 배타적사용권 현황판용 API다. 데이터가 없어도 404가 아니라 200과 `items=[]`를 반환한다.

Query parameters:

- `months_back`: 기본 `12`
- `limit`: 기본 `10`
- `insurance_type`: `생명보험`, `손해보험`, 또는 미지정
- `include_review`: 기본 `false`
- `fallback_latest`: 기본 `true`

Response item 주요 필드: `exclusive_right_id`, `insurance_type`, `company_id`, `company_name`, `subject_name`, `exclusivity_months`, `acquired_year_month`, `summary`, `article_title`, `article_url`.

### `POST /api/dashboard/query`

`DashboardQueryRequest`에는 `include_excluded_policy_products`가 추가되었다. 기본값은 `false`이며, 상품명/원문명/alias/observation에 `실손의료`가 포함된 상품은 일반 대시보드 조회에서 제외된다. DB 삭제가 아니라 조회 정책이다.

### `GET /api/exclusive-rights`

배타적사용권 조회목록 API다. 기본적으로 `event_status='merged'` event와 `needs_review=true` event는 제외한다.

필터:

- `insurance_type`
- `company_id`
- `company_name`
- `company_names`
- `acquired_year_month_from`
- `acquired_year_month_to`
- `months_back`
- `include_review`
- `keyword`
- `limit`

`keyword`는 subject name, alias, feature summary, representative article title, evidence text를 검색한다.

### `POST /api/exclusive-rights/export`

배타적사용권 조회목록과 동일한 필터 body를 받아 `exclusive_rights.xlsx`를 반환한다. Sheet name은 `배타적사용권`이며 컬럼 순서는 `배타적사용권 ID`, `업종`, `보험회사`, `상품/특약/제도명`, `배타적사용권 기간 개월 수`, `획득년월`, `주요 특징`, `대표 기사 제목`, `대표 기사 URL`, `alias 목록`, `근거문장`이다.
### POST /api/admin/product-consolidation/llm-review

Runs optional list-level LLM review for product consolidation blocks.

Request:

```json
{
  "mode": "dry_run",
  "target": "all",
  "limit": 1000,
  "max_blocks": 20
}
```

Response:

```json
{
  "job_id": null,
  "block_count": 8,
  "llm_call_count": 3,
  "auto_apply_count": 12,
  "review_count": 4,
  "estimated_cost_usd": 0.25,
  "plan_file": "data/exports/product_llm_merge_plan.csv"
}
```

`mode=dry_run` writes a CSV plan and does not mutate the DB. `mode=apply`
applies only validator-approved merge groups. The endpoint is disabled unless
`PRODUCT_LLM_CONSOLIDATION_ENABLED=true`.


### Dashboard filter semantics

Dashboard filter arrays use an empty list to mean "no filter" for that dimension. `release_years=[]` means all release years, `company_names=[]` means all companies in the selected insurance type or all companies when insurance type is all, and `product_type_codes=[]` means all product type groups. When `product_type_codes` is not empty, the product type filter is always applied independently of insurance type and company selection. With `classification_mode="include_secondary"`, both `primary_product_type_code` and secondary `fact_product_type_assignment` rows are searched. `/api/dashboard/query` and `/api/dashboard/export` use the same product selection logic.

## Multi-Company Article Default Exclusion

Default product and exclusive-use-right APIs exclude records derived only from articles flagged with `fact_article.multi_company_article_yn=true`.

- `/api/dashboard/query`, `/api/dashboard/export`, product search, and monthly new-product boards keep canonical products with non-multi-company evidence and exclude only multi-company source records from counts, aliases, related articles, coverage, narrative, and sales aggregations.
- `/api/exclusive-rights`, `/api/exclusive-rights/export`, and `/api/dashboard/recent-exclusive-rights` exclude `event_status in ('merged', 'rejected', 'rejected_multi_company_only')` and require non-multi-company article evidence for linked events.
- Raw article records are not removed. Admin/debug tooling can inspect flagged source articles separately.
