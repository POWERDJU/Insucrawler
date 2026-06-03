# Product Type Classification Rules

분류 우선순위는 `manual > rule > LLM`이다. `config/product_type_rules.yaml`의 strong keyword가 대표분류를 가장 강하게 결정하며, LLM 분류는 보조 신호로만 사용한다.

대표분류 정책:

- 암보험 명시: `CANCER`
- 면역질환/심뇌혈관/특정질병/중대질병 명시: `SPECIFIC_DISEASE`
- 실손의료/실손/실비 명시: `MEDICAL_INDEMNITY`
- 자동차보험 명시: `AUTO`
- 운전자보험 명시: `ACCIDENT_DRIVER`
- 치아보험 명시: `DENTAL`
- 펫/반려동물보험 명시: `PET`
- 여행자/골프/레저보험 명시: `TRAVEL_LEISURE`
- 치매/간병보험 명시: `DEMENTIA_CARE`
- 종신/정기/사망보험 명시: `DEATH_WHOLELIFE`
- 연금/저축/교육보험 명시: `ANNUITY_SAVINGS`
- 보증/신용/전세금보장보험 명시: `GUARANTEE_CREDIT`
- 기업/단체/해상/적하/특종보험 명시: `CORPORATE_GROUP_SPECIALTY`
- 건강/종합보험 명시: `HEALTH_COMPREHENSIVE`, 단 전용 분류가 명확하면 전용 분류 우선
- 정보 부족: `UNKNOWN`

Modifier 정책:

- 간편/유병자/무고지는 기본 보조분류 `SIMPLIFIED_IMPAIRED`다.
- 변액/유니버셜은 기본 보조분류 `VARIABLE_UL`다.
- `간편암보험`은 primary `CANCER`, secondary `SIMPLIFIED_IMPAIRED`.
- `변액종신보험`은 primary `DEATH_WHOLELIFE`, secondary `VARIABLE_UL`.
- `변액연금보험`은 primary `ANNUITY_SAVINGS`, secondary `VARIABLE_UL`.

상품명 추출 보정:

- `신규 출시`, `출시했다`, `선보였다`, `내놨다`와 직접 연결된 `...보험` 후보를 제목의 브랜드/서비스명보다 우선한다.
- `신한SOL`, `신한SOL 다이렉트`, `신한SOL EZ손보`, `쏠Drive`, `쏠Walk`처럼 앱/서비스/할인명으로 판단되는 값은 상품명으로 저장하지 않는다.
- 서비스명과 실제 보험상품명이 붙어 있으면 서비스 prefix를 제거하고 실제 보험상품명만 사용한다.

세부 keyword는 `config/product_type_rules.yaml`에 둔다.
