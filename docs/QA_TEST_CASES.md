# QA Test Cases

pytest는 다음 영역을 검증한다.

- amount normalizer: 억/천만원 변환, 보험료와 보장금액 구분
- date normalizer: 명시월/지난달/unknown 처리
- product type classifier: 암/간편/어린이/운전자/치매/종신/화재 분류
- coverage classifier: risk area와 benefit type 분류
- pivot service: primary_only/include_secondary distinct 집계와 grain 분리
- product search: 부분검색, 회사/보험종류 필터, 검색 key 정규화
- extraction schema: schema validation과 evidence 누락 review 처리
- llm routing: pipeline mode별 provider 선택과 조건부 검증
- verifier schema: unsupported/inferred/corrected field audit 저장
