## Runtime execution guard

The optimized pipeline is enforced in the runtime path, not only documented as an operating recommendation.

- Article extraction must not create `product_consolidation` LLM runs.
- Screening is required before extraction. `low` and `skip` results do not create extract/verify/adjudicate queues.
- When `LLM_USE_SNIPPETS_ONLY=true`, prompt input is built from title, description fallback, and `fact_article_snippet` bundles. Full article body is excluded by default.
- When `ENABLE_PRODUCT_CLUSTER_EXTRACTION=true`, cluster extraction is preferred and an already extracted cluster only links additional articles.
- When `LLM_VERIFY_ONLY_RISKY=true`, verification is skipped unless sales metrics, maximum coverage amount, uncertain release month, correction/conflict, or review signals are present.
- `ProductConsolidationJob` owns global same-product judgment. LLM gray-block review is disabled by default and, when enabled, is block-level only.
- Extract, verify, and product-consolidation LLM paths must check `fact_llm_response_cache` before provider calls and write `fact_llm_run`/`fact_llm_cost_log` afterward.
- Crawl jobs separate collection and LLM work with `extraction_mode`: `none`, `screening_only`, `enqueue_only`, `realtime`, or `batch`. Backfill should use `enqueue_only` or `batch`; `realtime` is for small manual tests only.
- CLI helpers use the same modes. `extract_pending_articles.py`, `extract_crawl_job_articles.py`, and `reprocess_collected_articles.py` default to queue-oriented execution; realtime provider calls require `--extraction-mode realtime`.

Administrators can audit policy health with:

```http
GET /api/admin/llm-execution-guard-summary
```

Key violation counters are `low_skip_llm_violation_count`, `article_level_same_product_llm_violation_count`, and `full_body_prompt_violation_count`.

`enqueue_only` creates `fact_llm_queue` records for the specific crawl job without provider calls. `batch` does the same and marks queues `batch_eligible_yn=true` so `BatchLLMService` can submit them to Gemini Batch API. Realtime extraction is scoped to the crawl job id and must not process unrelated pending articles.

# LLM Cost Optimization

## 목적

뉴스/블로그 수집량이 커질수록 모든 기사에 Gemini/Qwen을 호출하면 비용이 급격히 증가한다. 이 시스템은 LLM 호출 전 deterministic screening과 snippet extraction을 수행하고, 같은 상품 후보를 cluster로 묶어 LLM 호출량과 입력 토큰을 줄인다.

## 처리 흐름

1. 수집 및 중복 제거
2. 룰 기반 screening
3. 근거문장 snippet 추출
4. 상품 후보 cluster 생성
5. LLM queue 생성
6. 후보 cluster 또는 후보 article만 1차 추출
7. 위험 건만 2차 검증
8. cache/cost log 저장

## Screening

`ScreeningService`는 기사 제목, 요약, 본문 일부를 보고 관련성 점수를 계산한다.

- 보험회사 master/alias 발견: 가점
- 상품군 키워드 발견: 가점
- 출시/신상품 키워드 발견: 가점
- 보장/판매실적 키워드 발견: 가점
- 인사/채용/사회공헌/주가/배당/캠페인 등 상품 무관 키워드: 감점

결과는 `fact_content_screening`에 저장된다.

- `high`: LLM 추출 대상
- `medium`: 저비용 추출 또는 batch 대상
- `low`: 기본 skip
- `skip`: LLM 호출 금지

## Snippet Only 입력

기사 전문은 기본적으로 LLM에 넣지 않는다. `SnippetService`가 출시, 상품명, 보장, 판매실적, 채널, 마케팅, 언더라이팅 문장을 추출하고 `fact_article_snippet`에 저장한다.

기본 환경변수:

```env
LLM_USE_SNIPPETS_ONLY=true
SNIPPET_CONTEXT_SENTENCES=1
MAX_SNIPPET_CHARS_PER_ARTICLE=3000
LLM_MAX_INPUT_CHARS=6000
```

## Product Candidate Cluster

`FactProductCandidateCluster`는 같은 상품으로 보이는 여러 기사들을 묶는다.

기본 기준:

- `company_id + product_core_key`가 같으면 같은 cluster
- 회사가 다르면 같은 product_core_key라도 분리
- launch 문장에서 나온 상품명을 우선 사용
- 상품명이 없으면 title launch pattern으로 보조 후보 생성

LLM 입력은 cluster의 대표 기사와 snippet만 포함한다.

```env
ENABLE_PRODUCT_CLUSTER_EXTRACTION=true
MAX_ARTICLES_PER_CLUSTER_FOR_LLM=5
MAX_CLUSTER_SNIPPET_CHARS=5000
```

## LLM Queue

`fact_llm_queue`는 실행 대상을 저장한다.

- `target_type`: article, product_candidate_cluster, product
- `task_type`: cheap_classify, extract, verify, adjudicate
- `priority`: high, medium, low, skip
- `batch_eligible_yn`: backfill batch 처리 가능 여부

low/skip screening 결과에는 queue를 만들지 않는다.

## 선택적 검증

검증은 비용이 큰 작업이므로 기본적으로 위험 건에만 수행한다.

위험 신호:

- 판매실적 존재
- 최대보장금액 존재
- 출시월 불명확
- 상품명 negative pattern 보정
- company normalizer와 LLM 후보 충돌
- 홍보성 블로그 고위험

```env
LLM_VERIFY_ONLY_RISKY=true
ENABLE_GEMINI_GROUNDING=false
GROUNDING_ONLY_ON_CONFLICT=true
```

## Cache

`fact_llm_response_cache`는 input hash, prompt version, schema version, provider, model, task type 조합으로 LLM 응답을 저장한다. 동일 입력은 LLM을 다시 호출하지 않고 cache를 사용한다. cache hit은 `fact_llm_run.cached_yn=true`로 기록한다.

## 비용 로그

`fact_llm_cost_log`에는 provider, model, task type, token 수, cache/batch 여부, estimated cost, estimate quality를 저장한다. 가격표는 `config/llm_pricing.yaml`에서 관리한다. 실제 모델 가격은 변동될 수 있으므로 운영 전 공식 가격표를 확인해 업데이트한다.

관리자 API:

```http
GET /api/admin/llm-cost-summary
```

응답에는 총 예상 비용, 모델별 비용, task_type별 비용, cache hit rate, batch request count, token 합계, run count가 포함된다.

## 비용절감 측정

`GET /api/admin/llm-cost-savings-summary`는 최적화가 없었을 때의 baseline 비용과 현재 실제 비용을 비교한다.

기본 공식:

```text
estimated_savings_usd = baseline_estimated_cost_usd - optimized_actual_cost_usd
estimated_savings_rate = 1 - optimized_actual_cost_usd / baseline_estimated_cost_usd
```

지원 baseline policy:

- `all_articles_fulltext_extract_only`: 모든 수집 기사에 full text extract 1회
- `all_articles_fulltext_extract_and_verify`: 모든 수집 기사에 full text extract 1회 + verify 1회
- `candidate_articles_fulltext_extract_only`: screening 후보 기사에 full text extract 1회
- `candidate_articles_fulltext_extract_and_verify`: screening 후보 기사에 full text extract 1회 + verify 1회

절감 기여도는 다음 항목으로 분해한다.

- `screening_saved_usd`: low/skip 기사에 queue를 만들지 않아 줄어든 호출
- `snippet_saved_usd`: full text 대신 snippet 입력을 사용해 줄어든 input token
- `cluster_saved_usd`: article 단위 호출 대신 product candidate cluster 단위 호출을 사용해 줄어든 호출
- `selective_verification_saved_usd`: 모든 건 verify 대신 위험 건만 검증해 줄어든 호출
- `cache_saved_usd`: 동일 input/prompt/schema/model 조합을 cache로 재사용한 절감
- `batch_saved_usd`: batch discount를 적용한 절감

`estimate_quality`는 다음 의미다.

- `actual_tokens`: provider usage metadata 또는 명시 token으로 계산
- `mixed`: input/output 중 일부는 실제 token, 일부는 rough estimate
- `rough`: 실제 token이 없어 입력 텍스트 길이로 추정
- `missing_price`: `config/llm_pricing.yaml`에 provider/model 가격이 없어 비용 신뢰도가 낮음

주의: token이 없을 때 `input_hash`로 token을 추정하면 비용이 과소평가되므로 사용하지 않는다. 원문 전문이 저장되어 있지 않으면 title+description 또는 snippet text를 기준으로 rough estimate를 계산한다.

## Batch 전략

백필처럼 즉시 응답이 필요 없는 대량 추출은 `BatchLLMService`로 JSONL input을 만든 뒤 Gemini Batch API에 제출한다. 실시간 관리자 소량 테스트는 기존 generateContent 경로를 유지하고, 대량 백필 추출만 batch eligible queue를 묶어 처리한다.

기본 흐름:

1. `fact_llm_queue.batch_eligible_yn=true`이고 `status=pending`인 extract queue를 조회한다.
2. queue별 snippet bundle 또는 cluster 대표 입력을 Gemini Batch JSONL로 export한다.
3. `GeminiBatchAdapter`가 File API에 JSONL을 업로드한 뒤 `batchGenerateContent` 작업을 제출한다.
4. provider가 반환한 batch id를 `fact_llm_batch_job.provider_batch_id`에 저장한다.
5. 상태 조회 결과는 `provider_status`, `completed_count`, `failed_count`에 반영한다.
6. 완료 output을 다운로드하거나 로컬 output JSONL을 읽어 기존 extraction schema로 validation한다.
7. `ExtractService.save_extraction_result`를 재사용해 상품, 보장, 기사 연결 데이터를 저장한다.
8. queue는 성공/실패별로 `completed` 또는 `failed`가 되고, 실패 output은 `last_error`에 원인을 남긴다.
9. `fact_llm_run.batch_yn=true`, `fact_llm_cost_log.batch_yn=true`로 기록해 batch 할인 비용을 계산한다.

같은 output을 두 번 import해도 동일 batch job과 queue 조합의 성공 run이 이미 있으면 다시 저장하지 않는다. batch 제출 실패 시 원본 queue는 삭제하지 않으며, 상태를 확인한 뒤 재제출 또는 새 batch job 생성으로 복구한다.

주요 환경변수:

```env
ENABLE_GEMINI_BATCH=true
BATCH_LLM_FOR_BACKFILL=true
GEMINI_BATCH_MODEL=gemini-2.5-flash
LLM_BATCH_MAX_REQUESTS=1000
LLM_BATCH_OUTPUT_DIR=data/llm_batches
```

가격표는 `config/llm_pricing.yaml`에서 모델별 `batch_discount_rate`로 관리한다. 실제 청구 기준은 Google AI Studio/Gemini API 공식 가격표가 바뀔 수 있으므로 운영 전 최신 가격을 확인한다.

## Product Consolidation LLM Policy

상품 동일성 판단은 기사별 추출 단계에서 실행하지 않는다. 기사별 LLM은 상품명 후보, 회사 후보, 상품군, 보장, 요약, 근거문장을 추출하는 역할만 하며, 기존 DB 전체 상품과 비교하지 않는다.

전역 동일상품 판단은 `ProductConsolidationJob`에서 수행한다. 이 job은 먼저 deterministic blocking으로 같은 회사, 같은 제휴/파트너 맥락, 유사 상품명, 호환 가능한 상품군, 가까운 출시월 후보만 묶는다. 그 다음 동일 `product_core_key`, same-article weak mention, high similarity, containment 같은 rule merge를 LLM 없이 적용한다.

LLM은 다음 조건을 만족하는 gray block에만 선택적으로 사용한다.

- block 안 후보가 2개 이상이다.
- known company가 서로 다르지 않다.
- 상품군과 출시월, version signature가 명확히 충돌하지 않는다.
- deterministic rule로 자동 병합도 자동 제외도 되지 않았다.
- `PRODUCT_CONSOLIDATION_LLM_ENABLED=true`, 관리자 요청의 `use_llm_for_gray_blocks=true`, job별 호출/비용 예산을 모두 만족한다.

금지 정책:

- 기사 1건 저장 중 same-product LLM 호출 금지.
- 모든 상품쌍 pairwise LLM 비교 금지.
- 조회/Excel 다운로드 중 실시간 병합 LLM 호출 금지.
- article full text를 product consolidation judge 입력으로 사용 금지.

관련 환경변수:

```env
PRODUCT_CONSOLIDATION_AUTO_AFTER_CRAWL=true
PRODUCT_CONSOLIDATION_AUTO_MODE=rule_only_apply
PRODUCT_CONSOLIDATION_BATCH_SIZE=100
PRODUCT_CONSOLIDATION_LLM_ENABLED=false
PRODUCT_CONSOLIDATION_LLM_MAX_CALLS_PER_JOB=10
PRODUCT_CONSOLIDATION_LLM_MAX_COST_USD_PER_JOB=1.0
PRODUCT_CONSOLIDATION_LLM_MAX_BLOCK_SIZE=20
PRODUCT_CONSOLIDATION_LLM_MAX_INPUT_CHARS=2500
```

이 구조는 상품 후보 N개를 전부 pairwise 비교하는 비용을 피하고, 실제 LLM 호출을 rule로 판단하기 어려운 소수 block으로 제한한다. 동일 block judge 결과는 LLM cache에 저장해 같은 후보 묶음에 대한 반복 호출을 피한다.

참고:

- Gemini Batch API: https://ai.google.dev/gemini-api/docs/batch-api
- Gemini API pricing: https://ai.google.dev/gemini-api/docs/pricing

## Exclusive Use Rights Cost Policy

배타적사용권 추출도 동일한 비용절감 원칙을 사용한다.

- 모든 기사에 LLM을 호출하지 않고 `exclusive_right_candidate_yn=true`인 기사만 대상이 된다.
- 상품 관련성이 `low/skip`이어도 배타적사용권 점수가 높으면 별도 `exclusive_right_extract` queue가 생성될 수 있다.
- LLM 입력은 `exclusive_right`, `exclusive_period`, `exclusive_acquired_date`, `exclusive_feature` snippet bundle과 title/description으로 제한한다.
- `enqueue_only`와 `batch` 모드는 provider를 즉시 호출하지 않는다.
- Batch 추출은 `fact_llm_queue.task_type='exclusive_right_extract'`와 `batch_eligible_yn=true` queue를 사용한다.
- `screening_only`는 후보 선별만 저장하고 queue를 만들지 않는다.
- Crawl job에서 `include_exclusive_right_pipeline=true`를 사용하면 완료 hook이 해당 `crawl_job_id` 기사만 대상으로 screening/queue/batch 준비를 실행한다.
- Batch JSONL은 `exclusive_right_extract:queue:{queue_id}:article:{article_id}:crawl:{crawl_job_id}` custom id를 포함해 import 시 원래 queue/article/crawl job으로 돌아간다.
- Batch import는 `ExclusiveRightService.save_extraction_result()`를 사용한다. `acquired`만 canonical event로 저장하고, `applied_or_planned`는 review observation으로 보관한다.
- 같은 output을 다시 import해도 canonical, observation, article mapping, alias를 중복 생성하지 않는다.
- `exclusive_right_auto_submit_batch=false`가 기본이므로 batch 준비와 provider 제출은 분리된다. `exclusive_right_auto_import_when_completed=true`를 켠 job만 provider completed refresh 이후 output import까지 자동 시도한다.
- verify와 consolidation은 위험/충돌 block에만 확장할 수 있으며, grounding은 기본 OFF다.
- 중복기사와 유사 subject명 병합은 rule 우선이며, LLM consolidation은 gray block에만 선택적으로 사용할 수 있다.

이 정책 때문에 배타적사용권 수집량이 늘어도 기본 경로에서는 screening/snippet/queue/batch를 거치며, 실시간 LLM 호출은 관리자가 명시적으로 선택한 소량 작업에 한정된다.

배타적사용권 재통합과 품질 보정은 기본적으로 deterministic이다. `scripts/rebuild_exclusive_rights.py`는 기존 event/observation/article/alias를 읽어 local context 기준 subject 귀속, weak subject 제거, 획득년월 재계산, rule-only consolidation을 수행하며 LLM을 호출하지 않는다. LLM은 향후 gray block 수동 검토 옵션에서만 제한적으로 사용할 수 있고, 현황판/조회/Excel export에서는 절대 호출하지 않는다.

전체 배치 전 `python scripts/pre_full_batch_go_check.py`를 실행하면 비용절감 기본값과 UI/export 단순화, 배타적사용권 parser guardrail을 정적으로 확인한다. 이 GO/NO-GO 체크 역시 외부 API와 LLM provider를 호출하지 않는다.

## Deterministic Product Attribution Guard

상품 회사 귀속 보정은 LLM을 추가 호출하지 않는다. `ProductAttributionGuardService`가 저장/import 직전에 local product window를 만들고, `CompanyAttributionService`로 회사 근거를 검증한다.

- query company, crawl task company, screening matched company는 검색/수집 메타데이터이며 최종 회사 fallback이 아니다.
- Batch output의 회사 후보가 local product window와 충돌하면 local company를 우선하고 review로 낮춘다.
- 멀티컴퍼니 기사는 queue 생성, Batch JSONL 생성, import 단계에서 모두 차단된다.
- TV 광고/캠페인-only 기사에서 generic product name만 나온 경우 active product를 만들지 않는다.
- 진단/재빌드/GOAL 스크립트는 deterministic이며 Gemini/Qwen/Naver API를 호출하지 않는다.

```powershell
python scripts/run_product_attribution_multicompany_marketing_goal_check.py
```
## List-Level LLM Consolidation

List-level consolidation is an optional administrator workflow for duplicate
product rows or duplicate exclusive-use-right rows that deterministic rules
cannot confidently resolve.

Cost guardrails:

- It is disabled by default:
  - `PRODUCT_LLM_CONSOLIDATION_ENABLED=false`
  - `EXCLUSIVE_RIGHT_LLM_CONSOLIDATION_ENABLED=false`
- It uses compact block payloads only. Full article bodies, Excel rows,
  dashboard data, and raw DB dumps are never sent.
- The LLM returns a merge plan only. It never mutates the DB directly.
- Deterministic validators reject cross-company merges, version conflicts,
  product type conflicts, exclusivity period conflicts, weak/generic canonical
  names, out-of-block ids, and confidence below `0.85`.
- Calls are block-level, not pairwise.
- `fact_llm_response_cache` is checked before provider calls.
- `LLM_CONSOLIDATION_MAX_CALLS_PER_JOB` and
  `LLM_CONSOLIDATION_MAX_COST_USD_PER_JOB` cap a run.

Product full-list consolidation uses the same isolation rule: it is an
administrator-only job and never runs during article extraction, dashboard
query, or Excel export. It groups products by insurer and sends compact product
rows only. The LLM returns a merge plan, and local validation applies only safe
same-company groups. Defaults:

- `PRODUCT_LLM_CONSOLIDATION_ENABLED=false`
- `PRODUCT_LLM_CONSOLIDATION_MAX_COMPANIES_PER_JOB=50`
- `PRODUCT_LLM_CONSOLIDATION_MAX_PRODUCTS_PER_PROMPT=60`
- `PRODUCT_LLM_CONSOLIDATION_MAX_CALLS_PER_JOB=30`
- `PRODUCT_LLM_CONSOLIDATION_MAX_COST_USD_PER_JOB=3.0`

`scripts/check_product_duplicates.py` and the Excel `duplicate_warnings` sheet
are deterministic read-only checks and do not call Gemini/Qwen.

Task types recorded in `fact_llm_run` and `fact_llm_cost_log`:

- `product_list_consolidation`
- `exclusive_right_list_consolidation`

This path is never invoked by article extraction, dashboard rendering, or Excel
export.

## Product Consolidation Execution Guard

Product entity resolution has a dedicated consolidation-only quality gate:

```powershell
python scripts/run_product_consolidation_goal_check.py
```

The gate verifies that rule-only consolidation clears the recurring Tontine,
Signature Women 4.0, and ABL health-refund duplicate families without crawling,
article reparsing, or provider calls. It also checks that ABL whole-body
anesthesia surgery insurance, Signature Women 3.0, and same-name products from
another insurer remain separate.

Allowed LLM task type for the optional fallback is only:

- `product_list_consolidation`

Disallowed paths remain:

- article-level same-product judging
- pairwise product comparison
- full article reparse for product merge
- dashboard/render-time consolidation
- Excel/export-time consolidation

Live smoke is opt-in only:

```powershell
set ENABLE_LIVE_LLM_CONSOLIDATION_TEST=true
python scripts/run_live_llm_product_consolidation_smoke.py
```

Without the opt-in flag and API key, the smoke script writes a skipped report and
does not call a provider.

## Exclusive Right Consolidation Execution Guard

Exclusive-use-right consolidation follows the same cost boundary. The default
path is deterministic component/context consolidation, not article re-extraction
and not render-time LLM.

```powershell
python scripts/run_exclusive_right_consolidation_goal_check.py
```

The goal check verifies that:

- Kyobo Life `여성건강보험특약` / `여성건강보험` variants become one canonical
  event and one Excel row.
- Hanwha General Insurance legal-cost / lawyer-consulting-service variants
  become one canonical event and one Excel row.
- Stronger canonical subjects win over product-name context such as
  `시그니처 여성보험 4.0`.
- `article-level LLM calls` and `export/render LLM calls` remain `0`.

The optional LLM task type for unresolved compact-list review is only:

- `exclusive_right_list_consolidation`

It is disabled by default and is never invoked by dashboard rendering, keyword
search, or Excel export.

## Company Attribution Cost Guard

Company attribution is deterministic and does not call Gemini/Qwen. Product save, product candidate clustering, exclusive-right save, and rebuild dry-run/apply all use the company dictionary plus local context windows. Article-level same-product LLM calls, export-time LLM calls, and render-time LLM calls remain disallowed.

Run the guard:

```powershell
python scripts/run_company_attribution_goal_check.py
```

## Multi-Company Article LLM Guard

Multi-company article filtering is deterministic and does not call Gemini/Qwen.

- Articles with two or more known insurer companies are flagged before extraction.
- Flagged articles do not create new realtime or batch LLM queues.
- If a flagged article is already in a submitted batch, import skips only that output.
- Source-level cleanup never calls LLM and never physically deletes canonical products/events.
