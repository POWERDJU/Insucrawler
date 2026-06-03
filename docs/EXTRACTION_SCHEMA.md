# Extraction Schema

`app/extractors/extraction_schema.py`에 Gemini/Qwen 공통 JSON 구조를 Pydantic으로 정의한다.

## Extraction

최상위 구조:

- `article_relevance`
- `products[]`

상품 구조:

- `identity`
- `product_type_classification`
- `structured_features`
- `narrative_insights`
- `missing_fields`
- `major_coverages`
- `sales_metrics`
- `evidence`
- `confidence`
- `needs_human_review`

기사에 없는 값은 `null` 또는 `unknown`으로 둔다. 보장금액, 출시월, 판매실적, 회사명, 보험종류는 evidence와 confidence 없이 확정하지 않는다.

`identity.release_year_month_basis`는 `explicit_in_article`, `inferred_from_article_date`, `first_seen_only`, `earliest_related_article_month`, `external_grounded_source`, `manual`, `unknown` 중 하나다. `earliest_related_article_month`는 저장 후처리에서 관련 기사 중 가장 오래된 작성월로 보정했음을 뜻한다.

`identity.company_name_candidate`는 회사 마스터의 표준명 또는 alias로 판단되는 경우에만 확정 후보로 사용한다. 지역농협, 지점, 지역본부, 대리점명, GA 지점명은 보험회사로 반환하지 않는다. LLM이 회사 마스터에 없는 이름을 반환하더라도 최종 저장 전 company normalizer가 이를 검수 대상으로 돌리고 `dim_company`를 자동 생성하지 않는다.

상품명은 저장 전 `product_core_key`로 정규화한다. 회사명/약칭 접두어와 띄어쓰기 차이는 제거하지만 버전 숫자(`4.0`, `V2`)는 보존한다. 같은 회사의 같은 core key는 동일 상품으로 upsert하고, 원문 등장명은 `dim_product_alias`에 기록한다.

## Verifier

Verifier는 다시 추출하는 모델이 아니라 `field_checks[]`를 생성하는 audit 모델이다.

판정값:

- `supported`
- `unsupported`
- `inferred`
- `incorrect`
- `ambiguous`

`unsupported`, `incorrect`, `critical`은 review queue로 연결한다.

## Adjudicator

충돌 시 원문 근거, deterministic normalizer, company dictionary, product type rule을 LLM보다 우선한다. 근거가 부족하면 `needs_human_review=true`로 둔다.
## 배타적사용권 추출 스키마

배타적사용권 추출 item은 회사/업종 후보를 명시해야 한다.

- `company_name_raw`
- `company_name_candidate`
- `company_name_normalized_candidate`
- `insurance_type_candidate`
- `company_evidence_text`
- `company_confidence`

이 값은 저장 전 `CompanyNormalizer`와 `company_dictionary.csv`를 통해 다시 확정한다. LLM 후보가 회사 master에 없거나 지역조직/지점/제휴사로 보이면 canonical row에는 `company_id=null`, `insurance_type=unknown`, `needs_review=true`를 저장한다.
