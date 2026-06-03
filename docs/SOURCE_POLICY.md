# Source Policy

뉴스 API는 네이버 뉴스검색 API를 1차 수집원으로 사용한다. BigKinds 등은 `BaseNewsClient` 인터페이스로 확장한다.

## 원문 전문 저장

기사 원문 전문 저장은 기본 비활성화한다.

```env
ENABLE_ARTICLE_BODY_FETCH=false
```

MVP는 뉴스 API의 `title`, `description`, `pubDate`, `link`, `originallink`, `source_api`, `query`, `query_group`, `collected_at`을 저장한다. 운영 배치에서는 `crawl_job_id`, `crawl_task_id`도 함께 저장해 어떤 수집 작업에서 유입된 기사인지 추적한다.

## Dedup

운영 배치 중복 기준은 다음 순서다.

1. `original_url`
2. `link`
3. `title + pubDate + publisher`

동일 hash가 이미 있으면 `fact_article`에 다시 삽입하지 않고 crawl task의 중복 건수만 증가시킨다.

## Company-Aware Queries

기본 수집은 `config/query_sets.yaml`의 정적 검색어를 사용한다. 옵션으로 `--include-company-queries`를 켜면 `dim_company`/`company_dictionary.csv`의 표준 회사명과 alias를 이용해 회사별 검색어를 추가 생성한다.

기본 생성 대상은 `include_in_product_news_default=Y` 회사다. 재보험사/외국지점은 `--include-reinsurers`, `--include-foreign-branches` 옵션을 켰을 때만 검색어에 포함한다. 회사별 alias는 `MAX_COMPANY_ALIASES_FOR_QUERY` 개수만 사용해 검색어 폭증을 막는다.

## Naver Search Date Filtering

네이버 뉴스 검색 API는 공식 기간 검색 파라미터가 없다. 따라서 수집기는 `pubDate`를 파싱해 `date_from <= pubDate <= date_to` 조건에 맞는 기사만 저장한다. 과거 Backfill은 누락 위험을 줄이기 위해 월별/회사별/검색어별 task로 나누지만, 검색어 뒤에 `2026년 1월`, `2026.01`, `2026-01` 같은 월 키워드는 자동으로 붙이지 않는다. 월 표현이 없는 신상품 기사를 놓칠 수 있기 때문이다.

넓은 기간을 한 검색어로 한 번에 조회하지 않는다. Naver API의 `display`는 최대 100, `start`는 최대 1000이므로 task는 `start=1,101,201,...,901` 형태로 pagination한다.

관리자 진단용 검색 preview에서는 임의 검색어 입력을 허용한다. 다만 이는 검색 품질 확인용이며 자동 수집 QueryGenerator의 월 키워드 생성과는 별개다.

## Evidence

정형값을 저장할 때는 원문 근거 문장인 `evidence_text`를 보존한다. 근거가 없거나 원문에 없는 추정값은 자동 확정하지 않는다.
