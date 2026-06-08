# Pivot Spec

`app/services/pivot_service.py`는 `base`, `classification_mode`, `rows`, `columns`, `filters`, `metrics`를 받아 records를 반환한다.

## Base

- `product`: 상품 grain. 기본 view는 `vw_product_primary_type_pivot`.
- `coverage`: 주요보장 grain. view는 `vw_product_type_coverage_pivot`.
- `sales`: 판매실적 metric grain. view는 `vw_product_sales_pivot`.

## Classification Mode

- `primary_only`: 상품 1개는 대표 보험종류 기준으로 1회 집계한다.

보조 보종군은 더 이상 저장/조회하지 않는다. 이전 API 호환을 위해 `classification_mode="include_secondary"` 값이 들어와도 서비스는 `primary_only`로 처리한다. `product_count`는 모든 base에서 `product_id` distinct 기준을 유지한다.

## 중복 집계 방지

상품, 보장, 판매실적은 grain이 다르다. `coverage_count`는 `coverage_id`, `sales_metric_sum`은 `sales_metric_id`/`metric_value`, `product_count`는 `product_id` distinct로 계산한다.

한 피벗에서 서로 다른 grain의 metric을 같이 요청할 수는 있지만, MVP는 각 metric의 field 기준으로 독립 집계한다. 사용자는 coverage base에서 상품 수를 볼 때 `count_distinct product_id`를 써야 한다.

## 기본 Preset

- 업종 + 회사별 피벗
- 출시월별 피벗
- 상품별 피벗
- 보험종류별 피벗
- 보험종류 × 주요보장 피벗

## 대시보드 상품 비교표

대시보드 화면은 피벗 preset, 행 기준 버튼, 열 기준 columns를 사용하지 않는다. 사용자는 `release_years`, `insurance_type`, `company_names`, `product_type_codes`를 필터로 선택하고 상품 비교표를 확인한다.

대시보드 필터는 출시년도, 보험회사, 보종군을 체크박스형 다중 선택으로 보낸다. 각 영역의 `전체선택`은 배열을 비워 보내는 방식이며, 회사 목록은 업종을 먼저 선택한 뒤 해당 업종 회사만 표시한다.

화면에서 보내는 `custom_rows`는 `["company_name", "product_type_name"]`, `custom_columns`는 항상 `[]`이다. `pivot_result`는 기존 API 호환을 위해 계속 반환하지만 화면에는 표시하지 않는다.

상품 비교표 Excel export는 `/api/dashboard/export`에서 제공한다. 동일한 필터 조건으로 상품별 기본정보, 상품특성, 요약, 주요보장, 판매실적, 관련기사 제목을 상품 1행 기준의 가로형 비교표로 내려준다. 반복 grain인 주요보장, 판매실적, 관련기사는 `주요보장1`, `주요보장2`처럼 번호가 붙은 컬럼으로 펼친다. 다운로드 파일에는 근거/설명, confidence, 검수필요, 관련 URL을 포함하지 않는다.

대시보드 내부 기본 pivot base는 `product`이며, 직접 피벗 API를 호출하는 사용자는 기존처럼 `coverage`, `sales` base를 사용할 수 있다.

## 회사 포함 기준

기본 피벗과 상품 검색은 `dim_company.include_in_product_news_default='Y'` 회사를 대상으로 한다. 재보험사와 외국지점은 회사 마스터에는 보존하지만 기본 상품 뉴스 피벗에서는 제외한다.

옵션:

- `include_reinsurers`: `company_role='reinsurer'` 회사를 포함한다.
- `include_foreign_branches`: `company_role in ('foreign_branch', 'reinsurer_or_foreign_branch')` 회사를 포함한다.
- `include_changed_companies`: `renamed`, `merged`, `transferred_to_bridge`, `bridge`, `exiting` 상태 회사를 포함한다. 기본값은 포함.
- `include_short_term_insurers`: `short_term_pet_insurer` 또는 `new` 상태 회사를 포함한다. 기본값은 포함.

피벗 dimension으로 `company_role`, `status_2024_2026`을 사용할 수 있다. 예별손해보험 같은 가교보험사와 캐롯손해보험 같은 합병 이력 회사는 기본 포함 대상(`Y`)이지만, 상태별 분석이 가능하도록 별도 status를 유지한다.

회사 dimension의 표시순서는 업권별 설립년도 기준이다. 사명변경년도, 현 브랜드 출범년도, 합병년도는 정렬 기준으로 쓰지 않는다. 대시보드 회사 필터와 `/api/companies` 응답은 `display_order_established`, `establishment_year`, `establishment_month`, `establishment_day`, `sort_tie_breaker` 순으로 정렬한다.
