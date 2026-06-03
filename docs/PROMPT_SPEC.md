# Prompt Spec

프롬프트는 `app/llm/prompts.py`에서 버전 관리한다.

## Extractor

목적: 기사/텍스트에서 보험상품 정보를 추출한다.

규칙:

- 기사에 없는 정보는 만들지 않는다.
- 정규화 가능한 값은 structured field에 넣는다.
- 정규화가 어려운 상품특성은 narrative insight로 요약한다.
- 주요 정형값에는 evidence_text와 confidence를 포함한다.
- company_name_candidate는 회사 마스터의 표준 보험회사명 또는 alias로 판단되는 경우에만 반환한다.
- 지역농협, 지점, 대리점, 은행 지점, 지역본부, 설계사 조직, GA 지점명은 보험회사명으로 반환하지 않는다.
- 보험회사명이 불명확하면 추정하지 않고 unknown으로 둔다.
- 제목의 첫 따옴표 표현을 무조건 상품명으로 보지 않는다.
- `신규 출시`, `출시했다`, `선보였다`, `내놨다`와 직접 연결된 보험상품명을 우선한다.
- `신한SOL 다이렉트`, `신한SOL EZ손보`, `쏠Drive`, `쏠Walk`, 앱, 플랫폼, 서비스, 할인 프로그램은 상품명이 아니라 채널/마케팅 요소로 처리한다.
- `면역질환보험`처럼 특정 질병군을 집중 보장하는 상품은 `SPECIFIC_DISEASE`로 분류한다.
- 자동차보험과 운전자보험, 실손의료보험과 건강종합을 구분한다.
- JSON으로만 응답한다.

## Verifier

목적: 1차 추출 JSON을 원문과 대조해 field-level audit한다.

엄격 점검:

- 기사 발행월을 출시월로 오인
- 회사 전체 실적을 특정 상품 실적으로 오인
- 월 보험료를 보장금액으로 오인
- 보장금액 단위 변환 오류
- 상품명과 특약명 혼동
- 손보/생보 구분 오류
- evidence_text가 원문에 없는 경우
- company_name_candidate가 회사 마스터의 보험회사인지 여부
- 지역조직명이나 지점명을 보험회사로 오인한 경우
- product_name이 실제 보험상품명인지 앱/서비스/할인/브랜드명인지 여부
- `신한SOL`, `신한SOL 다이렉트`, `신한SOL EZ손보`, `쏠Drive`, `쏠Walk`가 상품명으로 추출된 경우 실제 출시 상품명 suggested_value 제안
- `자동차보험`을 `ACCIDENT_DRIVER`로, `실손보험`을 `HEALTH_COMPREHENSIVE`로, `면역질환보험`을 `HEALTH_COMPREHENSIVE`로 분류한 경우

## 저장 전 후처리

- 상품명은 회사명/alias 제거, 공백 정규화, 버전 숫자 보존 규칙으로 `product_core_key`를 만든다.
- deterministic launch candidate extractor는 출시 문장과 직접 연결된 `...보험` 후보를 뽑고, 앱/서비스/할인명 negative pattern을 배제한다.
- verifier가 high severity incorrect와 suggested_value를 주거나 deterministic candidate가 더 명확하면 저장 전에 최종 extraction을 보정한다.
- 상품명/상품분류 보정은 `fact_extraction_field_audit`에 남긴다.
- 같은 `company_id + product_core_key`는 같은 상품으로 upsert한다.
- 회사가 다르거나 company_id가 불명확하면 자동 병합하지 않는다.
- 출시년월이 없으면 관련 기사 중 가장 오래된 작성월을 `earliest_related_article_month` 기준으로 보정한다.

## Adjudicator

목적: 두 모델 결과가 충돌할 때 최종 저장값을 결정한다.

근거가 부족하면 값을 확정하지 않고 review로 보낸다.
## Same Product Judge

The same-product judge is used only for merge candidates, not for every product pair. It receives two candidate products with company, partner, article title, article summary, coverage summary, and source URL context.

Expected output:

```json
{
  "same_product": true,
  "confidence": 0.92,
  "canonical_product_name": "키즈폰 어린이 미니보험",
  "merge_reason": "same article and same coverage context",
  "alias_names": ["미니 보험", "키즈케어 보험"],
  "should_auto_merge": true,
  "needs_human_review": false
}
```

Rules:

- Same article or same source URL with compatible company/partner/product type can be auto-merged when confidence is at least `0.85`.
- Confidence from `0.65` to below `0.85` becomes a review candidate.
- Different insurer companies must not auto-merge even if product names are similar.
- Partner brand phrases such as `LG유플러스 키즈폰 고객 전용` are partner/channel context, not insurer company names.
- Weak mentions such as `이번 보험`, `해당 상품`, `미니 보험` alone are aliases or context references, not standalone product names.
## 배타적사용권 회사명 추출 규칙

배타적사용권 추출 시 각 item은 `company_name_candidate`, `insurance_type_candidate`, subject, 기간, 획득년월, feature/evidence summary를 중심으로 반환한다. 원문 회사명, 배타적사용권 구분, subject type, 기간 원문, 획득년월 basis는 저장 대상이 아니다.

- 배타적사용권을 획득한 보험회사를 찾아야 한다.
- 기사에 여러 회사가 등장하면 기사 제목보다 배타적사용권 문장 주변 local context의 획득 주체를 우선한다.
- 회사명이 불명확하면 `unknown`으로 둔다.
- 제휴사, 플랫폼, 은행, 지역조직, 지점, 대리점은 보험회사로 쓰지 않는다.
- 회사 master에 없는 이름은 확정하지 않는다.
- `해당 상품`, `이번 상품`, `신상품`, `해당 특약`, `서비스` 같은 지시어·약칭은 subject_name으로 출력하지 않는다. 같은 local window의 따옴표 표현이나 바로 앞 문장에서 실제 상품/특약/제도/서비스명을 찾아 치환하고, 찾지 못하면 `needs_review=true`로 둔다.
- 신청/추진/예정은 acquired가 아니다. 획득년월은 명시월이 있으면 사용하고, 없으면 저장 로직에서 관련기사 최초 게재월로 보정한다.

Verifier는 `company_name_candidate`가 실제 배타적사용권 획득 회사인지, 상품/특약/제도 주체와 일치하는지, 업종이 company master 기준으로 맞는지 검증한다.
