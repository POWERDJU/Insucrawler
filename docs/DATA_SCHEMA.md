# Data Schema

이 MVP는 4개 층을 분리한다: 정형화 데이터, 태그/분류 데이터, 비정형 서술형 인사이트, 근거 및 검증 데이터.

## Grain

- `dim_product`: product grain. 상품 1개당 1행.
- `fact_article`: article grain. 뉴스 API 결과 1건당 1행. 원문 전문은 기본 저장하지 않는다.
- `fact_product_article`: product-article bridge grain.
- `fact_product_major_coverage`: coverage grain. 상품의 주요보장 1개당 1행.
- `fact_sales_metric_structured`: sales metric grain. 상품의 명확한 실적 수치 1개당 1행.
- `fact_llm_run`: LLM 실행 1회당 1행.
- `fact_extraction_comparison`: extractor/verifier/adjudicator 비교 1건당 1행.
- `fact_extraction_field_audit`: field-level audit 1개당 1행.
- `fact_company_event`: 회사 사명변경/합병/가교이전 등 이벤트 1건당 1행.
- `fact_crawl_job`: 뉴스 수집 배치 job 1건당 1행.
- `fact_crawl_task`: 월/회사/검색어 단위 수집 task 1건당 1행.
- `fact_crawl_event_log`: 수집 job/task 이벤트 로그 1건당 1행.

## 핵심 테이블

요구 테이블 16개를 SQLAlchemy 모델로 구현한다.

- `dim_company`
- `dim_product`
- `dim_product_alias`
- `dim_product_type`
- `fact_product_type_assignment`
- `fact_article`
- `fact_product_article`
- `fact_product_structured_feature`
- `fact_product_narrative_insight`
- `fact_product_major_coverage`
- `fact_coverage_evidence`
- `fact_sales_metric_structured`
- `fact_manual_ingestion`
- `fact_extraction_raw_json`
- `fact_llm_run`
- `fact_extraction_comparison`
- `fact_extraction_field_audit`
- `fact_company_event`
- `fact_crawl_job`
- `fact_crawl_task`
- `fact_crawl_event_log`

## Company Master

`dim_company`는 2024~2026년 국내 생명보험/손해보험 상품 뉴스 분석을 위한 회사 마스터다. 현재 영업사, 사명변경 회사, 합병 회사, 가교보험사, 신규 소액단기보험사, 재보험사/외국지점을 함께 보존한다.

주요 컬럼:

- `company_name_normalized`: 표준 회사명. upsert 기준.
- `company_name_raw`: 수동 입력이나 기사에서 확인된 원문 회사명 후보.
- `alias`: pipe(`|`) 구분 alias. 예: `DGB생명|iM라이프`.
- `insurance_type`: `생명보험` 또는 `손해보험`.
- `company_role`: `life_primary`, `nonlife_primary`, `nonlife_digital`, `nonlife_bridge`, `short_term_pet_insurer`, `guarantee_insurer`, `foreign_primary`, `foreign_branch`, `reinsurer`, `reinsurer_or_foreign_branch`.
- `status_2024_2026`: `active`, `renamed`, `merged`, `transferred_to_bridge`, `bridge`, `new`, `exiting`, `unknown`.
- `include_in_product_news_default`: `Y`면 기본 상품 뉴스 피벗/검색 대상, `N`이면 재보험사/외국지점처럼 옵션을 켠 경우에만 포함.
- `predecessor_company`, `successor_company`, `notes`: 구 사명, 합병/승계 회사, 확인 필요 메모.
- `establishment_year`, `establishment_month`, `establishment_day`: 화면 표시순서에 쓰는 전신/모태 법인 설립일. 월/일을 모르면 null로 둔다.
- `establishment_sort_date`: 원천에서 확인한 설립일 문자열. `YYYY-MM-DD`, `YYYY-MM`, `YYYY` 중 가능한 정밀도로 저장한다.
- `establishment_basis`: 설립년도 기준. `predecessor`, `current_legal_entity`, `branch_entry`, `bridge_license`, `market_entry`, `unknown`을 사용한다.
- `oldest_predecessor_year`: 합병/인수 계보 중 가장 오래된 전신 설립년도.
- `current_brand_year`: 현재 사명 또는 현재 브랜드 출범년도. 표시 참고값이며 정렬에는 사용하지 않는다.
- `display_order_established`: 업권별 설립년도 표시순서의 명시적 tie-breaker. 이 값이 있으면 화면/API 회사 목록에서 우선 사용한다.
- `sort_tie_breaker`: 같은 설립년도 내 월/일이 불명확할 때 쓰는 보조 정렬값.
- `establishment_source_note`: 설립년도 판단 근거. 예: `조선화재해상보험 설립 기준`.

회사 표시순서는 사명변경년도나 현 브랜드 출범년도가 아니라 `display_order_established`, `establishment_year`, `establishment_month`, `establishment_day`, `sort_tie_breaker` 기준이다. 예를 들어 `iM라이프생명`은 `current_brand_year=2024`를 보존하지만 표시순서는 부산생명/DGB생명 계보의 `establishment_year=1988` 기준이다.

`dim_product.company_name_raw`는 상품 입력 시 사용된 원문 회사명을 보존하고, `dim_product.company_id`는 alias 정규화 후 표준 회사에 연결한다.

## Product Identity Normalization

`dim_product`에는 상품명 중복 생성을 줄이기 위한 식별 컬럼을 둔다.

- `product_core_key`: 회사명/회사 alias를 제거하고 공백과 장식 기호를 정규화한 상품명 핵심 key. `4.0`, `V2` 같은 버전 표기는 보존한다.
- `product_identity_key`: `company_id + product_core_key` 조합. 같은 회사의 같은 core key는 동일 상품으로 upsert한다.
- `release_year_month_source_article_id`: 출시년월을 관련 기사 최초 작성월로 보정한 경우 근거 기사 ID.
- `release_year_month_source_type`: 보정 근거 source type.
- `release_year_month_inferred_at`: 출시년월 보정 시각.

`dim_product_alias`는 상품명 관측값 테이블이다. `raw_product_name`, 사람이 보기 좋은 `normalized_product_name_candidate`, `product_core_key`, `company_id`, `article_id`, `source_type`, 최초/최종 관측 시각, 관측 횟수를 저장한다. 같은 상품이 기사마다 `한화손해보험 시그니처 여성건강 보험 4.0`, `한화손보 시그니처 여성건강보험 4.0`, `시그니처 여성건강보험 4.0`처럼 다르게 등장해도 하나의 `product_id`에 연결한다.

출시년월 기준값에는 `earliest_related_article_month`를 사용한다. 이는 명시 출시월이 없을 때 `fact_product_article`로 연결된 기사 중 가장 오래된 작성월을 사용했다는 뜻이다. `explicit_in_article`, `manual`, `external_grounded_source`는 이 보정으로 덮어쓰지 않는다.

회사명은 `dim_company` 또는 `company_dictionary.csv`에 등록된 표준명/alias만 확정한다. 지역농협, 지점, 지역본부, 대리점명 등 회사 마스터에 없는 조직명은 `company_id=null`, 검수필요 상태로 남기며 `dim_company`를 자동 생성하지 않는다.

`fact_company_event`는 이벤트 테이블로 준비되어 있으며, MVP에서는 핵심 이력은 `dim_company`의 predecessor/successor/notes에도 함께 저장한다.

## Crawl Job Tables

`fact_crawl_job`은 관리자 화면/CLI/주간 배치에서 생성되는 수집 작업의 상위 단위다. `job_type`은 `test_2026_01`, `backfill`, `incremental`, `manual_range`를 사용하고, `status`는 `pending`, `running`, `completed`, `failed`, `cancelled`, `paused`를 사용한다. 기간, 요청자, LLM 추출 옵션, 재보험/외국지점 포함 여부와 함께 task/기사/API 호출 집계값을 보존한다.

배타적사용권 crawl 후처리 옵션과 상태도 같은 job row에 저장한다. 주요 필드는 `include_exclusive_right_pipeline`, `exclusive_right_pipeline_mode`, `exclusive_right_auto_submit_batch`, `exclusive_right_auto_import_when_completed`, `exclusive_right_auto_consolidate`, `exclusive_right_limit`, `exclusive_right_candidate_count`, `exclusive_right_queue_created_count`, `exclusive_right_batch_job_id`, `exclusive_right_batch_status`, `exclusive_right_imported_count`, `exclusive_right_canonical_count`, `exclusive_right_consolidation_job_id`, `exclusive_right_pipeline_status`, `exclusive_right_pipeline_error`이다.

`fact_crawl_task`는 실제 네이버 뉴스 API 호출 단위다. 월별 Backfill에서는 `year`, `month`, `company_id`, `company_name`, `query_text`를 저장하고, API 호출 수, 조회 건수, 저장 기사 수, 중복 기사 수, 기간 외 기사 수, 오류 메시지를 누적한다.

`fact_crawl_event_log`는 `job_created`, `job_started`, `task_started`, `api_call`, `article_saved`, `duplicate_skipped`, `task_failed`, `job_completed`, `job_failed`, `job_cancelled` 같은 이벤트를 시간순으로 남긴다.

`fact_article.crawl_job_id`, `fact_article.crawl_task_id`는 어떤 수집 job/task에서 신규 저장된 기사인지 추적하기 위한 nullable FK다. 뉴스 중복 기준은 `original_url`, `link`, `title+pubDate+publisher` 순으로 만든 content hash다.

## Evidence Rule

LLM이 만든 정형값은 원문 근거가 있어야 자동 저장 후보가 된다. evidence가 없으면 `needs_review` 또는 `needs_human_review`로 저장한다.
## Product Canonicalization And Partner Context

`dim_product` includes canonicalization fields:

- `product_status`: `active`, `merged`, or `review`. Default dashboard queries exclude `merged`.
- `merged_into_product_id`: canonical target when this product was merged.
- `canonical_product_id`: canonical product id for active products and merged aliases.
- `partner_company_name`, `partner_context_summary`: lightweight partner context retained on the product row.

`dim_product_alias` stores raw product-name observations. Same-article weak mentions or descriptive aliases are attached to the canonical product instead of creating separate products.

`dim_partner_company` stores non-insurer partners such as telecom, platform, bank, card, agency, or affiliate organizations. These names must not be inserted into `dim_company` unless they are known insurer names or aliases.

`fact_product_partner` connects product, partner, article, role, evidence, and confidence.

`fact_product_merge_decision` records deterministic or AI-assisted merge decisions. `decision_source` can be `deterministic_same_article`, `deterministic_core_key`, `ai_same_product_judge`, or `manual`. Applied duplicate products remain in `dim_product` with `product_status='merged'` for auditability.

Candidate product-name types used before save:

- `official_name`
- `launch_name`
- `descriptive_alias`
- `weak_mention`
- `pronoun_or_context_reference`
- `partner_brand_phrase`
- `rejected`

`weak_mention` and `pronoun_or_context_reference` values do not create new products. They are stored as aliases when an official, launch, descriptive, or partner-context candidate exists in the same article context.

## Product Entity Resolution Tables

`fact_product_observation` records every product-name candidate observed during extraction or alias backfill. It stores the linked `product_id` when known, `article_id`, raw and normalized product names, `product_core_key`, `company_id`, raw company name, partner context, product type, release month, article title/description, source URL, local context text, `candidate_type`, confidence, and timestamps. This table is the audit trail that lets the system consolidate products later without asking the article-level extractor to compare against the whole catalog.

`dim_product.product_status` supports:

- `active`: canonical or currently displayed product.
- `provisional`: extracted product candidate that may still need consolidation.
- `merged`: duplicate product retained for audit, linked by `merged_into_product_id`.
- `review`: product candidate that needs human review.

`dim_product.canonical_product_id` points to the canonical product id for active/merged records when known. `alias_count`, `consolidation_status`, and `last_consolidated_at` help the dashboard and consolidation job avoid repeated work.

`fact_product_consolidation_job` stores each ProductConsolidationJob run. It records status, trigger type, mode, target counts, observation/provisional counts, block count, automatic merge count, review count, LLM call count, estimated cost, timestamps, and error message.

`fact_product_consolidation_block` stores deterministic blocking output for a consolidation job. A block contains candidate product ids, observation ids, company/partner context, release month window, product type codes, block reason, and block status. Blocks are the only unit eligible for optional LLM same-product judgment; pairwise product comparison is not used.

`fact_product_merge_decision` records applied or candidate merge decisions. Duplicate products are not deleted. Their related articles, aliases, observations, coverages, sales metrics, and narratives can be reassigned to the canonical product while the duplicate row remains marked as `merged`.

`dim_partner_company` and `fact_product_partner` separate non-insurer partners such as telecoms, banks, platforms, agencies, and affiliates from insurer master data. Partner names must not be inserted into `dim_company` unless they are known insurer names or aliases.
## 배타적사용권 스키마

### `fact_exclusive_use_right`

배타적사용권 canonical event 테이블이다. 회사, 업종, subject, 기간, 획득년월만 핵심 dimension으로 보관한다.

- `company_id`: `dim_company.company_id` nullable FK
- `company_name_normalized`: 회사 master/alias 기준 표준 보험회사명
- `insurance_type`: `생명보험`, `손해보험`, `unknown`
- `subject_name`, `subject_core_key`
- `exclusivity_months`
- `acquired_year_month`
- `feature_summary`, `evidence_summary`
- `primary_article_id`, `primary_article_title`, `primary_article_url`
- `article_count`, `confidence_total`, `needs_review`, `event_status`
- `merged_into_exclusive_right_id`, `canonical_exclusive_right_id`
- `alias_names_json`, `evidence_text`

회사명이 company master/alias로 확정되지 않으면 `company_id=null`, `company_name_normalized=null`, `insurance_type=unknown`, `needs_review=true`로 저장한다. 지역농협, 지점명, 대리점명, 플랫폼명, 제휴사명은 보험회사로 확정하지 않는다. `company_name_raw`, `company_display_name`, `exclusive_right_type`, `exclusive_right_type_code`, `subject_type`, `exclusivity_period_text`, `acquired_year_month_basis`, `acquired_date_text`는 저장하지 않는다.

`acquired_year_month`는 항상 `YYYY-MM` 형식이다. 기사 local context에 명시월이 있으면 그 값을 사용하고, “지난해 11월”, “올해 1월” 같은 상대 표현은 기사 게재일 기준으로 계산한다. 명시월이 없으면 관련기사 중 가장 이른 게재월을 사용한다. `2025-XX`, `2025-MM`, `unknown` 같은 placeholder는 저장하지 않는다.

조회 index:

- `insurance_type`
- `company_id`
- `company_name_normalized`
- `acquired_year_month`
- `(insurance_type, acquired_year_month)`
- `(company_id, acquired_year_month)`

### `fact_exclusive_use_right_observation`

배타적사용권 기사별 관측값 테이블이다. LLM 또는 rule parser 결과를 canonical로 확정하기 전 local context와 함께 저장한다.

- `company_id`
- `company_name_normalized`
- `insurance_type`
- `article_id`, `source_url`, `article_title`
- `raw_subject_name`, `normalized_subject_name_candidate`, `subject_core_key`
- `exclusivity_months`
- `acquired_year_month`
- `feature_summary`
- `evidence_text`
- `status_candidate`: `acquired`, `applied_or_planned`, `mentioned_only`, `rejected`, `unknown`
- `confidence`, `needs_review`

LLM이 반환한 회사명 후보는 최종 저장 전 `CompanyNormalizer`를 통과한다. 기사 제목보다 배타적사용권 문장 주변 local window의 회사명/alias를 우선한다. 여러 회사가 섞인 기사에서 local window 회사와 제목 회사가 다르면 local window 회사를 사용한다.

subject도 배타적사용권 문장 주변 local window에서 검증한다. “해당 상품”, “이번 상품”, “신상품”, “해당 특약”, “서비스” 같은 지시어·약칭은 canonical subject가 될 수 없다. 같은 문단의 따옴표 표현이나 바로 앞 문장에서 실제 명칭을 찾으면 치환하고, 실패하면 observation review로만 저장한다.

### 배타적사용권 수집/통합 보조 테이블

`fact_content_screening`에는 배타적사용권 후보 판정을 위한 컬럼을 둔다.

- `exclusive_right_score`
- `exclusive_right_candidate_yn`
- `matched_exclusive_keywords_json`

`fact_article_snippet.snippet_type`에는 배타적사용권용 타입을 추가한다.

- `exclusive_right`
- `exclusive_period`
- `exclusive_acquired_date`
- `exclusive_feature`

`fact_exclusive_use_right_article`은 canonical event와 관련 기사 연결을 저장한다. 같은 event/article 조합은 unique다.

`fact_exclusive_use_right_alias`는 기사마다 다르게 등장한 subject명을 저장한다. `raw_subject_name`, `normalized_subject_name_candidate`, `subject_core_key`, `article_id`, 관측 횟수와 최초/최종 관측 시각을 가진다.

`fact_exclusive_use_right_merge_decision`은 중복기사 또는 유사 subject명을 canonical event 하나로 통합한 이력을 저장한다. `decision_source`는 `deterministic_subject_core_key`, `deterministic_subject_similarity` 등 rule 기반 값을 사용한다.

`fact_exclusive_use_right`에는 병합 감사용 컬럼을 둔다.

- `merged_into_exclusive_right_id`
- `canonical_exclusive_right_id`

기본 목록/API/현황판/Excel은 `event_status='merged'` event를 제외하고 canonical active event를 표시한다. 기간 개월 수가 충돌하거나 회사가 다르면 자동 병합하지 않고 review로 둔다.

배타적사용권 LLM 배치 실행은 기존 `fact_llm_queue`, `fact_llm_batch_job`, `fact_llm_run`, `fact_llm_cost_log`를 재사용한다.

- `fact_llm_queue.task_type='exclusive_right_extract'`
- `target_type='article'`, `target_id=fact_article.article_id`
- `fact_llm_queue.crawl_job_id`는 crawl job 완료 hook에서 생성된 queue의 범위를 보존한다.
- `fact_llm_batch_job.crawl_job_id`는 특정 crawl job의 batch 추출 작업과 import 집계를 연결한다.
- `batch_eligible_yn=true`이면 Gemini Batch JSONL 생성 대상
- Batch JSONL `custom_id`는 `exclusive_right_extract:queue:{queue_id}:article:{article_id}:crawl:{crawl_job_id}` 형식
- import 성공 시 `fact_llm_run.batch_yn=true`, `fact_llm_cost_log.batch_yn=true`
- `applied_or_planned` 결과는 canonical event가 아니라 `fact_exclusive_use_right_observation.exclusive_right_id=null`, `needs_review=true`로 보관
## 조회 전용 상품 제외 정책

`실손의료` 상품 제외는 데이터 삭제 규칙이 아니라 일반 사용자 조회 정책이다. `dim_product.normalized_product_name`, `dim_product.raw_product_name`, `product_search_key`, `product_core_key`, `dim_product_alias`, `fact_product_observation` 중 하나에 공백/특수문자 제거 후 `실손의료`가 포함되면 기본 대시보드 상품목록, 신상품 현황판, 상품 Excel export, 일반 상품검색에서 제외한다.

관리자/디버그 조회나 직접 `product_id` 상세 조회는 원천 데이터를 보존하기 위해 이 정책을 강제하지 않는다. 향후 제외어는 `app/services/product_exclusion_service.py`의 pattern 목록 또는 같은 역할의 config로 확장할 수 있다.

## 배타적사용권 조회/Export 컬럼

배타적사용권 목록과 Excel export는 canonical active event를 기준으로 한다. `event_status='merged'` event는 기본 제외하고, `include_review=false`이면 검수 대상도 제외한다. Export 컬럼은 화면 조회조건을 그대로 적용하며 `배타적사용권 ID`, `업종`, `보험회사`, `상품/특약/제도명`, `배타적사용권 기간 개월 수`, `획득년월`, `주요 특징`, `대표 기사 제목`, `대표 기사 URL`, `alias 목록`, `근거문장` 순서로 반환한다.

## Company Attribution Fields

Company attribution for products and exclusive-use-right events is resolved by `CompanyAttributionService` before rows are saved. The service records the normalized insurer and insurance type from the company master/alias dictionary. Short aliases alone are review candidates and should not set `company_id`.

Existing rows can be audited with:

```powershell
python scripts/rebuild_product_company_attribution.py
python scripts/rebuild_exclusive_right_company_attribution.py
```

Dry-run CSV columns are `entity_type`, `entity_id`, `old_company`, `new_company`, `old_insurance_type`, `new_insurance_type`, `product_or_subject_name`, `confidence`, `reason`, `article_url`, and `action`.
