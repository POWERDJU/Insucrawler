# 배타적사용권 Subject 품질 기준

배타적사용권 데이터의 `subject_name`은 “어느 보험회사가 어떤 상품/특약/제도/서비스에 대해 배타적사용권을 획득했는지”를 식별하는 핵심 값이다. 따라서 기사 제목이나 LLM 원문 출력값을 그대로 믿지 않고, 저장 전에 local context 기반 검증을 반드시 수행한다.

## 저장 전 검증

`ExclusiveRightService`는 canonical event와 observation을 저장하기 전에 `validate_exclusive_subject_before_save()`를 호출한다.

다음 값은 canonical subject로 저장하지 않는다.

- `상품`
- `해당 상품`
- `이번 상품`
- `신상품`
- `특약`
- `서비스`
- `보험상품`
- `배타적사용권`

다음처럼 문장 조각이나 기관명이 섞인 값도 subject로 확정하지 않는다.

- `개발해`
- `출시`
- `획득`
- `협회로부터`
- `손해보험협회`
- `생명보험협회`
- `신상품심의위원회`

## Reference Resolution

subject가 약칭 또는 지시어이면 같은 local window, 바로 앞 문장, 기사 제목에서 더 구체적인 상품/특약/제도/서비스명을 찾는다.

예:

- `상품` → `(무)우리WON건강환급보험`
- `해당 상품` → `돌봄 로봇 제공 서비스`
- `보장 특약을 개발해 손해 보험` → `자기공명영상(MRI) 검사비 보장 특약`

구체적인 subject를 찾지 못하면 active canonical event를 만들지 않고 review/rejected observation으로 남긴다.

## Local Context 우선

배타적사용권 대상은 기사 전체 제목이 아니라 `배타적사용권`, `배타적 사용권`, `신상품심의위원회`, `획득`, `부여`, `승인`, `인정`이 등장하는 문장과 주변 문장 기준으로 판단한다.

여러 회사나 여러 상품이 섞인 기사에서는 local window 안의 보험회사와 subject가 기사 제목의 회사/상품보다 우선한다.

## Export와 목록 노출

`GET /api/exclusive-rights`와 `POST /api/exclusive-rights/export`는 기본적으로 weak subject, bad-tail subject, 비공식 subject를 제외한다. `include_review=true`를 사용하면 검수 목적의 review row를 조회할 수 있다.

Excel export에는 다음 컬럼만 포함한다.

1. 배타적사용권 ID
2. 업종
3. 보험회사
4. 상품/특약/제도명
5. 배타적사용권 기간 개월 수
6. 획득년월
7. 주요 특징
8. 대표 기사 제목
9. 대표 기사 URL
10. 관련기사 수
11. confidence
12. 검수필요
13. alias 목록
14. 근거문장

## 기존 데이터 재정리

기존 DB에 잘못 저장된 subject는 LLM 없이 deterministic rebuild로 정리한다.

```powershell
python scripts/rebuild_exclusive_rights.py --dry-run
python scripts/rebuild_exclusive_rights.py --apply
```

Dry-run은 `data/exports/exclusive_right_rebuild_plan.csv`에 다음 품질 정보를 포함한다.

- 기존 subject
- 제안 subject
- subject 품질 이슈
- resolution source
- resolution reason

`--apply`는 치환 가능한 subject를 resolved subject로 바꾸고, 치환이 불가능한 weak/bad subject는 rejected로 정리한 뒤 rule-only consolidation을 수행한다. 이 과정은 Gemini/Qwen을 호출하지 않는다.
