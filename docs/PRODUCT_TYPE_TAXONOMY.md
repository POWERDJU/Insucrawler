# Product Type Taxonomy

본 시스템의 상품분류는 법령상 보험종목이 아니라 뉴스/상품 비교 업무에서 널리 쓰는 시장형 상품군이다. 기존 코드는 삭제하지 않고, 보험시장 전반을 포괄하기 위해 신규 상품군을 추가한다.

| Code | 표시명 | 포함 기준 | 제외/주의 |
|---|---|---|---|
| DEATH_WHOLELIFE | 사망(종신/정기) | 종신보험, 정기보험, 사망보험 | 변액종신은 secondary `VARIABLE_UL`도 함께 사용 |
| HEALTH_COMPREHENSIVE | 건강(종합) | 질병·상해·진단·수술·입원 등을 종합 보장 | 실손, 암, 치매, 특정질병 등 전용 분류가 명확하면 전용 분류 우선 |
| SPECIFIC_DISEASE | 특정질병/중대질병 | 면역질환, 심뇌혈관, 뇌혈관, 심장질환, 통풍, 갑상선, 당뇨, 관절/척추 등 | 암은 `CANCER`, 치매/간병은 `DEMENTIA_CARE` 우선 |
| CANCER | 암보험 | 암 진단·치료·수술·입원 중심 상품 | 간편암보험은 primary `CANCER`, secondary `SIMPLIFIED_IMPAIRED` |
| MEDICAL_INDEMNITY | 실손의료 | 실손의료보험, 실손보험, 실비보험, 노후실손, 유병력자실손 | 건강종합과 구분 |
| ACCIDENT_DRIVER | 상해 및 운전자 | 상해보험, 운전자보험, 교통사고처리지원금, 벌금, 변호사선임비용 | 자동차보험은 `AUTO` |
| AUTO | 자동차 | 자동차보험, 다이렉트 자동차보험, 개인용/업무용 자동차보험 | 운전자보험과 구분 |
| SIMPLIFIED_IMPAIRED | 간편(유병자) | 간편고지, 유병자, 무고지, 고령자 | 많은 경우 secondary modifier |
| DEMENTIA_CARE | 치매간병 | 치매보험, 간병보험, 장기요양, 간병인 보장 | 간편치매보험은 secondary `SIMPLIFIED_IMPAIRED` |
| CHILD_ADULT_CHILD | 어린이/어른이 | 어린이, 자녀, 태아, 어른이보험 | 종합형이면 보조로 `HEALTH_COMPREHENSIVE` 가능 |
| DENTAL | 치아 | 치아보험, 치과보험, 임플란트, 크라운, 보철/보존치료 |  |
| PET | 펫/반려동물 | 펫보험, 반려동물보험, 강아지/고양이보험, 동물병원 치료비 | 마이브라운 관련 상품은 기본적으로 PET |
| TRAVEL_LEISURE | 여행/레저 | 국내외 여행보험, 유학생보험, 장기체류, 골프, 레저보험 |  |
| PROPERTY_EXPENSE | 재물 및 비용 | 화재, 재물손해, 배상책임, 비용손해 | 펫, 여행, 자동차는 전용 분류 우선 |
| GUARANTEE_CREDIT | 보증/신용 | 보증보험, 신용보험, 이행보증, 전세금보장 | 서울보증보험 관련 상품에 중요 |
| ANNUITY_SAVINGS | 연금/저축 | 연금보험, 연금저축보험, 저축보험, 교육보험 | 변액연금은 secondary `VARIABLE_UL` |
| VARIABLE_UL | 변액/유니버셜 | 변액보험, 변액종신, 변액연금, 유니버셜보험 | 많은 경우 secondary modifier |
| CORPORATE_GROUP_SPECIALTY | 기업/단체/특종 | 기업보험, 단체보험, 해상, 적하, 기술, 특종, 전문직배상책임 | 개인 장기보험 대시보드에서는 빈도가 낮을 수 있음 |
| OTHER | 기타 | 위 분류에 명확히 속하지 않음 |  |
| UNKNOWN | 분류불명 | 정보 부족으로 분류 불가 | 검수 대상 |

## 대표분류 우선순위

1. 수동 override
2. 상품명에 명시된 특화 상품군
3. 어린이/태아/어른이 등 가입대상형 상품군
4. 간편/유병자/무고지 modifier
5. 변액/유니버셜 modifier
6. 주요보장 risk_area/benefit_type 기반 보정
7. LLM 분류 결과
8. 불명확하면 `HEALTH_COMPREHENSIVE`, `OTHER`, `UNKNOWN` 중 보수적으로 선택

## 예시

- `면역질환보험` → primary `SPECIFIC_DISEASE`
- `간편암보험` → primary `CANCER`, secondary `SIMPLIFIED_IMPAIRED`
- `간편실손보험` → primary `MEDICAL_INDEMNITY`, secondary `SIMPLIFIED_IMPAIRED`
- `변액종신보험` → primary `DEATH_WHOLELIFE`, secondary `VARIABLE_UL`
- `변액연금보험` → primary `ANNUITY_SAVINGS`, secondary `VARIABLE_UL`
- `자동차보험` → primary `AUTO`
- `운전자보험` → primary `ACCIDENT_DRIVER`
