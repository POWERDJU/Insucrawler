## Crawl and consolidation guardrails

Collection and LLM extraction remain separate operations. Crawl jobs should default to `include_llm_extraction=false`; enabling extraction only processes candidate articles after screening.

After a crawl job completes, product consolidation can be triggered as a separate `ProductConsolidationJob`. The default automatic mode is `rule_only_apply` with `PRODUCT_CONSOLIDATION_LLM_ENABLED=false`, so consolidation first applies deterministic blocking and merge rules without calling an LLM. Gray-block LLM review is an explicit administrator option and is never run during article extraction, dashboard query, or Excel export.

Backfill LLM processing should still follow the low-cost route: screening first, snippet-only input, product candidate clusters, risky verification only, cache lookup before provider calls, and Batch API for eligible large jobs.

`extraction_mode` controls what happens after collection:

- `none`: collection only.
- `screening_only`: screen crawl-job articles only.
- `enqueue_only`: create extract queues for crawl-job candidates only; providers are not called.
- `batch`: create batch-eligible extract queues for crawl-job candidates only.
- `realtime`: call providers immediately, scoped to the crawl job id. Use only for small tests.

Backfill should use `enqueue_only` or `batch`. Realtime extraction no longer processes all pending articles globally; it is limited to the current `crawl_job_id`.
CLI helpers follow the same guardrail: `extract_pending_articles.py`, `extract_crawl_job_articles.py`, and `reprocess_collected_articles.py` default to queue-oriented modes unless `--extraction-mode realtime` is explicitly selected. Weekly jobs can set `WEEKLY_UPDATE_EXTRACTION_MODE`.

Before trusting a product backfill/export after consolidation changes, run the
version/birth/mobile regression gate:

```powershell
python scripts/run_product_version_birth_mobile_goal_check.py
```

It verifies version-aware Signature Women consolidation, birth-benefit component
consolidation, version-compatible release-month selection, and shared PC/mobile
coverage dedupe without crawling, reparsing, or calling Gemini/Qwen.

# Batch Operation

뉴스 수집 배치는 `CrawlJobService`를 공통 실행 경로로 사용한다. 관리자 API, 관리자 화면, CLI 스크립트가 같은 job/task/event 테이블을 사용하므로 어느 경로로 실행해도 진행률과 오류를 같은 방식으로 확인할 수 있다.

## Backfill 전략

2024-01-01 ~ 2026-05-31 전체 적재는 `backfill_2024_2026_05` job으로 실행한다. 기간을 월별로 나누고, 각 월마다 공통 검색어와 회사별 검색어를 생성한다. 네이버 뉴스 검색 API에는 공식 기간 파라미터가 없으므로 API 응답의 `pubDate`를 파싱해 해당 월에 속하는 기사만 저장한다.

월 키워드는 자동으로 사용하지 않는다. 네이버 뉴스 검색 API에는 공식 기간 파라미터가 없지만, `2026년 1월` 같은 표현을 query에 붙이면 해당 표현이 제목/본문에 없는 신상품 기사가 누락될 수 있다. 따라서 월별 Backfill의 기간 조건은 query 문자열이 아니라 API 응답의 `pubDate` 후처리로만 적용한다.

```env
CRAWL_USE_MONTH_KEYWORD=false
```

자동 생성 검색어 예: `메리츠화재 신상품`, `메리츠화재 건강보험 출시`, `암보험 출시`

월 키워드가 포함된 검색은 관리자 진단용 preview에서 수동으로 입력할 때만 허용한다. 이 경우에도 자동 수집 task로 저장되지는 않는다.

## 증분 업데이트 전략

주간 업데이트는 기본 최근 14일을 수집한다.

```env
WEEKLY_UPDATE_DAYS_BACK=14
```

관리자 화면에서는 최근 7일, 14일, 30일 중 선택할 수 있다. 증분 업데이트는 `sort=date`를 사용하고, 저장 시점에는 동일하게 `pubDate` 범위 필터와 중복 제거를 적용한다. 증분 업데이트 query에도 날짜 문자열을 붙이지 않는다.

## 작업 상태 관리

상위 job은 `fact_crawl_job`, 세부 task는 `fact_crawl_task`, 이벤트는 `fact_crawl_event_log`에 저장된다.

주요 상태:

- `pending`: 생성됨
- `running`: 실행 중
- `completed`: 모든 task 완료
- `failed`: 하나 이상의 task 실패
- `cancelled`: 관리자가 취소 요청

관리자 화면과 `GET /api/admin/crawl-jobs/{id}`에서 `total_tasks`, `completed_tasks`, `failed_tasks`, `total_api_calls`, `total_items_fetched`, `total_articles_saved`, `total_articles_duplicated`, `total_articles_out_of_range`를 확인한다.

## 재실행과 중복 제거

수집은 재실행 가능해야 한다. 같은 기사가 다시 발견되면 `FactArticle.content_hash`로 중복을 막고 task의 `articles_duplicated`를 증가시킨다.

중복 기준:

1. `original_url`
2. `link`
3. `title + pubDate + publisher`

실패 task는 `POST /api/admin/crawl-jobs/{id}/retry-failed`로 다시 pending 상태로 바꾼 뒤 재실행한다.

## Rate Limit

```env
NAVER_NEWS_DISPLAY=100
NAVER_NEWS_MAX_START=1000
CRAWL_API_SLEEP_SECONDS=0.2
CRAWL_MAX_API_CALLS_PER_JOB=5000
CRAWL_MAX_API_CALLS_PER_DAY=20000
```

`display`는 최대 100, `start`는 1~1000 범위에서 호출한다. 한 페이지의 모든 기사가 수집 범위보다 오래된 경우 조기 중단할 수 있다. 기간 판정은 query 문구가 아니라 `pubDate` 파싱 결과로 한다.

```env
CRAWL_STOP_WHEN_OLDER_THAN_RANGE=true
```

## 관리자 화면

대시보드에서 `관리자 업데이트`를 열고 `ADMIN_BATCH_PASSWORD`로 인증한다. 인증 후 다음 작업을 실행할 수 있다.

- 2026년 1월 테스트 수집
- 2024~2026년 5월 전체 수집
- 최근 뉴스 업데이트
- 직접 기간 수집

LLM 추출은 기본 꺼짐이며, 체크박스를 켠 경우 이번 crawl job에서 신규 저장된 pending 기사만 대상으로 추출을 시도한다.

배타적사용권은 별도 후처리 옵션으로 연결할 수 있다. `크롤링 후 배타적사용권 Batch 준비`를 켜면 crawl job 완료 후 해당 job 기사만 대상으로 `screening_only`, `enqueue_only`, `batch`, `realtime` 중 선택한 모드를 실행한다. 기본 권장값은 `batch`이며 `Batch 자동 제출`은 기본 OFF다. 이 경로는 실시간 Gemini 호출을 하지 않고 `exclusive_right_extract` queue와 Batch job 준비까지만 자동화하므로, 운영자가 job 상세에서 후보 수, queue 수, batch id, import/consolidation 상태를 확인한 뒤 제출할 수 있다.

## Windows 작업 스케줄러

- 프로그램: `python`
- 인수: `scripts/run_weekly_update.py`
- 시작 위치: repo root
- 주기: 매주 월요일 오전 7시

## cron

```bash
0 7 * * 1 cd /path/to/repo && /path/to/python scripts/run_weekly_update.py >> data/logs/weekly_update.log 2>&1
```

## 장애 대응

1. 관리자 화면에서 실패 job을 연다.
2. 실패 task의 `last_error`와 event log를 확인한다.
3. API key, 네트워크, rate limit, 검색어 폭증 여부를 점검한다.
4. `retry-failed`로 실패 task만 재시도한다.
5. 같은 기간 전체를 다시 실행해도 중복 기사는 저장되지 않는다.

## LLM 비용절감 백필

백필에서는 수집과 LLM 추출을 분리한다. 먼저 기사 수집과 `fact_content_screening` 저장을 완료하고, `high`/`medium` 후보만 `fact_llm_queue`에 올린다. `low`/`skip` 기사는 기본적으로 LLM을 호출하지 않는다.

LLM 입력은 기사 전문이 아니라 `fact_article_snippet`의 근거문장 bundle을 사용한다. 같은 상품으로 보이는 기사들은 `fact_product_candidate_cluster`로 묶고, cluster 단위로 1회 추출하는 것을 기본 정책으로 한다.

백필 추출은 `BATCH_LLM_FOR_BACKFILL=true`일 때 batch eligible queue를 JSONL로 export해 Gemini Batch API에 제출할 수 있다. 실시간 관리자 소량 테스트는 일반 generateContent 경로를 유지한다.

권장 기본값:

```env
LLM_EXTRACT_ONLY_CANDIDATES=true
LLM_VERIFY_ONLY_RISKY=true
LLM_SKIP_LOW_RELEVANCE=true
LLM_USE_SNIPPETS_ONLY=true
ENABLE_PRODUCT_CLUSTER_EXTRACTION=true
ENABLE_GEMINI_BATCH=true
BATCH_LLM_FOR_BACKFILL=true
GEMINI_BATCH_MODEL=gemini-2.5-flash
LLM_BATCH_MAX_REQUESTS=1000
LLM_BATCH_OUTPUT_DIR=data/llm_batches
ENABLE_GEMINI_GROUNDING=false
```

비용과 cache hit은 `GET /api/admin/llm-cost-summary` 또는 관리자 패널의 LLM 비용 요약에서 확인한다.

## Gemini Batch API 운영 흐름

Gemini Batch API는 대량 요청을 비동기로 처리하며, input file 방식은 JSONL 각 줄에 `key`와 `request`를 담는다. 시스템은 `llm_queue_id`를 `key`로 사용한다.

1. `POST /api/admin/llm-batch-jobs/create`
   - `batch_eligible_yn=true`, `status=pending` queue를 모아 `data/llm_batches/llm_batch_{id}.jsonl`을 생성한다.
   - `submit=true`이면 Gemini File API에 JSONL을 업로드하고 `models/{model}:batchGenerateContent`로 제출한다.
   - 반환된 `batches/...` 값을 `fact_llm_batch_job.provider_batch_id`에 저장한다.

2. `POST /api/admin/llm-batch-jobs/{id}/refresh-status`
   - `provider_batch_id`로 provider 상태를 조회하고 `provider_status`를 갱신한다.
   - `JOB_STATE_SUCCEEDED`, `JOB_STATE_FAILED`, `JOB_STATE_CANCELLED`, `JOB_STATE_EXPIRED`는 terminal 상태로 취급한다.

3. `POST /api/admin/llm-batch-jobs/{id}/import-results`
   - 완료된 batch의 output file을 다운로드하거나 기존 `output_file_path`를 읽는다.
   - 각 JSONL line의 `key`로 원래 queue를 찾고, response text를 extraction schema로 검증한다.
   - 성공 건은 `ExtractService.save_extraction_result`를 재사용해 상품 DB에 반영한다.
   - 실패 건은 queue `status=failed`, `last_error`에 오류를 남긴다.
   - 같은 output을 다시 import해도 기존 `llm_queue_id + llm_batch_job_id` run이 있으면 건너뛰므로 비용 로그와 상품 저장이 중복되지 않는다.

Batch import 성공 run은 `fact_llm_run.batch_yn=true`로 저장되고, `fact_llm_cost_log.batch_yn=true` 비용 로그가 생성된다. `config/llm_pricing.yaml`의 `batch_discount_rate`가 적용된다.

## 배타적사용권 수집과 추출

배타적사용권 기사 수집은 일반 상품 뉴스 수집과 같은 crawl job/task 구조를 사용한다. Query generator는 `exclusive_right_common`, `exclusive_right_company` query group을 생성하며, 월 키워드는 자동 추가하지 않는다. 기간 필터는 `pubDate` 후처리로만 적용한다.

운영 흐름:

1. 일반 crawl job을 실행해 배타적사용권 검색어 기사까지 수집한다. 또는 crawl job 요청에 `include_exclusive_right_pipeline=true`를 설정해 완료 후 배타적사용권 pipeline을 자동 연결한다.
2. `ScreeningService`가 `exclusive_right_score`와 `exclusive_right_candidate_yn`을 저장한다.
3. 관리자 화면의 `배타적사용권 추출` 또는 crawl job 후처리 옵션에서 `none`, `screening_only`, `enqueue_only`, `batch`, `realtime` 중 하나를 선택한다.
4. `screening_only`는 후보 여부만 저장하고 queue/provider 호출을 하지 않는다.
5. `enqueue_only`는 `task_type='exclusive_right_extract'` queue만 만든다.
6. `batch`는 `batch_eligible_yn=true` queue를 만들고, `LLM Batch 작업`에서 task를 `exclusive_right_extract`로 선택해 제출한다.
7. `realtime`은 `EXCLUSIVE_RIGHT_REALTIME_LIMIT` 이내 소량 진단용이며, exclusive snippet bundle만 사용한다.

Crawl job 연동 필드:

- `include_exclusive_right_pipeline`: crawl 완료 후 배타적사용권 후처리를 실행할지 여부
- `exclusive_right_pipeline_mode`: `none`, `screening_only`, `enqueue_only`, `batch`, `realtime`
- `exclusive_right_auto_submit_batch`: Batch job 생성 후 즉시 provider에 제출할지 여부
- `exclusive_right_auto_import_when_completed`: provider completed 상태 확인 시 output import까지 이어갈지 여부
- `exclusive_right_auto_consolidate`: import 또는 realtime 저장 후 rule-only 통합 실행 여부
- `exclusive_right_limit`: 후처리 대상 상한

상태는 `GET /api/admin/crawl-jobs/{crawl_job_id}`의 `exclusive_right_pipeline_status`, `exclusive_right_candidate_count`, `exclusive_right_queue_created_count`, `exclusive_right_batch_job_id`, `exclusive_right_batch_status`, `exclusive_right_imported_count`, `exclusive_right_canonical_count`로 추적한다.

Queue 상태는 `GET /api/admin/exclusive-rights/extract-queue-status` 또는 아래 CLI로 확인한다.

```bash
python scripts/list_exclusive_right_queue.py --date-from 2026-01-01 --date-to 2026-01-31
```

2026년 1월 배타적사용권 테스트 실행 예:

```bash
python scripts/run_exclusive_right_batch.py --date-from 2026-01-01 --date-to 2026-01-31 --mode enqueue_only --limit 100
python scripts/run_exclusive_right_batch.py --date-from 2026-01-01 --date-to 2026-01-31 --mode batch --limit 100 --create-batch
python scripts/run_crawl_with_exclusive_batch.py --date-from 2026-01-01 --date-to 2026-01-31 --exclusive-mode batch
```

전체 데이터 배치 전에는 반드시 GO/NO-GO 체크를 먼저 실행한다.

```bash
python scripts/pre_full_batch_go_check.py
```

`GO`가 아닌 경우에는 `failed_checks`에 나온 항목을 수정한 뒤 다시 실행한다. 이 체크는 배타적사용권 키워드, local context 선택, weak subject validation, type master 제거, 화면/Excel 컬럼 단순화, LLM 비용절감 기본값을 정적으로 확인하며 외부 API나 LLM provider를 호출하지 않는다.

Batch JSONL은 `custom_id=exclusive_right_extract:queue:{queue_id}:article:{article_id}:crawl:{crawl_job_id}`를 포함한다. 결과 import는 `ExclusiveRightService.save_extraction_result()` 공통 경로를 사용해 schema validation, company normalization, observation/canonical upsert, article mapping, alias 저장을 수행한다. `applied_or_planned`는 active canonical으로 확정하지 않고 review observation으로만 남긴다.

중복기사/유사 subject 통합은 `ExclusiveRightConsolidationService`에서 rule 기반으로 수행한다. 같은 회사, 같은/유사 subject, 가까운 획득월, 같은 기간, 호환 가능한 type은 canonical event 하나로 병합하고, 기간 충돌은 review로 둔다.
## 배타적사용권 Batch 결과 조회 흐름

배타적사용권 batch pipeline에서 import된 canonical event는 `GET /api/dashboard/recent-exclusive-rights`, `GET /api/exclusive-rights`, `POST /api/exclusive-rights/export`에 즉시 반영된다. 현황판과 조회목록은 추가 LLM 호출을 하지 않고 저장된 canonical event, observation, article mapping, alias 데이터를 사용한다.

운영자는 크롤링 후 `screening_only`, `enqueue_only`, `batch`, `realtime` 중 하나로 배타적사용권 pipeline을 실행할 수 있다. 대량 작업의 기본 권장은 `batch`이며, import 후 rule-only consolidation을 수행하면 중복 기사나 유사 subject명이 canonical event 하나로 정리되어 현황판과 Excel에는 merged event가 기본 표시되지 않는다.

배타적사용권 canonical event는 단순 스키마를 사용한다. 원문 회사명, 구분, subject type, 기간 원문, 획득년월 basis는 저장/Export하지 않는다. 획득년월은 명시월이 있으면 기사 게재일 기준으로 해석하고, 명시월이 없으면 관련기사 중 최초 게재월을 사용한다. 여러 회사/상품이 섞인 기사에서는 제목이 아니라 배타적사용권 키워드가 있는 local window를 기준으로 회사와 subject를 귀속한다.

기존 데이터 재정리는 LLM 없이 deterministic rebuild로 수행한다.

```bash
python scripts/rebuild_exclusive_rights.py --dry-run
python scripts/rebuild_exclusive_rights.py --apply
```

Dry-run은 `data/exports/exclusive_right_rebuild_plan.csv`에 병합/거절 후보를 출력한다. “해당 상품”, “이번 상품”, “신상품” 같은 weak subject는 canonical event로 유지하지 않고, local context에서 실제 subject를 찾지 못하면 review/rejected로 남긴다.
## Exclusive Right Consolidation Goal Check

배타적사용권 batch import 또는 기존 데이터 rebuild 후에는 다음 deterministic goal-check를 실행해 중복 통합 품질을 확인한다.

```powershell
python scripts/run_exclusive_right_consolidation_goal_check.py
```

이 스크립트는 임시 DB에 교보생명 여성건강보험특약 계열과 한화손해보험 법률비용/변호사 상담 서비스 계열 회귀 데이터를 넣고, `ExclusiveRightDuplicateGuardService`와 `ExclusiveRightConsolidationService`가 rule-only로 중복을 제거하는지 확인한다. 성공 시 `docs/exclusive-right-consolidation-goal-result.md`에 `GOAL status = PASS`를 남긴다.

이 점검은 Naver/Gemini/Qwen API를 호출하지 않는다. Excel export와 화면 렌더링 중에도 LLM을 호출하지 않는다는 비용 절감 원칙을 함께 검증한다.

## Company Attribution in Batch Pipelines

Batch import uses the same save paths as realtime extraction. Product and exclusive-right rows are attributed by local evidence windows through `CompanyAttributionService`; the batch pipeline does not trust the first company in the article title or a short alias alone. Rebuild scripts are deterministic and can be run after import without re-crawling or calling LLM providers.

```powershell
python scripts/run_company_attribution_goal_check.py
```
