# 국내 보험상품 뉴스 인텔리전스 MVP

국내 장기손해보험 및 생명보험 상품 관련 뉴스, 보도자료, 수동 텍스트, 수동 정형 JSON을 수집하고 Gemini/Qwen 기반 추출·검증 결과를 SQLite에 저장해 상품 검색과 피벗 분석을 제공하는 로컬 MVP입니다.

## 빠른 시작

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python scripts/init_db.py
python scripts/seed_demo_data.py
uvicorn app.api.main:app --reload
```

기본 DB는 `sqlite:///./data/insurance_news.db`입니다. `.env`에 실제 API 키를 넣고, `.env`는 커밋하지 않습니다.

## 주요 명령

```powershell
python scripts/init_db.py
python scripts/seed_master_data.py
python scripts/collect_news.py --query-group new_product --days-back 30
python scripts/extract_pending_articles.py --limit 20
python scripts/export_pivot.py --preset product_type_by_month --format csv
python scripts/run_daily.py
pytest
```

## API 예시

```powershell
uvicorn app.api.main:app --reload
```

- `POST /api/articles/collect`: 네이버 뉴스검색 API 수집
- `POST /api/extractions/from-text`: 수동 텍스트 입력 후 LLM 추출
- `POST /api/ingestion/structured-product`: 수동 정형 JSON upsert
- `GET /api/products/search`: 상품명/회사/보험종류 검색
- `GET /api/products/{product_id}`: 상품 상세 조회
- `POST /api/pivots/run`: 상품/보장/판매실적 피벗
- `GET /api/dashboard/options`: 대시보드 필터 옵션
- `GET /api/dashboard/monthly-new-products`: 이달의 신상품 현황판 목록
- `POST /api/dashboard/query`: 대시보드 상품 비교표 조회
- `POST /api/dashboard/export`: 현재 필터 조건의 상품 비교표 Excel 다운로드
- `GET /api/companies`: 2024~2026 보험회사 마스터 조회
- `POST /api/companies/normalize`: 기사/텍스트의 회사명 alias 표준화
- `GET /api/review/queue`: 검수 대상 조회
- `GET /api/llm-runs/metrics`: LLM 실행 품질 지표

## 대시보드

```powershell
python scripts/init_db.py
python scripts/seed_demo_data.py
uvicorn app.api.main:app --reload
```

브라우저에서 `http://127.0.0.1:8000/`에 접속하면 사용자용 대시보드가 열립니다. Swagger 문서는 기존대로 `http://127.0.0.1:8000/docs`에서 확인할 수 있습니다.

대시보드는 피벗 요약 없이 상품 비교표를 바로 보여줍니다. 사용자는 `출시년도`, `업종`, `보험회사`, `보종군`을 선택해 상품 목록을 좁힐 수 있습니다. 보험회사 목록은 처음에는 비어 있고, `생명보험` 또는 `손해보험` 업종을 선택하면 해당 업종 회사만 체크박스로 표시됩니다.

첫 화면 상단에는 `이달의 신상품 현황판`이 표시됩니다. 현황판은 이번달 출시 상품을 하나씩 보여주며, 회사명, 상품명, 상품군, 출시년월, 2~3줄 요약을 제공합니다. 5초마다 다음 상품으로 자동 전환되고, 마우스를 올리거나 포커스하면 전환이 잠시 멈춥니다. 카드를 클릭하면 대표 원문 기사 URL이 새 탭으로 열립니다.

현황판은 Gemini/Qwen을 추가 호출하지 않습니다. 이미 DB에 저장된 narrative insight의 상품개발 요약, 상품특징 요약, 주요보장 요약, 마케팅 요약을 우선 사용하고, 없으면 대표 기사 description/title로 대체합니다. 이번달 상품이 없으면 가장 최근 출시월 상품을 fallback으로 보여줍니다.

출시년도, 보험회사, 보종군은 체크박스형 다중 선택을 지원하며 각 영역의 `전체선택`은 해당 조건을 적용하지 않는다는 뜻입니다. 업종이 `생명보험`이면 보험회사 `전체선택`은 생명보험사 전체, `손해보험`이면 손해보험사 전체를 의미합니다. 보종군 `전체선택`은 상품군 필터 없이 전체 상품군을 조회합니다. 회사 표시 범위는 합병/소멸/가교회사와 신규/소액단기보험사를 기본 포함하고, 사용자는 `재보험/외국지점 포함`만 선택할 수 있습니다.

조회 결과는 상품명, 보험회사, 출시년월, 대표 보종군을 중심으로 비교표 형태로 표시합니다. `엑셀 다운로드` 버튼을 누르면 현재 필터 조건 그대로 `insurance_product_comparison.xlsx`가 생성되며, 상품별 기본정보, 가입연령, 고지유형, 납입기간, 보험기간, 요약, 주요보장, 판매실적, 관련기사 제목을 상품 1행 기준의 가로형 비교표로 내려줍니다. 보조 보종군, 근거/설명, confidence, 검수필요, 관련 URL은 다운로드 파일에 포함하지 않습니다. 상품명을 클릭하면 하단 전체 폭 상품상세 패널에 주요보장 리스트, 판매실적, 관련기사가 표시됩니다.

## 2024~2026 보험회사 마스터

회사 마스터는 현재 영업사뿐 아니라 사명변경, 합병, 가교보험사, 신규 소액단기보험사, 철수/정리 이력이 있는 회사를 함께 관리합니다. 기본 상품 뉴스 조회에는 `include_in_product_news_default=Y` 회사만 표시하며, 재보험사/외국지점은 마스터에는 포함하지만 기본 상품 비교표에서는 제외합니다.

기본 조회에는 `MG손해보험`, `예별손해보험`, `캐롯손해보험`, `마이브라운반려동물전문보험`, `iM라이프생명`, `라이나손해보험`, `신한EZ손해보험`을 포함합니다. 대시보드에서는 `재보험/외국지점 포함` 체크박스로 재보험사와 외국지점을 추가할 수 있습니다.

대표 alias 예시는 다음과 같습니다.

- `DGB생명` → `iM라이프생명`
- `에이스손해보험` → `라이나손해보험`
- `BNP카디프손보` → `신한EZ손해보험`
- `캐롯손보` → `캐롯손해보험`
- `MG손보` → `MG손해보험`
- `마이브라운` → `마이브라운반려동물전문보험`

회사 마스터 기반 검색어를 함께 쓰려면 다음처럼 실행합니다.

```powershell
python scripts/collect_news.py --query-group new_product --include-company-queries --days-back 30
```

## 보험회사 표시순서

보험회사 표기순서는 보험업권별 설립년도 기준입니다. 사명변경년도, 현 브랜드 출범년도, 합병년도는 정렬 기준으로 쓰지 않고 `current_brand_year`에 참고값으로만 저장합니다. 사명변경이나 통합 이력이 있는 회사는 전신/모태 법인의 설립년도를 `establishment_year`로 저장하고, 화면과 API는 이 값을 기반으로 정렬합니다.

손해보험 표시 예시는 `메리츠화재 1922`, `한화손해보험 1946`, `롯데손해보험 1947`, `MG손해보험 1947`, `흥국화재 1948` 순입니다. 생명보험 표시 예시는 `한화생명 1946`, `흥국생명 1950`, `ABL생명 1954`, `삼성생명 1957`, `교보생명 1958` 순입니다.

예를 들어 `iM라이프생명`은 2024년 사명변경 기준이 아니라 부산생명/DGB생명 계보의 1988년 기준으로 정렬하고, `하나손해보험`은 2020년 출범 기준이 아니라 더케이/교원나라자동차보험 계보의 2003년 기준으로 정렬합니다. `신한EZ손해보험`도 2022년 현 브랜드 기준이 아니라 다음다이렉트자동차보험 계보의 2004년 기준입니다.

## 뉴스 수집 및 배치 운영

운영 배치는 뉴스 수집과 LLM 추출을 분리합니다. 기본은 뉴스 API 결과의 title/description/link/pubDate만 저장하며, 기사 원문 전문 저장은 `ENABLE_ARTICLE_BODY_FETCH=false` 정책을 유지합니다.

테스트 수집:

```powershell
python scripts/crawl_test_2026_01.py
```

전체 Backfill:

```powershell
python scripts/crawl_backfill_2024_2026_05.py
```

주간 업데이트:

```powershell
python scripts/run_weekly_update.py
```

관리자 화면에서도 실행할 수 있습니다. 대시보드에서 `관리자 업데이트`를 열고 비밀번호를 입력한 뒤 `2026년 1월 테스트 수집`, `2024~2026년 5월 전체 수집`, `최근 뉴스 업데이트`, `직접 기간 수집` 중 하나를 실행합니다. 실행 상태는 작업 목록에서 task 진행률, API 호출 수, 저장 기사 수, 중복 기사 수, 기간 외 기사 수, 오류 메시지로 확인할 수 있습니다.

필수/주요 환경변수:

- `NAVER_CLIENT_ID`
- `NAVER_CLIENT_SECRET`
- `ADMIN_BATCH_PASSWORD` 또는 `ADMIN_BATCH_PASSWORD_HASH`
- `WEEKLY_UPDATE_DAYS_BACK=14`
- `CRAWL_API_SLEEP_SECONDS=0.2`
- `CRAWL_MAX_API_CALLS_PER_JOB=5000`
- `CRAWL_USE_MONTH_KEYWORD=false`
- `MAX_COMPANY_ALIASES_FOR_QUERY=3`
- `MAX_QUERIES_PER_COMPANY_PER_MONTH=40`
- `ENABLE_GEMINI_BATCH=true`
- `BATCH_LLM_FOR_BACKFILL=true`
- `GEMINI_BATCH_MODEL=gemini-2.5-flash`
- `LLM_BATCH_MAX_REQUESTS=1000`
- `LLM_BATCH_OUTPUT_DIR=data/llm_batches`

네이버 뉴스 검색 API는 공식 기간 파라미터가 없으므로 `pubDate`를 프로그램에서 후처리 필터링합니다. `2026년 1월`, `2026.01`, `2026-01` 같은 월 키워드는 자동 수집 query에 붙이지 않습니다. 월 표현이 없는 신상품 기사가 누락될 수 있기 때문입니다. 넓은 기간은 월별 task로 나누되 검색어는 회사명, 상품군, 출시/신상품 키워드 중심으로 생성하고, 기간은 저장 직전 `pubDate`로 판정합니다.

검색 API에서 누락된 URL은 관리자 URL 직접 등록 또는 관리자 검색 preview로 점검해 보정합니다. 관리자 preview에는 임의 검색어를 넣을 수 있지만, preview 검색어는 자동 배치 QueryGenerator에 반영되지 않습니다.

재실행 시 `original_url`, `link`, 또는 `title+pubDate+publisher` 기반 해시로 중복 저장을 막습니다. Backfill은 오래 걸릴 수 있고, LLM 추출 옵션을 켜면 별도 API 비용이 발생할 수 있습니다.

Windows 작업 스케줄러 예:

- 프로그램: `python`
- 인수: `scripts/run_weekly_update.py`
- 시작 위치: repo root
- 주기: 매주 월요일 오전 7시

cron 예:

```bash
0 7 * * 1 cd /path/to/repo && /path/to/python scripts/run_weekly_update.py >> data/logs/weekly_update.log 2>&1
```

## 상품분류 체계

본 시스템의 상품분류는 법령상 보험종목 구분이 아니라 시장에서 널리 통용되는 상품군 기준입니다. 기존 분류는 삭제하지 않고, 실손의료, 자동차, 여행/레저, 펫, 치아, 연금/저축, 변액/유니버셜, 특정질병/중대질병, 보증/신용, 기업/단체/특종을 추가했습니다.

대표 상품군은 상품명에 명시된 특화 상품군을 우선합니다. 예를 들어 `면역질환보험`은 건강종합보다 `특정질병/중대질병`, `실손의료보험`은 `실손의료`, `자동차보험`은 `자동차`, `운전자보험`은 `상해 및 운전자`로 구분합니다. `간편(유병자)`과 `변액/유니버셜`은 primary가 될 수도 있지만, 많은 경우 secondary modifier로 함께 저장됩니다.

앱, 서비스, 할인 프로그램명은 상품명으로 저장하지 않습니다. `신한SOL 다이렉트`, `신한SOL EZ손보`, `쏠Drive`, `쏠Walk` 같은 값은 채널/마케팅 요소로 보존하고, 본문에서 `신규 출시`, `출시했다`, `선보였다`와 직접 연결된 보험상품명을 우선합니다. 예를 들어 신한EZ손해보험 기사에서 `신한SOL`이 아니라 `면역질환보험`을 상품명으로 저장하고, 상품군은 `특정질병/중대질병`으로 보정합니다.

## 데이터 정규화 개선 규칙

상품명은 저장 전에 deterministic normalizer를 통과합니다. 같은 회사의 상품명에 회사명이나 약칭이 붙거나 빠진 경우, 띄어쓰기나 일부 장식 기호가 다른 경우에도 `product_core_key`를 기준으로 같은 상품으로 인식합니다. 예를 들어 `한화손해보험 시그니처 여성건강 보험 4.0`, `한화손보 시그니처 여성건강보험 4.0`, `시그니처 여성건강보험 4.0`은 같은 회사라면 같은 상품으로 upsert됩니다. 단, 회사가 다르면 core key가 같아도 자동 병합하지 않습니다.

상품명 관측값은 `dim_product_alias`에 보존합니다. 상품 상세 화면에서는 표준 상품명과 함께 기사별 원문 등장명을 확인할 수 있습니다. 기존 데이터의 core key와 alias 관측값은 다음 스크립트로 보정할 수 있습니다.

```powershell
python scripts/backfill_product_core_keys.py --apply
```

출시년월이 기사에 명시되지 않은 상품은 관련 기사 중 가장 오래된 작성월을 `release_year_month`로 보정합니다. 이때 기준값은 `earliest_related_article_month`이며, 명시 출시월(`explicit_in_article`), 수동값(`manual`), 외부 근거값(`external_grounded_source`)은 덮어쓰지 않습니다.

```powershell
python scripts/backfill_release_months.py
```

회사명은 회사 마스터의 표준명 또는 alias로만 확정합니다. `경남농협`, 지역본부, 지점, 대리점, GA 지점명처럼 보험회사 마스터에 없는 조직명은 보험회사로 저장하지 않고 검수 대상으로 둡니다. 단, 원문에 `NH농협손해보험`, `농협손보`, `NH농협생명`, `농협생명`처럼 등록된 alias가 명시되어 있으면 해당 보험회사로 연결합니다.

## 설계 원칙

뉴스에는 모든 상품 정보가 없을 수 있으므로 기사에 없는 값은 만들지 않습니다. LLM이 추출한 정형값은 `evidence_text`와 `confidence`가 있어야 자동 저장 후보가 되며, 근거가 부족한 값은 review queue 또는 narrative insight로 보존합니다.

자세한 스키마와 정책은 `docs/`를 참고하세요.

## LLM 비용절감 구조

본 시스템은 모든 기사에 Gemini/Qwen을 호출하지 않는다. 수집된 기사는 먼저 룰 기반 screening을 거치며, 보험회사명, 상품군, 출시/신상품, 보장, 판매실적 신호를 점수화해 `fact_content_screening`에 저장한다. `low` 또는 `skip`으로 판정된 기사는 기본적으로 LLM queue를 만들지 않고 `screened_skip`으로 처리한다.

LLM 입력은 기사 전문이 아니라 `fact_article_snippet`에 저장된 근거문장 묶음이다. 출시, 상품명, 보장, 판매실적, 언더라이팅, 채널/마케팅 문장과 앞뒤 문장만 추려 `LLM_USE_SNIPPETS_ONLY=true` 기준으로 전달한다.

관련성이 높은 기사는 `fact_product_candidate_cluster`에서 `company_id + product_core_key` 기준으로 후보 상품 단위로 묶는다. 같은 상품 관련 기사 여러 건은 cluster 단위 queue로 만들어 중복 LLM 호출을 줄인다. 동일 input/prompt/schema/model 조합은 `fact_llm_response_cache`로 재사용하고, cache hit도 `fact_llm_run.cached_yn=true`로 남긴다.

검증은 모든 건에 수행하지 않고 `LLM_VERIFY_ONLY_RISKY=true` 기준으로 보장금액, 판매실적, 출시월 불명확, 회사/상품명 충돌 등 위험 신호가 있는 건 위주로 수행한다. Gemini Grounding은 `ENABLE_GEMINI_GROUNDING=false`가 기본이며, 수동 검수나 충돌 판정에서만 선택적으로 켠다.

LLM 실행 비용은 `fact_llm_cost_log`에 provider, model, task_type, input/output token, cache/batch 여부, estimated_cost_usd로 기록된다. 관리자 API `GET /api/admin/llm-cost-summary`와 관리자 패널에서 누적 예상 비용, token 합계, cache hit rate, batch 요청 수를 확인할 수 있다. 대량 백필은 `fact_llm_queue`의 batch eligible 항목을 `BatchLLMService`로 JSONL export한 뒤 Gemini Batch API에 제출하고, 완료 output을 import해 상품 DB에 반영한다.

Gemini Batch 처리 흐름:

1. 수집과 screening을 먼저 끝낸다.
2. `high`/`medium` 후보를 `fact_llm_queue.batch_eligible_yn=true`로 만든다.
3. 관리자 화면의 `LLM Batch 작업`에서 Batch를 생성한다.
4. `submit=true`이면 JSONL 생성 후 Gemini File API 업로드와 Batch API 제출까지 수행한다.
5. 상태 새로고침으로 `provider_status`를 확인한다.
6. `JOB_STATE_SUCCEEDED`가 되면 결과를 import한다.
7. import된 run은 `fact_llm_run.batch_yn=true`, 비용 로그는 `fact_llm_cost_log.batch_yn=true`로 저장된다.

Gemini Batch API는 대량 비동기 작업용이며 표준 interactive API 대비 50% 비용으로 처리되는 구조다. 운영 전 `config/llm_pricing.yaml`의 모델별 가격표를 최신 공식 가격 기준으로 확인해야 한다.

## LLM 비용 측정 및 절감률 확인

관리자 API `GET /api/admin/llm-cost-savings-summary`는 현재 구조의 실제 비용과 최적화 전 baseline 예상 비용을 비교한다. 기본 baseline은 `all_articles_fulltext_extract_and_verify`이며, 모든 수집 기사에 full text extract와 verify를 각각 1회 호출했다고 가정한다.

지원 baseline policy:

- `all_articles_fulltext_extract_only`
- `all_articles_fulltext_extract_and_verify`
- `candidate_articles_fulltext_extract_only`
- `candidate_articles_fulltext_extract_and_verify`

응답은 `baseline_estimated_cost_usd`, `optimized_actual_cost_usd`, `estimated_savings_usd`, `estimated_savings_rate`와 함께 screening, snippet, cluster, selective verification, cache, batch별 절감 기여도를 제공한다. `estimate_quality`는 `actual_tokens`, `mixed`, `rough`, `missing_price` 중 하나다. 실제 provider token usage가 있으면 실제 token을 우선하고, 없으면 입력 텍스트 길이를 한국어 기준으로 보수 추정한다. `input_hash`는 token 추정에 사용하지 않는다.

가격표는 `config/llm_pricing.yaml`에서 관리한다. Gemini/Qwen 가격은 변동될 수 있으므로 운영 전 최신 공식 가격표 기준으로 업데이트해야 하며, estimated cost는 실제 청구액과 다를 수 있다.

## 키워드 검색과 상품통합

대시보드 필터에는 `키워드` 입력창이 있다. 키워드는 표준 상품명, 원문 상품명, 상품명 alias, 상품 요약, 보장 요약, 주요보장명, 관련기사 제목과 요약을 함께 검색한다. 공백 차이를 줄이기 위해 `미니 보험`과 `미니보험`처럼 띄어쓰기만 다른 검색어도 같은 결과를 찾도록 보조 정규화 검색을 적용한다. 화면 조회와 Excel 다운로드는 같은 `DashboardQueryRequest.keyword` 조건을 사용한다.

상품명은 같은 기사 맥락에서 여러 표현으로 추출될 수 있으므로 canonical product 하나로 통합한다. `키즈폰 전용 어린이 미니 보험`, `미니 보험`, `어린이 특화 보험`, `키즈케어 보험`, `LG유플러스 키즈폰 고객 전용 미니 보험`처럼 같은 기사와 같은 제휴/보장 맥락에서 나온 표현은 대표 상품명 하나를 선택하고 나머지는 observation/alias로 보존한다. `이번 보험`, `해당 상품`, `미니 보험` 단독처럼 약한 언급은 독립 상품으로 만들지 않는다.

보험회사와 제휴사/플랫폼은 분리한다. 예를 들어 `LG유플러스`는 보험회사 master인 `dim_company`에 만들지 않고 `dim_partner_company`, `fact_product_partner` 또는 product partner context로 저장한다. 기본 조회와 Excel export는 `product_status='merged'` 상품을 제외하고 canonical 상품 1행만 보여주며, Excel에는 alias 목록, canonical product id, 통합근거 요약, source article URL을 함께 제공한다.

기사별 LLM은 기존 상품 전체와 비교하지 않고 추출자 역할만 수행한다. 추출된 상품명 후보는 `fact_product_observation`에 먼저 남기며, 명확한 exact core key match가 있으면 기존 상품에 연결하고 애매하면 `provisional` 상태로 저장한다. 전역 동일상품 판단은 별도 `ProductConsolidationJob`에서만 수행한다.

상품통합 job은 신규 observation이 쌓였을 때, crawl job 완료 후, 또는 관리자가 수동 실행할 때 동작한다. 기본값은 `rule_only_apply`와 LLM off이며, 같은 회사·유사 상품명·같은 상품군·가까운 출시월 후보를 blocking한 뒤 deterministic rule merge를 먼저 적용한다. rule로 판단하기 어려운 gray block만 관리자가 옵션을 켠 경우 block 단위 LLM judge로 넘긴다. pairwise LLM 비교와 조회/Excel 중 실시간 병합 LLM 호출은 사용하지 않는다.

같은 보험회사 안에서 기사마다 약칭과 공식명이 섞이는 경우에는 `product_family_signature`와 `family_tokens`를 추가로 사용한다. 예를 들어 `신한톤틴 연금보험`, `톤틴(Tontine) 연금`, `한국형 톤틴연금보험`은 `톤틴+연금` family로, `(무)우리WON건강환급보험`, `건강환급보험`, `납입 특약보험료 건강환급`은 `우리WON+건강환급` family로 묶인다. 단 `연금`, `건강보험`, `암보험`처럼 너무 일반적인 signature만으로는 자동 병합하지 않고, 서로 다른 회사나 `3.0`/`4.0` 같은 버전 충돌도 자동 병합하지 않는다. 공식명·출시명·브랜드 토큰이 있는 이름을 canonical로 우선 선택하고, 설명형 문구는 alias/observation으로 보존한다.

운영 스크립트:

```powershell
python scripts/backfill_product_observations.py --dry-run
python scripts/run_product_consolidation.py --mode dry-run --target all_provisional
python scripts/run_product_consolidation.py --mode rule-only-apply --target all_provisional
python scripts/run_product_consolidation.py --mode dry-run --target all --all-pages --include-family-signature
```

상세 기준은 `docs/PRODUCT_CONSOLIDATION.md`를 참고한다.

선택적으로 관리자/CLI에서만 list-level LLM 통합 검토를 실행할 수 있다. 이 경로는 기사별 LLM 동일상품 판단이 아니며, block 안의 compact 후보 목록만 LLM에 전달한다. LLM은 merge plan만 만들고, 실제 병합은 validator가 같은 회사, 버전 충돌 없음, 상품군 호환, 약칭 canonical 금지, confidence 0.85 이상 등을 확인한 뒤에만 적용한다. 기본값은 OFF다.

```powershell
$env:PRODUCT_LLM_CONSOLIDATION_ENABLED="true"
python scripts/check_product_duplicates.py --target all --output data/exports/product_duplicate_check.csv
python scripts/run_llm_product_consolidation.py --mode dry-run --target all --max-companies 20 --max-blocks 20
python scripts/run_llm_product_consolidation.py --mode dry-run --target company --company-name "Shinhan Life" --max-blocks 5
python scripts/run_llm_product_consolidation.py --mode apply --target all --max-companies 20 --max-blocks 20

$env:EXCLUSIVE_RIGHT_LLM_CONSOLIDATION_ENABLED="true"
python scripts/run_llm_exclusive_right_consolidation.py --mode dry-run --target all --max-blocks 20
python scripts/run_llm_exclusive_right_consolidation.py --mode apply --target all --max-blocks 20
```

상품 full-list dry-run은 `data/exports/product_full_list_llm_merge_plan.csv`를 생성한다. `scripts/check_product_duplicates.py`는 LLM을 호출하지 않는 읽기 전용 중복 점검이며, Excel 다운로드는 DB를 변경하거나 LLM을 호출하지 않는다. Excel 결과에 아직 중복 위험이 남아 있으면 `duplicate_warnings` sheet를 추가하고, canonical product family와 명확히 맞지 않는 alias는 사용자용 alias 목록에서 제외한다. 대시보드 렌더링이나 Excel 다운로드 중에는 이 LLM 통합 경로를 호출하지 않는다.
 
## LLM execution guard

The production extraction path enforces the cost-saving guardrails at runtime:

- Article extraction does not call any same-product or product-consolidation LLM judge.
- Every article extraction runs rule-based screening first and stores `fact_content_screening`.
- `low` and `skip` screening results do not create LLM queue items and do not call Gemini/Qwen.
- LLM extraction input is snippet-bundle based when `LLM_USE_SNIPPETS_ONLY=true`; full article body is not used by default.
- Product candidate clusters are preferred over article-level extraction when `ENABLE_PRODUCT_CLUSTER_EXTRACTION=true`.
- Verification runs only for risky results when `LLM_VERIFY_ONLY_RISKY=true`.
- Product consolidation LLM usage is isolated to `ProductConsolidationJob` gray blocks and is disabled by default with `PRODUCT_CONSOLIDATION_LLM_ENABLED=false`.
- Extract/verify calls use `fact_llm_response_cache` before calling a provider and write `fact_llm_run` plus `fact_llm_cost_log`.
- Dashboard and Excel export hide `product_status='merged'` by default and export canonical product rows with alias/observation names.
- Crawl jobs and CLI scripts use `extraction_mode` to separate collection from LLM work. Backfill should use `enqueue_only` or `batch`; `realtime` is intended only for small manual tests.

## Product Consolidation Signature Guard

Product consolidation signatures are calculated from product-name sources only:
the canonical product name, raw product name, product core key, aliases, and
product observations. Article titles, descriptions, snippets, narrative
summaries, and coverage summaries are used only for context similarity; they
must not enter `product_family_signature` or `version_signature`.

This prevents article words such as `암`, `치매`, `12일`, `1월`, `130만원`, or
general coverage phrases from polluting product identity. Explicit versions such
as `4.0`, `3.0`, `V2`, and `2세대` are recognized, while dates, periods, amounts,
and rankings are not treated as versions.

Rule-only consolidation handles same-company families such as Shinhan Life
tontine annuity variants, Hanwha Signature Women 4.0 variants, and ABL health
refund variants. Incompatible aliases, such as an anesthesia surgery product
appearing under a health-refund product, are preserved as source observations
but filtered from user-facing dashboard and Excel alias lists.

Before a large Excel export, run the deterministic consolidation and duplicate
guard first:

```powershell
python scripts/run_product_consolidation.py --mode rule-only-apply --target all --all-pages
python scripts/check_product_duplicates.py --target all --output data/exports/product_duplicate_check.csv
```

Excel export and dashboard rendering never call LLM. Optional full-list LLM
consolidation is administrator-triggered only and applies only
validator-approved merge plans.
- Weekly jobs can override the default with `WEEKLY_UPDATE_EXTRACTION_MODE`; otherwise `CRAWL_EXTRACTION_MODE` is used when set.

Administrators can inspect guardrail health with:

```http
GET /api/admin/llm-execution-guard-summary
```

The response includes low/skip LLM violations, article-level same-product LLM violations, full-body prompt violations, cache hit rate, task-type run counts, and whether snippet/cluster/risky-verify/consolidation flags are enabled. The dashboard admin panel also shows this summary.

## 상품 버전/출산지원/모바일 보장 GOAL 체크

시그니처 여성건강보험처럼 `3.0`/`4.0` 버전이 있는 상품은 버전을 보존해 별도 canonical로 유지한다. 버전 없는 약칭은 두 버전을 연결하는 자동 병합 근거로 쓰지 않는다. 반대로 `출산하면 보험료 지원`, `출산지원금`, `출산 혜택`처럼 같은 회사·같은 출시창의 출산/임신 지원 컴포넌트는 하나의 특약/보장 family로 묶되, 본상품에는 병합하지 않는다.

상품 출시월이 명시되지 않은 경우에는 관련기사 중 가장 이른 월을 무조건 쓰지 않고, 상품명/버전과 직접 연결된 출시 기사 또는 신상품 기사월을 우선한다. 판매실적, 배타적사용권, 보장금 지급 등 후속 기사월은 직접 출시 기사보다 뒤로 밀린다.

상품 상세의 주요보장 리스트는 API 응답 단계에서 보장명, 보장영역, 급부유형, 금액, 지급조건 기준으로 dedupe한다. PC 표와 모바일 아코디언 모두 같은 dedupe 함수를 사용한다.

회귀 확인:

```powershell
python scripts/run_product_version_birth_mobile_goal_check.py
```

결과는 `docs/product-version-birth-mobile-goal-result.md`에 저장되며, 이 스크립트는 크롤링/재파싱/LLM 호출을 하지 않는다.

## 상품통합 보정 운영

상품통합은 특정 상품명을 하드코딩하지 않고, 상품명과 기사 맥락을 함께 보는 context blocking으로 처리한다. 회사가 미확정이거나 제휴사 필드가 비어 있어도 출시월이 가깝고, 상품군이 호환되며, 상품명/기사 제목/요약/observation 문맥의 핵심 토큰이 겹치면 같은 block 후보로 묶는다. 단, 실제 자동 병합은 더 보수적으로 수행하며 known company가 서로 다르거나 상품군/버전이 명확히 충돌하면 자동 병합하지 않는다.

기존 데이터 정리는 먼저 dry-run으로 block CSV를 확인한 뒤 rule-only를 적용한다. 이 절차는 기본적으로 LLM을 호출하지 않는다.

```powershell
python scripts/run_product_consolidation.py --mode dry-run --target all --all-pages
python scripts/run_product_consolidation.py --mode rule-only-apply --target all --all-pages
```

Dry-run 결과는 `data/exports/product_consolidation_blocks.csv`에 저장된다. Excel과 대시보드는 `product_status='merged'` 상품을 기본 제외하고 canonical product 1행에 alias/원문 등장명을 모아 표시한다.

## 전체 배치 전 GO/NO-GO 체크

2024~2026 전체 배치를 실행하기 전에는 먼저 아래 스크립트를 실행한다.

```powershell
python scripts/pre_full_batch_go_check.py
```

결과가 `GO`이면 배타적사용권 띄어쓰기 키워드, local context window 선택, weak subject 검증, 배타적사용권 type master 제거, 사용자 화면/Excel 컬럼 단순화, LLM 비용절감 기본값이 배치 전 기준을 만족한 상태다. `NO_GO`이면 `failed_checks`에 표시된 항목을 고친 뒤 다시 실행한다. 이 스크립트는 정적 검사만 수행하며 Gemini/Qwen/Naver API를 호출하지 않는다.
## 배타적사용권 회사/업종 기준

배타적사용권 데이터는 “어느 보험회사가 획득했는지”가 핵심 정보이므로 canonical row와 observation row 모두에 업종과 보험회사명을 저장한다.

- 저장 필드: `company_id`, `company_name_normalized`, `insurance_type`
- 회사명 확정은 `config/company_dictionary.csv`의 표준 회사명과 alias를 기준으로 한다.
- `한화손보`, `농협손보`, `신한라이프` 같은 alias는 각각 표준 보험회사명과 업종으로 정규화한다.
- `경남농협`, 지점명, 대리점명, 플랫폼명, 제휴사명은 보험회사로 자동 확정하지 않는다.
- 회사가 불명확한 배타적사용권은 `insurance_type=unknown`, `needs_review=true`로 보관한다.

API와 화면:

- `GET /api/exclusive-rights`는 `insurance_type`, `company_id`, `company_name`, `company_names`, 획득년월, `keyword` 필터를 지원한다.
- `GET /api/dashboard/recent-exclusive-rights`는 최근 1년 배타적사용권 현황판용 데이터를 반환하며, 대시보드 업종 선택과 연동된다.
- `POST /api/exclusive-rights/export` Excel에는 업종, 보험회사, 상품/특약/제도명, 기간, 획득년월, 주요 특징, 대표 기사 URL, alias, 근거문장이 포함된다.

## 배타적사용권 수집/정형화 파이프라인

배타적사용권도 뉴스 수집 대상에 포함된다. 크롤링 검색어에는 `보험 배타적사용권`, `신상품심의위원회 보험`, `보험 신상품 배타적사용권` 같은 공통 검색어와 `{company} 배타적사용권`, `{company} 신상품심의위원회`, `{company} 독창성 인정` 같은 회사별 검색어가 포함된다. 월 키워드는 자동으로 붙이지 않고, 기간 조건은 기존 뉴스 수집과 동일하게 `pubDate` 후처리로 적용한다.

수집된 기사는 `ScreeningService`에서 상품 관련성 점수와 별도로 `exclusive_right_score`를 계산한다. `배타적사용권/배타적 사용권/독점사용권/독점 사용권`, `획득/부여/승인/인정받았다`, `신상품심의위원회`, `3/6/9/12개월`, 보험회사 alias를 점수화하며, 신청/추진/예정뿐인 기사는 후보에서 제외한다. 후보 결과는 `fact_content_screening.exclusive_right_candidate_yn`과 `matched_exclusive_keywords_json`에 저장된다.

LLM 입력은 기사 전문이 아니라 `exclusive_right`, `exclusive_period`, `exclusive_acquired_date`, `exclusive_feature` snippet bundle이다. 관리자 화면의 `배타적사용권 추출`에서 `none`, `screening_only`, `queue만 생성`, `Batch 추출용 queue`, `실시간 정형화`를 선택할 수 있으며, API는 `POST /api/admin/exclusive-rights/extract-pending`이다. 기본 운영은 `enqueue_only` 또는 `batch`이며, realtime은 `EXCLUSIVE_RIGHT_REALTIME_LIMIT` 범위 안의 소량 진단용이다. Queue 상태는 `GET /api/admin/exclusive-rights/extract-queue-status`로 확인한다.

크롤링 job 생성 시 `include_exclusive_right_pipeline=true`와 `exclusive_right_pipeline_mode=batch`를 주면, job 완료 후 해당 crawl job에서 새로 저장된 기사만 대상으로 screening, snippet 생성, `exclusive_right_extract` queue 생성, Batch job 준비까지 자동으로 이어진다. `exclusive_right_auto_submit_batch=false`가 기본이라 운영자가 Batch 제출 전 queue와 비용 범위를 확인할 수 있다. `exclusive_right_auto_import_when_completed=true`를 켠 경우 provider Batch가 성공 상태가 된 뒤 refresh 시 output import까지 이어질 수 있으며, import 후에는 `exclusive_right_auto_consolidate=true` 기준으로 rule-only 통합을 실행한다.

Batch를 사용할 때는 `LLM Batch 작업`의 task를 `exclusive_right_extract`로 선택한다. Batch JSONL은 `custom_id=exclusive_right_extract:queue:{queue_id}:article:{article_id}:crawl:{crawl_job_id}`를 포함해 import 시 원래 queue/article/crawl job을 추적한다. 완료 output을 import하면 `ExclusiveRightService.save_extraction_result()`가 schema 검증, 회사명 정규화, observation 저장, canonical upsert, article mapping, alias 저장을 수행한다. `applied_or_planned` 상태는 active canonical event로 확정하지 않고 review observation으로만 남긴다. 같은 batch output을 다시 import해도 canonical, observation, article mapping, alias가 중복 생성되지 않는다.

CLI:

```bash
python scripts/run_exclusive_right_batch.py --date-from 2026-01-01 --date-to 2026-01-31 --mode enqueue_only --limit 100
python scripts/run_exclusive_right_batch.py --date-from 2026-01-01 --date-to 2026-01-31 --mode batch --limit 100 --create-batch
python scripts/run_crawl_with_exclusive_batch.py --date-from 2026-01-01 --date-to 2026-01-31 --exclusive-mode batch
python scripts/list_exclusive_right_queue.py --date-from 2026-01-01 --date-to 2026-01-31
```

중복기사와 유사 subject명은 canonical event 하나로 통합한다. `fact_exclusive_use_right_article`은 event-article 연결을, `fact_exclusive_use_right_alias`는 원문 subject alias를, `fact_exclusive_use_right_merge_decision`은 병합 이력을 저장한다. 같은 회사, 같은/유사 subject core, 가까운 획득월, 같은 배타적사용권 기간이면 rule 기반으로 병합하고, 기간이 3개월과 6개월처럼 충돌하면 review로 둔다. merged event는 삭제하지 않고 `event_status='merged'`, `merged_into_exclusive_right_id`로 canonical event에 연결한다.

획득년월은 `acquired_year_month` 단일 필드만 사용한다. 기사에 “2025년 11월”, “지난해 11월”, “올해 1월”처럼 명시된 월이 있으면 기사 게재일 기준으로 계산하고, 명시월이 없으면 관련기사 중 가장 이른 게재월을 사용한다. `2025-XX`, `2025-MM`, `unknown` 같은 placeholder는 저장하지 않는다.

배타적사용권 대상은 기사 제목이 아니라 배타적사용권 키워드가 있는 문장과 주변 local context에서 판단한다. “해당 상품”, “이번 상품”, “신상품”, “해당 특약”, “서비스” 같은 지시어·약칭은 canonical subject로 저장하지 않고, 같은 문단의 따옴표 표현이나 바로 앞 문장에서 실제 상품/특약/제도/서비스명을 찾은 경우에만 치환 저장한다. 실패하면 observation review로만 남긴다. 기존 데이터 재정리는 `python scripts/rebuild_exclusive_rights.py --dry-run` 후 `--apply`로 실행하며 LLM을 호출하지 않는다.
## 대시보드 조회 정책과 배타적사용권 목록

일반 사용자 대시보드에서는 상품명, 원문 상품명, alias, observation에 `실손의료`가 포함된 상품을 기본 제외한다. 이 정책은 DB 원천 데이터를 삭제하지 않고 조회 단계에서만 적용되며, 상품 상세를 product_id로 직접 조회하거나 관리자/디버그 용도로 `include_excluded_policy_products=true`를 지정하면 확인할 수 있다. `실손보험`, `실비보험`처럼 `실손의료` 문구가 없는 이름은 이번 제외 규칙의 대상이 아니다.

상단 현황판은 데스크톱에서 `이달의 신상품`과 `최근 1년 배타적사용권`을 좌우 2단으로 표시하고, 좁은 화면에서는 세로로 쌓는다. 두 현황판 모두 기존 DB의 narrative summary, 기사 title/description, canonical 배타적사용권 event를 사용하며 LLM을 추가 호출하지 않는다. 배타적사용권 현황판은 `GET /api/dashboard/recent-exclusive-rights`를 사용하고 데이터가 없어도 200 응답과 빈 `items` 배열을 반환한다.

대시보드 하단의 `배타적사용권 조회`에서는 업종, 회사, 획득년월 범위, 키워드로 canonical 배타적사용권 목록을 조회할 수 있다. 대표 기사 제목은 원문 URL이 있으면 새 탭 링크로 열린다. `배타적사용권 엑셀 다운로드` 버튼은 현재 화면의 같은 조회조건을 `POST /api/exclusive-rights/export`로 전달해 별도 Excel 파일을 내려받는다.

## 사용자 화면 UI 테마

일반 대시보드는 브랜드 오렌지(`#ff6600`)를 상단 헤더 색으로 사용하고, 본문은 블랙/다크그레이 톤으로 표시한다. 기본 폰트는 `Noto Sans KR` 500 weight이며, 외부 폰트 로딩이 실패해도 `Apple SD Gothic Neo`, `Malgun Gothic`, sans-serif로 fallback된다.

상단 제목은 `보험상품 뉴스 자동조사봇`만 표시한다. 별도 subtitle과 보험회사 로고/사명은 사용자 화면에 노출하지 않는다. 관리자 업데이트 버튼은 공룡 얼굴 아이콘과 함께 표시되며, 기존 관리자 패널 열기 동작은 그대로 유지한다. 테이블, 필터, 현황판, 상세 패널은 dark background, gray border, white text를 기준으로 하고, 입력/버튼/테이블 padding과 글씨 크기를 기존보다 키워 운영자가 긴 표를 읽기 쉽게 조정했다.

일반 사용자 화면에는 내부 관리 정보인 confidence, 검수필요 여부, 보정이력, 통합이력, 원문 등장명, 추출근거/검수 섹션을 노출하지 않는다. DB와 관리자 API에는 필요한 내부 데이터가 남아 있지만, 상품비교표, 상품상세, 주요보장리스트, 배타적사용권 조회목록과 Excel은 사용자에게 필요한 핵심 컬럼만 표시한다.

### 모바일 화면

모바일 기준은 `767px` 이하이다. 데스크톱에서는 기존 상단 필터와 table 중심 레이아웃을 유지하고, 모바일에서만 전용 요소를 표시한다.

- 상단 현황판은 `신상품`과 `배타적사용권` 탭으로 전환한다.
- 상품 필터는 화면 상단에 길게 펼치지 않고 `필터` 버튼으로 여는 하단 시트에서 조정한다.
- 모바일 필터는 업종 세그먼트 버튼, 출시년도/보험회사/상품군 체크박스, 키워드 입력을 제공한다.
- 상품 목록은 table 대신 카드형 목록으로 표시하며, 카드에는 보험회사, 상품명, 출시년월, 상품군, 요약, 상세보기만 표시한다.
- 상품 상세는 모바일 전용 전체화면 모달에서 보여주고, 주요보장은 table 대신 카드/아코디언으로 표시한다.
- 배타적사용권 조회도 모바일에서는 카드형 목록과 전용 필터 하단 시트를 사용한다.

모바일 UI는 기존 API 응답을 그대로 사용한다. DB, migration, 크롤링, 배치, 파싱, LLM 로직은 모바일 대응을 위해 수정하지 않는다.
## Product Consolidation GOAL Check

Run this before trusting a large product export when duplicate product names
appear in Excel:

```powershell
python scripts/run_product_consolidation_goal_check.py
```

This is a consolidation-only check. It does not crawl Naver, does not reparse
articles, and the rule-only path does not call Gemini/Qwen. It verifies that
Tontine annuity variants, Hanwha Signature Women 4.0 variants, and ABL
health-refund variants collapse to canonical rows while Signature Women 3.0,
another insurer's similar Signature Women 4.0, and ABL whole-body anesthesia
surgery insurance remain separate. The result is written to
`docs/product-consolidation-goal-result.md`.

Optional LLM product-list consolidation is a separate administrator workflow:

```powershell
set PRODUCT_LLM_CONSOLIDATION_ENABLED=true
python scripts/run_llm_product_consolidation.py --mode dry-run --target all --max-companies 20 --max-blocks 20
```

It sends only compact same-company product lists and receives a merge plan.
Local validators must approve every merge before apply. It is never run during
article extraction, dashboard rendering, or Excel export. A live smoke test is
available only when explicitly enabled:

```powershell
set ENABLE_LIVE_LLM_CONSOLIDATION_TEST=true
python scripts/run_live_llm_product_consolidation_smoke.py
```
## Product Consolidation Real Export Quality Gate

Before final dashboard or Excel review, run the product consolidation quality
gate. It does not crawl news, does not reparse articles, and does not call
Gemini/Qwen in the rule-only path.

```powershell
python scripts/run_product_consolidation_goal_check.py
```

The script writes `docs/product-consolidation-goal-result.md`. It verifies that
the known real-export duplicate families collapse to canonical products:
Shinhan tontine annuity, Hanwha Signature Women 4.0, ABL health-refund, NH
StepUp 700, and KB pet-product variants. It also verifies negative controls:
different insurers, different versions, and unrelated ABL surgery products stay
separate.

Details and diagnosis for the real Excel row fixtures are in
`docs/product-consolidation-real-export-diagnosis.md`.

For the current operating DB, the final rule-only remediation report is
`data/exports/product_duplicate_check_real_final_after_all_fixes.csv`. It should
show `duplicate_group_count=0`, `high_risk_group_count=0`, and
`export_warning=false`. Weak or sentence-fragment product names such as
`지키면보험`, `다만건강보험`, and standalone `종합보험` are marked
`product_status='rejected'` and are excluded from dashboard and Excel views.
## 배타적사용권 중복 통합 품질 게이트

배타적사용권 canonical event는 같은 회사, 같은 배타적사용권 기간, 같은 획득년월, 유사 subject/component/evidence를 기준으로 rule-only 통합을 우선한다. 예를 들어 `여성건강보험특약`과 `여성건강보험`, 또는 `가정폭력 법률비용 담보 및 변호사 상담 서비스` 계열처럼 기사마다 표현이 조금 다른 대상은 하나의 canonical event로 정리하고, 나머지 표현은 alias로 보존한다.

이 통합은 대시보드 렌더링이나 Excel 다운로드 중에 LLM을 호출하지 않는다. article-level 재파싱도 하지 않으며, optional `exclusive_right_list_consolidation` LLM은 관리자가 명시적으로 켠 compact list workflow에서만 사용할 수 있다.

운영 전 회귀 확인은 아래 goal-check 스크립트로 수행한다.

```powershell
python scripts/run_exclusive_right_consolidation_goal_check.py
```

결과는 `docs/exclusive-right-consolidation-goal-result.md`에 기록된다. `GOAL status = PASS`이면 교보생명 여성건강보험특약 계열과 한화손해보험 법률비용/변호사 상담 서비스 계열이 각각 Excel 1행으로 통합되고, article-level/export-render LLM 호출이 0건임을 확인한 것이다.

상품 조회와 배타적사용권 조회의 키워드 입력창은 흰 배경에서도 입력값이 보이도록 검정 텍스트와 caret 색상을 강제한다. 데스크톱과 모바일 입력창 모두 같은 `keyword-search` 스타일을 사용한다.

## Company Attribution Reliability

Product and exclusive-use-right company attribution uses the shared `CompanyAttributionService` before data is saved. The resolver prefers the local product/exclusive-right evidence window over the article title or the first company in the full article. Full company names and long aliases outrank short aliases, and short aliases such as `Hanwha`, `Samsung`, `KB`, `DB`, `NH`, `Nonghyup`, `Shinhan`, `Kyobo`, `Heungkuk`, `Meritz`, `Lotte`, and `Hana` do not force a company by themselves.

The attribution layer is deterministic and does not call Gemini/Qwen. To audit existing rows, run dry-run first and review the CSV plan:

```powershell
python scripts/rebuild_product_company_attribution.py
python scripts/rebuild_exclusive_right_company_attribution.py
```

Apply only after review:

```powershell
python scripts/rebuild_product_company_attribution.py --apply
python scripts/rebuild_exclusive_right_company_attribution.py --apply
```

The goal check verifies product upsert, product candidate cluster, exclusive right save, short-alias review, rebuild detection, and zero LLM calls:

```powershell
python scripts/run_company_attribution_goal_check.py
```

Details are in `docs/company-attribution-diagnosis.md`; the latest run report is written to `docs/company-attribution-goal-result.md`.


### Dashboard board height and filter semantics

The top `monthly new products` and `recent exclusive-use-rights` boards keep a fixed card height so carousel transitions do not shift the layout. Names are clamped to two lines, summaries to four lines, and article titles to one line.

Dashboard filter arrays use an empty list to mean "no filter" for that dimension. `release_years=[]` means all release years, `company_names=[]` means all companies in the selected insurance type or all companies when insurance type is all, and `product_type_codes=[]` means all product type groups. When `product_type_codes` contains any value, the product type filter is applied even if insurance type is all and no company is selected. Query and Excel export use the same filter logic.

## Multi-Company Article Exclusion

Articles that mention two or more known insurer companies are excluded from new product and exclusive-use-right extraction at the article/source level. This is not a canonical entity deletion policy.

- `fact_article.multi_company_article_yn=true` prevents new extract queues, batch input, and import for that article.
- New crawl saves run snippet creation and `MultiCompanyArticleFilterService` immediately after screening, so articles are flagged before product clustering or LLM queue creation.
- The multi-company detector uses title, description, and saved snippets. It counts only known insurer companies from the company master and ignores associations, partners, platforms, agencies, and short ambiguous aliases.
- Existing cleanup affects only records derived from the excluded source article: observations, article links, aliases, coverage, narrative, and sales metrics.
- Canonical products or exclusive-use-right events remain visible when they have at least one non-multi-company source article.
- Canonical rows that only have multi-company source evidence are not physically deleted; they are marked as `rejected_multi_company_only` and excluded from default dashboard/export views.
- Raw article rows are preserved for audit.

Operational scripts:

```powershell
python scripts/audit_multi_company_articles.py --dry-run
python scripts/audit_multi_company_articles.py --apply
python scripts/cleanup_multi_company_product_extractions.py --dry-run
python scripts/cleanup_multi_company_product_extractions.py --apply
python scripts/cleanup_multi_company_exclusive_rights.py --dry-run
python scripts/cleanup_multi_company_exclusive_rights.py --apply
python scripts/run_multi_company_entity_safe_goal_check.py
```

Run dry-run and back up the DB before apply. The scripts do not physically delete products, exclusive-use-right events, or raw articles.

## Product Company Attribution and Marketing-Only Guard

Product company attribution is resolved from the local product evidence window before product creation. `query_company`, crawl task company, screening matched company names, and LLM company candidates are metadata only; they are not enough to create an active product when the local product sentence does not contain reliable company evidence.

The product guard is deterministic and does not call LLM providers.

- Local product window wins over article title, query company, and LLM company candidate.
- If local company differs from the LLM/query company, the local company is used and the product is marked for review when needed.
- If only query/company-candidate evidence exists for a generic product name such as `간편건강보험`, the product is not created as active.
- Marketing-only articles such as TV advertisement or campaign coverage do not create a new active generic product. If an existing row has only multi-company or marketing-only generic evidence, it is marked `rejected_marketing_only` and excluded from dashboard/export views.
- Batch import uses the same save path, so the guard also protects imported batch results.

Operational diagnostics:

```powershell
python scripts/diagnose_product_company_attribution.py --product-id 150 --output docs/product-150-company-attribution-diagnosis.md
python scripts/rebuild_product_company_attribution.py --product-id 150 --output data/exports/product_company_attribution_rebuild_plan_product_150.csv
python scripts/rebuild_product_company_attribution.py --apply --product-id 150
python scripts/run_product_attribution_multicompany_marketing_goal_check.py
```

The goal check writes `docs/product-attribution-multicompany-marketing-goal-result.md` and verifies the guard without realtime LLM calls.
