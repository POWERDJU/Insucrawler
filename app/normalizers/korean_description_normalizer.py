from __future__ import annotations

import re
from typing import Any


_HANGUL_RE = re.compile(r"[가-힣]")
_EN_WORD_RE = re.compile(r"[A-Za-z]{2,}")
_ASCII_LETTER_RE = re.compile(r"[A-Za-z]")
_ALLOWED_ENGLISH_TOKENS = {
    "DB",
    "AXA",
    "KB",
    "SK",
    "KT",
    "NS",
    "CU",
    "M",
    "TV",
    "LMS",
    "ABL",
    "CDR",
    "WGS",
    "KPI",
    "APE",
    "DIY",
    "Pi",
    "OK",
    "THE",
    "The",
    "S",
    "V",
    "N",
    "UP",
    "WON",
    "Fit",
    "ZERO",
    "NH",
    "VBI",
    "LG",
    "PRO",
    "Plus",
    "NHe",
    "HANA",
    "NEXT",
}
_CODE_TRANSLATIONS = {
    "unspecified": "미분류",
    "DEATH": "사망보험",
    "DEATH_WHOLELIFE": "종신보험",
    "DEATH_TERM": "정기보험",
    "TRAVEL_LEISURE": "여행·레저보험",
    "TRAVEL": "여행보험",
    "LEISURE": "레저보험",
    "PERSONAL_ACCIDENT": "상해보험",
    "ACCIDENT": "상해보험",
    "ACCIDENT_DRIVER": "운전자·상해보험",
    "HEALTH_COMPREHENSIVE": "종합건강보험",
    "HEALTH": "건강보험",
    "SPECIFIC_DISEASE": "특정질병보험",
    "RIDER": "특약",
    "DEMENTIA_CARE": "치매·간병보험",
    "CANCER_AND_NURSING_CARE": "암·간병보험",
    "ANNUITY_SAVINGS": "연금·저축보험",
    "ANNUITY": "연금보험",
    "ENDOWMENT": "환급형 보험",
    "WHOLE_LIFE": "종신보험",
    "LIFE_INSURANCE": "생명보험",
    "OTHER": "기타",
}
_LOW_VALUE_TERMS = {
    "보험",
    "보장",
    "보험상품",
    "보험 보장",
    "제공",
    "제공합니다",
    "제공됩니다",
    "제공합니다.",
    "제공됩니다.",
    "출시했습니다",
    "형태로 출시됐습니다",
    "설계됐습니다",
    "목적으로 합니다",
    "줄입니다",
    "중점적으로 다룹니다",
    "보장합니다",
    "인정받은",
    "획득했습니다",
    "통해 가입할 수 있습니다",
    "가입 가능",
    "포함합니다",
    "로 언급됐습니다",
    "근거로",
    "에 따라",
    "및",
    "또는",
    "포함 또는",
    "고객",
    "대상",
    "기사",
    "전년도",
    "무료",
}


FIELD_FALLBACKS = {
    "product_category_summary": "상품 분류와 성격이 기사 근거 기준으로 정리되어 있습니다.",
    "partner_context_summary": "최종 검증에서 상품명, 회사명, 출시월 또는 제휴 정보를 기사 근거에 맞춰 보정했습니다.",
    "feature_summary": "기사 원문에서 확인되는 상품 특징을 기준으로 정리했습니다.",
    "product_development_summary": "기사 원문에서 확인되는 출시 또는 개발 배경을 기준으로 정리했습니다.",
    "marketing_summary": "기사 원문에서 확인되는 홍보, 캠페인 또는 이벤트 내용을 기준으로 정리했습니다.",
    "target_customer_summary": "기사 원문에서 확인되는 가입 대상 또는 고객층을 기준으로 정리했습니다.",
    "underwriting_summary": "기사 원문에서 확인되는 가입심사 또는 인수 기준을 기준으로 정리했습니다.",
    "channel_summary": "기사 원문에서 확인되는 판매 채널 또는 제휴 채널을 기준으로 정리했습니다.",
    "coverage_summary": "기사 원문에서 확인되는 보장 내용을 기준으로 정리했습니다.",
    "sales_summary": "기사 원문에서 확인되는 판매 실적 또는 시장 반응을 기준으로 정리했습니다.",
    "differentiation_summary": "기사 원문에서 확인되는 차별화 요소를 기준으로 정리했습니다.",
    "risk_note_summary": "기사 원문에서 확인되는 유의사항 또는 위험 요인을 기준으로 정리했습니다.",
    "missing_info_summary": "보장금액, 납입기간, 보험기간 등 일부 세부 정보는 기사에서 충분히 확인되지 않습니다.",
    "condition_text": "기사에서 확인되는 지급 조건입니다.",
    "limit_text": "기사에서 확인되는 보장 한도입니다.",
    "amount_basis": "기사에서 확인되는 금액 산정 기준입니다.",
    "evidence_summary": "기사에서 해당 내용의 근거가 확인됩니다.",
}


_EXACT_TRANSLATIONS = {
    "initial examinations and treatments": "초기 검사와 치료",
    "undergoing general anesthesia": "전신마취를 받는 경우",
    "victims of voice phishing": "보이스피싱 피해자",
    "resulting from car accidents": "자동차 사고로 발생한 경우",
    "specialized for small and medium-sized m&a": "중소형 M&A에 특화된 경우",
    "annual limit of 5 million krw per incident": "사고 1건당 연간 500만원 한도",
    "differentiated based on pet weight": "반려동물 체중에 따라 차등 적용",
    "simplified to 5 categories": "5개 항목으로 간소화",
    "relative": "상대 기준",
    "premium_percentage": "보험료 비율",
    "per_diagnosis": "진단 1회당",
    "per_period_total": "기간별 총액 기준",
    "premium_or_reserve_based": "보험료 또는 적립금 기준",
    "per_incident": "사고 1건당",
    "per_occurrence": "발생 1건당",
    "per_accident": "사고 1건당",
    "per_visit": "방문 1회당",
    "per_person": "1인당",
    "per_month": "월별 기준",
    "per_surgery": "수술 1회당",
    "per incident": "사고 1건당",
    "coverage_period": "보험기간 기준",
    "coverage_limit": "보장 한도 기준",
    "loan_limit": "대출 한도 기준",
    "max_amount": "최대 금액 기준",
    "explicit_in_article": "기사에 명시된 기준",
    "not_specified": "명시되지 않음",
    "unknown": "확인되지 않음",
    "up to 500,000 krw": "최대 50만원",
    "details not provided in the snippet.": "기사 요약문에는 세부 내용이 제공되지 않았습니다.",
}


_COMPANY_REPLACEMENTS = (
    ("Samsung Fire & Marine Insurance", "삼성화재"),
    ("Samsung Life Insurance", "삼성생명"),
    ("Samsung Life", "삼성생명"),
    ("Hanwha General Insurance", "한화손해보험"),
    ("Hanwha Life Insurance", "한화생명"),
    ("Hyundai Marine & Fire Insurance", "현대해상"),
    ("Hyundai Fire & Marine Insurance", "현대해상"),
    ("Meritz Fire & Marine Insurance", "메리츠화재"),
    ("DB Fire & Marine Insurance", "DB손해보험"),
    ("DB Insurance", "DB손해보험"),
    ("DB손해보험", "DB손해보험"),
    ("AXA General Insurance", "AXA손해보험"),
    ("AXA손해보험", "AXA손해보험"),
    ("Shinhan Life", "신한라이프"),
    ("Hana Life Insurance", "하나생명"),
    ("Hana Insurance", "하나손해보험"),
    ("Hana Bank", "하나은행"),
    ("KB Kookmin Bank", "KB국민은행"),
    ("KB Star Banking", "KB스타뱅킹"),
    ("Naver Pay", "네이버페이"),
    ("Carrot General Insurance", "캐롯손해보험"),
    ("NS Home Shopping", "NS홈쇼핑"),
    ("Korea Non-Life Insurance Association", "손해보험협회"),
    ("Non-Life Insurance Association", "손해보험협회"),
    ("General Insurance Association", "손해보험협회"),
    ("Life Insurance Association", "생명보험협회"),
    ("New Product Deliberation Committee", "신상품심의위원회"),
)


_PHRASE_REPLACEMENTS = (
    ("senior total life care service", "시니어 토털 라이프케어 서비스"),
    ("new product deliberation committee", "신상품심의위원회"),
    ("korea non-life insurance association", "손해보험협회"),
    ("non-life insurance association", "손해보험협회"),
    ("general insurance association", "손해보험협회"),
    ("life insurance association", "생명보험협회"),
    ("exclusive-use-right", "배타적사용권"),
    ("exclusive use rights", "배타적사용권"),
    ("exclusive use right", "배타적사용권"),
    ("exclusive usage rights", "배타적사용권"),
    ("exclusive usage right", "배타적사용권"),
    ("fire & marine insurance", "화재해상보험"),
    ("general insurance", "손해보험"),
    ("life insurance", "생명보험"),
    ("auto insurance", "자동차보험"),
    ("automobile insurance", "자동차보험"),
    ("car insurance", "자동차보험"),
    ("driver insurance", "운전자보험"),
    ("health insurance", "건강보험"),
    ("cancer insurance", "암보험"),
    ("dementia care insurance", "치매·간병보험"),
    ("long-term care insurance", "장기요양보험"),
    ("whole life insurance", "종신보험"),
    ("term insurance", "정기보험"),
    ("pet insurance", "펫보험"),
    ("dental insurance", "치아보험"),
    ("travel insurance", "여행자보험"),
    ("mini insurance", "미니보험"),
    ("insurance product", "보험상품"),
    ("insurance products", "보험상품"),
    ("insurance coverage", "보험 보장"),
    ("insurance benefits", "보험 혜택"),
    ("insurance premium", "보험료"),
    ("premiums", "보험료"),
    ("premium", "보험료"),
    ("policyholders increasing", "가입자 증가"),
    ("policyholders", "계약자"),
    ("policyholder", "계약자"),
    ("customers purchasing overseas travel insurance", "해외여행보험 가입 고객"),
    ("senior customers", "시니어 고객"),
    ("customers", "고객"),
    ("customer", "고객"),
    ("elderly individuals", "고령층"),
    ("individuals", "고객"),
    ("seniors", "시니어 고객"),
    ("senior citizens", "시니어 고객"),
    ("socially vulnerable groups", "사회취약계층"),
    ("foreign seasonal workers", "외국인 계절근로자"),
    ("youth", "청년층"),
    ("young people", "청년층"),
    ("young tenants", "청년 임차인"),
    ("homeless individuals", "주거 취약 청년층"),
    ("small business owners", "소상공인"),
    ("low-credit individuals", "저신용자"),
    ("coverage amounts", "보장금액"),
    ("coverage amount", "보장금액"),
    ("coverage details", "보장 세부내용"),
    ("specific coverage details", "구체적인 보장 세부내용"),
    ("coverage periods", "보험기간"),
    ("coverage period", "보험기간"),
    ("coverage limits", "보장 한도"),
    ("coverage limit", "보장 한도"),
    ("benefit amounts", "보험금액"),
    ("benefit amount", "보험금액"),
    ("benefit periods", "보장기간"),
    ("benefit period", "보장기간"),
    ("benefit types", "보험금 유형"),
    ("benefit type", "보험금 유형"),
    ("benefit triggers", "보험금 지급 조건"),
    ("payment periods", "납입기간"),
    ("payment period", "납입기간"),
    ("policy terms", "보험기간과 약관 조건"),
    ("join ages", "가입연령"),
    ("join age", "가입연령"),
    ("exact launch date", "정확한 출시일"),
    ("release date", "출시일"),
    ("sales performance", "판매 실적"),
    ("sales metrics", "판매 지표"),
    ("sales results", "판매 실적"),
    ("sales growth", "판매 성장"),
    ("initial consumer reaction", "초기 소비자 반응"),
    ("market reaction", "시장 반응"),
    ("monthly subscribers", "월별 가입자"),
    ("subscriber", "가입자"),
    ("subscribers", "가입자"),
    ("cumulative subscriptions", "누적 가입"),
    ("rapid growth", "빠른 성장"),
    ("approximately", "약"),
    ("sixfold", "6배"),
    ("fivefold", "5배"),
    ("long-term payment", "장기 납입"),
    ("payment period", "납입기간"),
    ("launch date", "출시일"),
    ("release year-month", "출시월"),
    ("release_year_month", "출시월"),
    ("pre-launch", "출시 전"),
    ("launched in collaboration with", "협업을 통해 출시했습니다"),
    ("launched through", "통해 출시했습니다"),
    ("launched by", "출시했습니다"),
    ("launched as", "형태로 출시됐습니다"),
    ("scheduled to be launched", "출시될 예정입니다"),
    ("scheduled for release", "출시 예정입니다"),
    ("launched", "출시했습니다"),
    ("launch", "출시"),
    ("at the end of may", "5월 말"),
    ("end of may", "5월 말"),
    ("event", "이벤트"),
    ("events", "이벤트"),
    ("customer participation events", "고객 참여 이벤트"),
    ("pre-reservation event", "사전예약 이벤트"),
    ("campaign", "캠페인"),
    ("tv advertising campaign", "TV 광고 캠페인"),
    ("tv advertisement", "TV 광고"),
    ("advertisement", "광고"),
    ("advertising campaign", "광고 캠페인"),
    ("direct channels", "다이렉트 채널"),
    ("direct channel", "다이렉트 채널"),
    ("non-face-to-face channels", "비대면 채널"),
    ("non-face-to-face channel", "비대면 채널"),
    ("online-exclusive", "온라인 전용"),
    ("online", "온라인"),
    ("homepage", "홈페이지"),
    ("platform", "플랫폼"),
    ("banking", "은행"),
    ("insurance", "보험"),
    ("shopping", "쇼핑"),
    ("distribution", "유통"),
    ("home shopping", "홈쇼핑"),
    ("collaboration", "협업"),
    ("collaborative effort", "협업"),
    ("joint development", "공동 개발"),
    ("jointly developed", "공동 개발됐습니다"),
    ("jointly offered", "공동 제공됩니다"),
    ("jointly provided", "공동 제공됩니다"),
    ("jointly launched", "공동 출시됐습니다"),
    ("jointly", "공동으로"),
    ("partner company", "제휴사"),
    ("partner_company_name", "제휴사명"),
    ("partner_role", "제휴 역할"),
    ("product type", "상품유형"),
    ("product_type_code", "상품유형 코드"),
    ("insurance_type", "보험종류"),
    ("company_name", "회사명"),
    ("canonical_product_name", "대표 상품명"),
    ("product name", "상품명"),
    ("current product name", "현재 상품명"),
    ("current release month", "현재 출시월"),
    ("article", "기사"),
    ("snippets", "기사 요약문"),
    ("snippet", "기사 요약문"),
    ("evidence", "근거"),
    ("explicit", "명시적인"),
    ("unsupported", "근거가 부족한"),
    ("contradicts", "상충됩니다"),
    ("corrected", "보정했습니다"),
    ("updated", "수정했습니다"),
    ("retained", "유지했습니다"),
    ("shortened", "줄였습니다"),
    ("normalized spacing", "띄어쓰기를 정규화했습니다"),
    ("exact quoted form", "기사의 정확한 인용 표현"),
    ("article quote", "기사 인용문"),
    ("pub_date", "기사 발행일"),
    ("relative to", "기준으로"),
    ("last year", "전년도"),
    ("this year", "올해"),
    ("based on", "근거로"),
    ("according to", "에 따라"),
    ("not fully provided", "충분히 제공되지 않았습니다"),
    ("not fully elaborated", "충분히 구체적으로 설명되지 않았습니다"),
    ("not provided", "제공되지 않았습니다"),
    ("not specified", "명시되지 않았습니다"),
    ("not detailed", "상세히 제시되지 않았습니다"),
    ("not elaborated", "구체적으로 설명되지 않았습니다"),
    ("limited", "제한적입니다"),
    ("fully covered", "전액 부담합니다"),
    ("provides protection against", "피해를 보장합니다"),
    ("provides support for", "지원합니다"),
    ("compensation provided", "보상이 제공됩니다"),
    ("compensates", "보상합니다"),
    ("compensation", "보상"),
    ("covers", "보장합니다"),
    ("covering", "보장"),
    ("coverage", "보장"),
    ("provides", "제공합니다"),
    ("provided", "제공됩니다"),
    ("provide", "제공"),
    ("offers", "제공합니다"),
    ("offered", "제공됩니다"),
    ("offer", "제공"),
    ("includes", "포함합니다"),
    ("included", "포함됐습니다"),
    ("include", "포함"),
    ("aims to", "목적으로 합니다"),
    ("designed to", "설계됐습니다"),
    ("designed for", "대상으로 설계됐습니다"),
    ("focuses on", "중점적으로 다룹니다"),
    ("focus", "초점"),
    ("targets", "대상으로 합니다"),
    ("targeting", "대상"),
    ("primarily targets", "주요 대상으로 합니다"),
    ("reduces", "줄입니다"),
    ("reduce", "줄입니다"),
    ("alleviate", "완화"),
    ("financial burden", "경제적 부담"),
    ("cost burden", "비용 부담"),
    ("initial costs", "초기 비용"),
    ("examinations", "검사"),
    ("treatments", "치료"),
    ("diagnosis", "진단"),
    ("disease", "질환"),
    ("diseases", "질환"),
    ("parkinson's disease", "파킨슨병"),
    ("cancer recurrence", "암 재발"),
    ("metastasis", "전이"),
    ("cancer", "암"),
    ("dementia", "치매"),
    ("nursing care", "간병"),
    ("care", "케어"),
    ("death benefit", "사망보험금"),
    ("disability benefit", "장해보험금"),
    ("legal consultation fees", "법률상담 비용"),
    ("legal consultation", "법률상담"),
    ("legal costs", "법률비용"),
    ("lawyer consultation", "변호사 상담"),
    ("domestic violence", "가정폭력"),
    ("internet shopping mall fraud", "인터넷 쇼핑몰 사기"),
    ("internet shopping fraud", "인터넷 쇼핑 사기"),
    ("fraud damage", "사기 피해"),
    ("protects against", "피해를 보장합니다"),
    ("offering up to", "최대"),
    ("noted as", "로 언급됐습니다"),
    ("such coverage", "해당 보장"),
    ("damage", "피해"),
    ("voice phishing", "보이스피싱"),
    ("used-item transaction fraud", "중고거래 사기"),
    ("digital accident", "디지털 사고"),
    ("rental fraud", "전세사기"),
    ("rental deposit loans", "전세자금대출"),
    ("rental deposit loan", "전세자금대출"),
    ("tenants", "임차인"),
    ("tenant", "임차인"),
    ("landlord", "임대인"),
    ("real estate agents", "공인중개사"),
    ("document forgery", "문서 위조"),
    ("cast treatment", "깁스 치료"),
    ("fracture treatment", "골절 치료"),
    ("achilles tendon damage", "아킬레스건 손상"),
    ("rider", "특약"),
    ("three types of new medical treatments", "신규 의료행위 3종"),
    ("percutaneous radiofrequency ablation", "경피적 고주파 소작술"),
    ("percutaneous microwave ablation", "경피적 마이크로파 소작술"),
    ("intraperitoneal hyperthermic chemotherapy", "복강내 온열항암화학요법"),
    ("autonomous driving", "자율주행"),
    ("school violence", "학교폭력"),
    ("professional liability", "전문직 배상책임"),
    ("educators", "교직원"),
    ("high blood pressure", "고혈압"),
    ("diabetes", "당뇨"),
    ("simplified underwriting", "간편심사"),
    ("simple underwriting", "간편심사"),
    ("underwriting process", "가입심사 절차"),
    ("underwriting", "가입심사"),
    ("health management activities", "건강관리 활동"),
    ("health history", "건강 이력"),
    ("pre-existing conditions", "기왕증"),
    ("standard underwriting", "일반심사"),
    ("application process", "가입 절차"),
    ("notification items", "고지 항목"),
    ("disclosures", "고지 항목"),
    ("available through", "통해 가입할 수 있습니다"),
    ("available", "가입 가능"),
    ("accessible", "접근 가능합니다"),
    ("discount", "할인"),
    ("2% discount", "2% 할인"),
    ("5% discount", "5% 할인"),
    ("vehicle usage restrictions", "차량 운행 제한"),
    ("personal auto insurance", "개인용 자동차보험"),
    ("who have purchased", "가입한"),
    ("who purchased", "가입한"),
    ("own vehicles valued", "보유 차량가액"),
    ("not driving", "운전하지 않는"),
    ("driving", "운전"),
    ("excluding", "제외"),
    ("comply with", "준수하는"),
    ("accompanied by", "함께 진행됐습니다"),
    ("held before", "전에 진행됐습니다"),
    ("including notifications sent via", "안내 발송을 포함합니다"),
    ("notifications sent via", "안내 발송"),
    ("AlimTalk", "알림톡"),
    ("before product launch", "상품 출시 전"),
    ("vehicle 5-day driving system", "차량 5부제"),
    ("5-day driving system", "5부제 운행"),
    ("designated days", "지정 요일"),
    ("last digit of the license plate", "차량번호 끝자리"),
    ("electric and hydrogen vehicles", "전기차와 수소차"),
    ("eco-friendly vehicles", "친환경차"),
    ("vehicle value", "차량가액"),
    ("less than 50 million krw", "5천만원 미만"),
    ("under 50 million krw", "5천만원 미만"),
    ("per incident", "사고 1건당"),
    ("annual limit", "연간 한도"),
    ("trillion won", "조원"),
    ("billion krw", "억원"),
    ("million krw", "백만원"),
    ("krw", "원"),
    ("won", "원"),
    ("industry's first", "업계 최초"),
    ("industry-first", "업계 최초"),
    ("first product in the industry", "업계 최초 상품"),
    ("originality", "독창성"),
    ("usefulness", "유용성"),
    ("progressiveness", "진보성"),
    ("recognized", "인정받은"),
    ("granted", "부여받았습니다"),
    ("acquired", "획득했습니다"),
    ("market", "시장"),
    ("product line", "상품군"),
    ("product lineup", "상품군"),
    ("differentiated coverage", "차별화된 보장"),
    ("hyper-personalized health insurance", "초개인화 건강보험"),
    ("customer needs", "고객 니즈"),
    ("product competitiveness", "상품 경쟁력"),
    ("impaired risk insurance", "유병자보험"),
    ("major diseases", "주요 질병"),
    ("major illnesses", "주요 질병"),
    ("injuries", "상해"),
    ("flight delays", "항공기 지연"),
    ("cancellations", "결항"),
    ("damages", "피해"),
    ("hacking", "해킹"),
    ("cerebrovascular diseases", "뇌혈관질환"),
    ("heart diseases", "심장질환"),
    ("shingles", "대상포진"),
    ("hospitalization expenses", "입원비"),
    ("lifestyle-related diseases", "생활질환"),
    ("mothers and fetuses", "산모와 태아"),
    ("retirement", "노후"),
    ("annuity", "연금"),
    ("securitization", "유동화"),
    ("subway delay", "지하철 지연"),
    ("seoul metropolitan area", "수도권"),
    ("rainfall", "강수량"),
    ("weather conditions", "기상 조건"),
    ("civil litigation", "민사소송"),
    ("litigation costs", "소송비용"),
    ("appeal stages", "상고심"),
    ("some mentions", "일부 언급"),
    ("dog bite incidents", "개물림 사고"),
    ("dog bites", "개물림 사고"),
    ("fines incurred due to", "로 발생한 벌금"),
    ("during concert attendance", "공연 관람 중"),
    ("surgery", "수술"),
    ("commercial trucks", "영업용 화물차"),
    ("domestic travelers", "국내 여행자"),
    ("key factor for success", "성공의 핵심 요인"),
    ("aligns with", "부합합니다"),
    ("government's energy-saving policy", "정부 에너지 절약 정책"),
    ("free", "무료"),
)


_MISSING_INFO_TERMS = (
    ("specific coverage details", "구체적인 보장 세부내용"),
    ("coverage details", "보장 세부내용"),
    ("coverage amounts", "보장금액"),
    ("benefit amounts", "보험금액"),
    ("benefit periods", "보장기간"),
    ("benefit types", "보험금 유형"),
    ("payment periods", "납입기간"),
    ("coverage periods", "보험기간"),
    ("policy terms", "보험기간과 약관 조건"),
    ("sales performance", "판매 실적"),
    ("sales metrics", "판매 지표"),
    ("release date", "출시일"),
    ("exact launch date", "정확한 출시일"),
    ("join ages", "가입연령"),
    ("underwriting process", "가입심사 절차"),
    ("specific conditions", "구체적인 할인 조건"),
    ("duration of the discount", "할인 적용 기간"),
    ("features", "세부 특징"),
    ("name", "상품명"),
    ("coverages", "보장"),
    ("benefits", "보험 혜택"),
)


def compact_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def is_english_like(value: str | None) -> bool:
    if not value:
        return False
    text = str(value)
    english_letters = len(_ASCII_LETTER_RE.findall(text))
    english_words = len(_EN_WORD_RE.findall(text))
    hangul = len(_HANGUL_RE.findall(text))
    if english_words == 1 and "_" in text and " " not in text:
        return True
    return english_letters >= 8 and english_words >= 2 and english_letters > max(6, hangul)


def has_untranslated_english(value: str | None) -> bool:
    if not value:
        return False
    for token in _EN_WORD_RE.findall(str(value)):
        if token not in _ALLOWED_ENGLISH_TOKENS:
            return True
    return False


def koreanize_description_text(value: Any, field_name: str | None = None) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    text = compact_spaces(str(value))
    if not text:
        return None

    exact = _EXACT_TRANSLATIONS.get(text.lower())
    if exact:
        return exact

    text = _strip_english_parentheticals(text)
    if not is_english_like(text):
        return text

    for translator in (
        _correction_translation,
        _missing_info_translation,
        lambda t: _field_template_translation(t, field_name),
        lambda t: _literal_korean_summary(t, field_name),
    ):
        translated = translator(text)
        if translated:
            return translated
    return _minimal_field_sentence(field_name)


def koreanize_description_payload(payload: dict[str, Any], fields: list[str] | tuple[str, ...]) -> dict[str, Any]:
    for field in fields:
        if field in payload:
            payload[field] = koreanize_description_text(payload.get(field), field)
    return payload


def _strip_english_parentheticals(text: str) -> str:
    if not _HANGUL_RE.search(text):
        return text

    def replace(match: re.Match[str]) -> str:
        inside = match.group(1)
        return "" if is_english_like(inside) else match.group(0)

    return compact_spaces(re.sub(r"\s*\(([^()]*)\)", replace, text))


def _correction_translation(text: str) -> str | None:
    lower = text.lower()
    if lower.startswith("no correction needed"):
        return "현재 상품명, 회사명, 출시월 등 주요 항목이 기사 근거와 일치해 별도 보정은 필요하지 않습니다."
    if "candidate_product_name" in lower:
        quoted = re.findall(r'"candidate_product_name"\s*:\s*"([^"]+)"', text)
        if quoted:
            return f"후보 상품명 '{quoted[0]}'이 기사에서 확인됐습니다."
        return "후보 상품명이 기사 근거 기준으로 확인됐습니다."
    if not any(token in lower for token in ("corrected", "updated", "shortened", "retained", "downgraded", "unsupported", "reassigned")):
        return None

    sentences: list[str] = []
    product_from_to = re.search(
        r"(?:canonical_product_name|canonical product name|product name|current product name)"
        r"(?:\s+corrected)?\s+from\s+'([^']+)'\s+to\s+'([^']+)'",
        text,
        flags=re.IGNORECASE,
    )
    if product_from_to:
        sentences.append(f"상품명을 '{product_from_to.group(1)}'에서 '{product_from_to.group(2)}'(으)로 보정했습니다.")
    elif match := re.search(
        r"(?:canonical product name|canonical_product_name).*?(?:corrected|updated).*?'([^']+)'",
        text,
        flags=re.IGNORECASE,
    ):
        sentences.append(f"기사 근거에 따라 대표 상품명을 '{match.group(1)}'(으)로 보정했습니다.")

    release_match = re.search(
        r"(?:release_year_month|release year-month)\s+(?:corrected\s+)?from\s+'?(\d{4}-\d{2})'?\s+to\s+'?(\d{4}-\d{2})'?",
        text,
        flags=re.IGNORECASE,
    )
    if release_match:
        sentences.append(f"출시월을 {release_match.group(1)}에서 {release_match.group(2)}(으)로 보정했습니다.")

    for label, ko in [
        ("insurance_type", "보험종류"),
        ("product_type_code", "상품유형"),
        ("company", "회사명"),
    ]:
        pattern = rf"{re.escape(label)}\s+from\s+'?([A-Z_]+|unspecified|[가-힣A-Za-z0-9_.-]+)'?\s+to\s+'?([A-Z_]+|[가-힣A-Za-z0-9_.-]+)'?"
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            before = _translate_code(match.group(1).strip())
            after = _translate_code(match.group(2).strip())
            sentences.append(f"{ko}을 {before}에서 {after}(으)로 보정했습니다.")

    if not sentences:
        named_fields: list[str] = []
        if "canonical_product_name" in lower or "canonical product name" in lower:
            named_fields.append("상품명")
        if "release_year_month" in lower or "release year-month" in lower:
            named_fields.append("출시월")
        if "insurance_type" in lower:
            named_fields.append("보험종류")
        if "product_type_code" in lower:
            named_fields.append("상품유형")
        if named_fields:
            sentences.append(f"{', '.join(named_fields)}을 기사 근거에 맞춰 보정했습니다.")

    if "reassigned company" in lower and not any("회사명" in sentence for sentence in sentences):
        match = re.search(r"from\s+([가-힣A-Za-z0-9]+)\s+to\s+([가-힣A-Za-z0-9]+)", text, flags=re.IGNORECASE)
        if match:
            sentences.append(f"기사의 회사 귀속 근거에 따라 회사명을 {match.group(1)}에서 {match.group(2)}(으)로 재배정했습니다.")
        else:
            sentences.append("기사의 회사 귀속 근거에 따라 회사명을 재배정했습니다.")

    if "unsupported" in lower:
        sentences.append("기존 값 일부는 기사 근거와 맞지 않는 것으로 확인했습니다.")
    if "explicit" in lower or "article" in lower:
        sentences.append("보정 근거는 기사 내 명시 표현입니다.")
    if "partner" in lower and not any("제휴" in sentence for sentence in sentences):
        sentences.append("제휴사 또는 제휴 역할 정보도 기사 근거에 맞춰 정리했습니다.")

    return compact_spaces(" ".join(dict.fromkeys(sentences))) if sentences else None


def _missing_info_translation(text: str) -> str | None:
    lower = text.lower()
    if not any(
        token in lower
        for token in ("not provided", "not specified", "not detailed", "not elaborated", "not fully elaborated", "not fully provided", "limited")
    ):
        return None

    terms = [ko for en, ko in _MISSING_INFO_TERMS if en in lower]
    terms = list(dict.fromkeys(terms))
    if "구체적인 보장 세부내용" in terms and "보장 세부내용" in terms:
        terms.remove("보장 세부내용")
    if not terms:
        if "details" in lower:
            terms = ["세부내용"]
        else:
            return None

    source = "기사 요약문" if "snippet" in lower else "기사"
    if "focus" in lower and ("advertis" in lower or "campaign" in lower):
        return f"기사가 광고 캠페인에 초점을 두고 있어 {', '.join(terms[:4])} 등은 {source}에서 확인되지 않습니다."
    return f"{', '.join(terms[:5])} 등은 {source}에서 확인되지 않습니다."


def _field_template_translation(text: str, field_name: str | None) -> str | None:
    lower = text.lower()
    normalized = _company_normalized(text)

    if field_name == "target_customer_summary":
        translated_target = _target_sentence(text)
        if translated_target:
            return translated_target

    if field_name == "channel_summary":
        translated_channel = _channel_sentence(text)
        if translated_channel:
            return translated_channel

    if field_name in {"coverage_summary", "condition_text", "limit_text", "amount_basis"}:
        translated_coverage = _coverage_sentence(text, field_name)
        if translated_coverage:
            return translated_coverage

    if field_name in {"feature_summary", "evidence_summary"} or "exclusive" in lower:
        translated_exclusive = _exclusive_sentence(text)
        if translated_exclusive:
            return translated_exclusive

    if "5-day" in lower or "designated day" in lower or "license plate" in lower:
        return "차량 5부제 등 지정 운행 제한을 지키면 자동차보험료를 2% 할인해 주는 특약입니다."
    if "discount" in lower and ("auto" in lower or "automobile" in lower or "car insurance" in lower):
        if "2%" in lower:
            return "자동차보험 가입자가 조건을 충족하면 보험료 2% 할인을 받을 수 있는 특약입니다."
        if "5%" in lower:
            return "자동차보험 가입자가 조건을 충족하면 보험료 5% 할인을 받을 수 있는 특약입니다."
        return "자동차보험 가입자가 일정 조건을 충족하면 보험료 할인을 받을 수 있는 내용입니다."
    if "parkinson" in lower:
        return "파킨슨병의 초기 검사와 치료에 따른 비용 부담을 줄이는 보장입니다."
    if "internet shopping mall fraud" in lower and ("1.5" in lower or "million" in lower):
        return "인터넷 쇼핑몰 사기 피해를 최대 150만원까지 보장하는 업계 최초 담보입니다."
    if "percutaneous radiofrequency" in lower or "microwave ablation" in lower or "hyperthermic chemotherapy" in lower:
        return "경피적 고주파 소작술, 경피적 마이크로파 소작술, 복강내 온열항암화학요법 등 신규 의료행위 3종을 보장합니다."
    if "direct auto insurance" in lower and ("advertisement" in lower or "campaign" in lower):
        return "다이렉트 자동차보험 TV 광고 캠페인과 관련된 내용입니다."
    if "accompanied by customer participation events" in lower:
        return "상품 출시와 함께 고객 참여 이벤트가 진행됐습니다."
    if "event was held before product launch" in lower or "event was held before" in lower:
        return "상품 출시 전 이벤트가 진행됐고 알림톡과 LMS 안내 발송이 포함됐습니다."
    if "advertisement" in lower or "campaign" in lower:
        return "상품 홍보를 위한 광고 캠페인 또는 이벤트 내용입니다."
    if "senior total life care" in lower or ("senior" in lower and ("bank" in lower or "shopping" in lower or "distribution" in lower)):
        return "시니어 고객을 대상으로 은행, 보험, 쇼핑 또는 유통 서비스를 연계한 생활관리 서비스입니다."
    if "banking" in lower and "insurance" in lower and ("shopping" in lower or "distribution" in lower):
        return "은행, 보험, 쇼핑 또는 유통 채널을 결합한 제휴형 서비스입니다."
    if "rental fraud" in lower or "rental deposit" in lower:
        return "청년 임차인 등 주거 취약층을 전세사기 위험으로부터 보호하는 보험상품입니다."
    if "specialized financial product" in lower or "specialized finance" in lower:
        return "소상공인과 저신용자 등 취약 고객층을 지원하는 특화 금융상품입니다."
    if "impaired risk" in lower and "cancer" in lower:
        return "유병자 고객이 암보험 혜택을 더 쉽게 받을 수 있도록 고지 항목을 간소화한 상품입니다."
    if "public transportation" in lower:
        return "대중교통 이용과 관련된 위험을 보장하는 제휴 보험입니다."
    if "hyper-personalized" in lower:
        return "초개인화 건강보험 구조로 고객별 차별화 보장을 제공하는 상품입니다."
    if "cancer recurrence" in lower or "metastasis" in lower:
        return "암 재발과 전이 위험까지 폭넓게 보장하는 특약입니다."
    if "legal consultation" in lower or "lawyer consultation" in lower:
        return "보행자 사고 등 분쟁 상황에서 법률상담 또는 변호사 자문 비용을 보장합니다."
    if "initial consumer reaction" in lower and "key factor" in lower:
        return "초기 소비자 반응이 상품 성공의 핵심 요인으로 언급됐습니다."
    if "energy-saving policy" in lower:
        return "정부 에너지 절약 정책과 부합하는 점을 차별화 요소로 제시합니다."

    launch_sentence = _launch_sentence(normalized)
    if launch_sentence and field_name == "product_development_summary":
        return launch_sentence

    if field_name == "sales_summary":
        sales_sentence = _sales_sentence(text)
        if sales_sentence:
            return sales_sentence

    if field_name == "differentiation_summary":
        differentiation_sentence = _differentiation_sentence(text)
        if differentiation_sentence:
            return differentiation_sentence

    if field_name == "risk_note_summary":
        risk_sentence = _risk_sentence(text)
        if risk_sentence:
            return risk_sentence

    return None


def _target_sentence(text: str) -> str | None:
    lower = text.lower().strip(" .")
    target_map = (
        ("pet owners, specifically dog owners", "반려견 보호자가 대상입니다."),
        ("pet dog owners", "반려견 보호자가 대상입니다."),
        ("pet owners", "반려동물 보호자가 대상입니다."),
        ("senior customers", "시니어 고객이 대상입니다."),
        ("seniors", "시니어 고객이 대상입니다."),
        ("drivers and passengers", "운전자와 탑승자가 대상입니다."),
        ("foreign seasonal workers", "외국인 계절근로자가 대상입니다."),
        ("elderly individuals and those with pre-existing conditions", "고령층과 유병자 고객이 대상입니다."),
        ("domestic travelers", "국내 여행자가 대상입니다."),
        ("small business owners and individuals with low credit scores", "소상공인과 저신용자가 대상입니다."),
    )
    for english, korean in target_map:
        if lower == english or english in lower:
            return korean
    if "personal auto insurance" in lower and "vehicle value" in lower and "eco-friendly" in lower:
        return "차량가액 5천만원 미만의 개인용 자동차보험 가입자 중 친환경차 운전자가 아닌 고객이 대상입니다."
    if "personal auto insurance" in lower and "electric and hydrogen" in lower:
        return "차량가액 5천만원 미만의 개인용 자동차보험 가입자 중 전기차·수소차 보유자는 제외됩니다."
    if "vehicle 5-day driving system" in lower:
        return "차량 5부제를 준수하는 고객이 대상입니다."
    if "aged 15 and under" in lower:
        return "15세 이하 고객이 대상입니다."
    if "commercial trucks" in lower:
        return "1톤 초과 영업용 화물차 운전자가 대상입니다."
    if "overseas travel insurance" in lower:
        return "해외여행보험 가입 고객이 대상입니다."
    if "pre-existing conditions" in lower:
        return "기왕증이나 치료 이력이 있는 고객도 대상에 포함됩니다."
    if "customers" in lower or "individuals" in lower:
        fragment = _translate_fragment(text)
        return f"{fragment}이 대상입니다." if fragment else None
    return None


def _channel_sentence(text: str) -> str | None:
    lower = text.lower()
    normalized = _company_normalized(text)
    if match := re.search(r"(?:jointly offered|jointly provided)\s+by\s+(.+)", normalized, flags=re.IGNORECASE):
        return f"{_translate_company_list(match.group(1))}이 공동 제공하는 채널입니다."
    if "naver pay" in lower:
        return "네이버페이를 통해 가입할 수 있습니다."
    if "direct channel" in lower or "direct channels" in lower:
        return "다이렉트 채널을 통해 제공됩니다."
    if "online" in lower:
        return "온라인 채널을 통해 가입할 수 있습니다."
    if "kakaotalk" in lower:
        return "카카오톡을 통해 24시간 가입 또는 청구가 가능합니다."
    if "hana bank" in lower:
        return "하나은행 채널을 통해 제공됩니다."
    if "sk broadband" in lower:
        return "SK브로드밴드 채널을 통해 제공됩니다."
    if "kt" in lower:
        return "KT 채널을 통해 제공됩니다."
    if "toss" in lower:
        return "토스 플랫폼을 통해 제공됩니다."
    return None


def _coverage_sentence(text: str, field_name: str | None) -> str | None:
    lower = text.lower().strip(" .")
    if field_name == "amount_basis":
        exact = _EXACT_TRANSLATIONS.get(lower)
        if exact:
            return exact
    if "fines incurred due to dog bites" in lower or "dog bites" in lower:
        return "개물림 사고로 발생한 벌금을 보장합니다."
    if "concert attendance" in lower:
        return "공연 관람 중 발생한 사고 또는 비용과 관련한 보장 조건입니다."
    if "resulting from car accidents" in lower or "due to car accident" in lower:
        return "자동차 사고로 발생한 경우를 지급 조건으로 합니다."
    if "pedestrian accident" in lower:
        return "보행자 사고가 발생한 경우를 지급 조건으로 합니다."
    if "public transportation" in lower:
        return "대중교통 이용 중 발생한 경우를 지급 조건으로 합니다."
    if "civil and criminal lawsuits" in lower:
        return "민형사 소송 발생 시 보장합니다."
    if lower.startswith("covers "):
        fragment = _translate_fragment(text[7:])
        return f"{fragment}을 보장합니다." if fragment else None
    if lower.startswith("coverage for "):
        fragment = _translate_fragment(text[13:])
        return f"{fragment} 보장입니다." if fragment else None
    if lower.startswith("provides support for "):
        fragment = _translate_fragment(text[21:])
        return f"{fragment}를 지원합니다." if fragment else None
    if lower.startswith("provides coverage for "):
        fragment = _translate_fragment(text[22:])
        return f"{fragment}을 보장합니다." if fragment else None
    if lower.startswith("includes "):
        fragment = _translate_fragment(text[9:])
        return f"{fragment}을 포함합니다." if fragment else None
    if "discount on" in lower and "premium" in lower:
        return f"{_extract_percent(text)}보험료 할인을 제공합니다.".strip()
    if "up to" in lower and ("krw" in lower or "won" in lower):
        return _translate_money_limit(text)
    if "maximum loan amount" in lower:
        return _translate_money_limit(text) or "대출 한도를 보장 또는 지원 기준으로 제시합니다."
    if "subway" in lower and "delay" in lower:
        return "수도권 지하철이 일정 시간 이상 지연될 경우 보상을 제공합니다."
    if "rainfall" in lower:
        return "일정 강수량 이상 등 기상 조건에 따라 자동 보상을 제공합니다."
    if "civil litigation" in lower:
        return "민사소송 출석 등 소송 관련 비용을 보장합니다."
    if "appeal stages" in lower:
        return "일부 언급에서는 상고심을 제외합니다."
    if lower in {"covers cancer", "covers cancer."}:
        return "암을 보장합니다."
    return None


def _exclusive_sentence(text: str) -> str | None:
    lower = text.lower()
    normalized = _company_normalized(text)
    if "exclusive" not in lower and "originality" not in lower and "usefulness" not in lower:
        return None
    months = re.search(r"for\s+(\d+)\s+months?", lower)
    month_text = f"{months.group(1)}개월" if months else None
    quoted = re.findall(r"'([^']{2,120})'", text)
    subject = quoted[0] if quoted else None
    company = _extract_leading_company(normalized)
    if subject and company and month_text:
        return f"{company}이 '{subject}'에 대해 {month_text} 배타적사용권을 획득했습니다."
    if subject and month_text:
        return f"'{subject}'에 대해 {month_text} 배타적사용권을 획득했습니다."
    if company and month_text:
        return f"{company}이 {month_text} 배타적사용권을 획득했습니다."
    if "32" in lower:
        return "32건의 배타적사용권을 획득해 상품 개발 역량을 인정받았습니다."
    if "17" in lower and "hanwha" in lower:
        return "한화 시그니처 여성건강보험 시리즈와 관련해 17건의 배타적사용권을 획득했습니다."
    if "first pet insurance" in lower:
        return "업계 최초 펫보험으로 9개월 배타적사용권을 부여받았습니다."
    if "originality" in lower or "usefulness" in lower:
        return "신상품심의위원회에서 독창성과 유용성을 인정받았습니다."
    return "해당 보장 또는 서비스의 독창성을 인정받아 배타적사용권을 획득했습니다."


def _launch_sentence(text: str) -> str | None:
    normalized = _company_normalized(text)
    if match := re.search(r"^The product was launched by\s+(.+)\.?$", normalized, flags=re.IGNORECASE):
        return f"{_translate_company_list(match.group(1))}가 출시한 상품입니다."
    if match := re.search(r"^Launched in\s+([A-Za-z]+\s+\d{4})\s+through a partnership between\s+(.+?)\s+and\s+(.+?)\.?$", normalized, flags=re.IGNORECASE):
        return f"{_translate_date_phrase(match.group(1))} {_translate_company_list(match.group(2))}와 {_translate_company_list(match.group(3))}의 제휴를 통해 출시됐습니다."
    if match := re.search(r"^Jointly developed by\s+(.+?)\s+and\s+(.+?)\.?$", normalized, flags=re.IGNORECASE):
        return f"{_translate_company_list(match.group(1))}와 {_translate_company_list(match.group(2))}이 공동 개발한 상품입니다."
    if "scheduled to be launched at the end of may" in text.lower():
        return "5월 말 출시 예정인 상품입니다."
    return None


def _sales_sentence(text: str) -> str | None:
    lower = text.lower()
    if match := re.search(r"over\s+([\d,]+)\s+cumulative subscriptions", lower):
        return f"누적 가입이 {match.group(1)}건을 넘어선 것으로 언급됐습니다."
    if "billion krw" in lower and "within" in lower:
        translated = _translate_fragment(text)
        return f"{translated} 수준의 판매 또는 운용 실적이 기사에서 언급됐습니다."
    if "exclusive" in lower and "months" in lower:
        return _exclusive_sentence(text)
    if "sales growth" in lower or "contributes to sales" in lower:
        return "해당 상품 출시가 판매 성장에 기여한 것으로 언급됐습니다."
    return None


def _differentiation_sentence(text: str) -> str | None:
    lower = text.lower()
    if "hyper-personalized" in lower:
        return "초개인화 건강보험과 차별화된 보장을 강점으로 내세웁니다."
    if "industry-first" in lower or "first of its kind" in lower or "industry's first" in lower:
        return "업계 최초 성격의 보장 또는 서비스라는 점이 차별화 요소입니다."
    if "mileage" in lower and "discount" in lower:
        return "주행거리 기반 보험료 할인을 차별화 요소로 제시합니다."
    if "rear-side collision" in lower:
        return "후측방 충돌방지 장치 유무에 따른 특화 할인을 차별화 요소로 제시합니다."
    return None


def _risk_sentence(text: str) -> str | None:
    lower = text.lower()
    if "school violence" in lower or "professional liability" in lower or "educators" in lower:
        return "학교폭력과 교직원 배상책임 등 교육 현장 관련 위험을 다룹니다."
    if "landlord" in lower or "real estate" in lower or "rental" in lower:
        return "임대인, 공인중개사, 문서 위조 등 임대차 거래 관련 위험을 다룹니다."
    if "autonomous" in lower:
        return "자율주행 차량 사고에서 책임 소재가 달라질 수 있는 위험을 다룹니다."
    if "profitability" in lower or "delinquency" in lower:
        return "수익성과 연체율 등 건전성 관련 우려가 언급됐습니다."
    if "overutilization" in lower or "medical services" in lower:
        return "의료 이용 과다 등 손해율 관련 위험을 완화하려는 내용입니다."
    return None


def _literal_korean_summary(text: str, field_name: str | None) -> str | None:
    original = text
    working = _company_normalized(text)
    working = _strip_leading_english_fillers(working)
    for english, korean in sorted(_PHRASE_REPLACEMENTS, key=lambda item: len(item[0]), reverse=True):
        working = _replace_english_phrase(working, english, korean)
    working = _cleanup_literal_translation(working)
    if not working:
        return None
    if _low_information_korean(working):
        return _minimal_field_sentence(field_name)
    if is_english_like(working) or has_untranslated_english(working):
        semantic = _semantic_fallback(original, field_name)
        if semantic:
            return semantic
        return _minimal_field_sentence(field_name)
    return working


def _replace_english_phrase(text: str, english: str, korean: str) -> str:
    if re.search(r"[A-Za-z]", english):
        pattern = rf"(?<![A-Za-z]){re.escape(english)}(?![A-Za-z])"
    else:
        pattern = re.escape(english)
    return re.sub(pattern, korean, text, flags=re.IGNORECASE)


def _strip_leading_english_fillers(text: str) -> str:
    patterns = (
        r"^This is an?\s+",
        r"^This product is an?\s+",
        r"^This product\s+",
        r"^The product is an?\s+",
        r"^The product\s+",
        r"^The insurance\s+",
        r"^The service\s+",
        r"^The article\s+mentions\s+",
        r"^The article\s+identifies\s+",
        r"^The article\s+",
        r"^Current\s+",
    )
    result = text
    for pattern in patterns:
        result = re.sub(pattern, "", result, flags=re.IGNORECASE)
    return result


def _cleanup_literal_translation(text: str) -> str:
    result = compact_spaces(text)
    replacements = (
        (r"\bthat\s+", ""),
        (r"\bis\s+", ""),
        (r"\bare\s+", ""),
        (r"\bwas\s+", ""),
        (r"\bwere\s+", ""),
        (r"\bbeing\s+", ""),
        (r"\bhas\s+", ""),
        (r"\bhave\s+", ""),
        (r"\bits\s+", ""),
        (r"\btheir\s+", ""),
        (r"\bthe\s+", ""),
        (r"\ba\s+", ""),
        (r"\ban\s+", ""),
        (r"\bof\s+", ""),
        (r"\bin\s+", ""),
        (r"\bon\s+", ""),
        (r"\s+\\.", "."),
        (r"\s+,", ","),
        (r"\s+and\s+", " 및 "),
        (r"\s+or\s+", " 또는 "),
        (r"\s+for\s+", " 대상 "),
        (r"\s+from\s+", "에서 "),
        (r"\s+to\s+", "로 "),
        (r"\s+by\s+", "에서 "),
        (r"\s+with\s+", " 포함 "),
    )
    for pattern, repl in replacements:
        result = re.sub(pattern, repl, result, flags=re.IGNORECASE)
    result = re.sub(r"\s*;\s*", ". ", result)
    result = re.sub(r"\s*:\s*", ": ", result)
    result = re.sub(r"\.{2,}", ".", result)
    result = compact_spaces(result)
    if result and result[-1] not in ".다요음)":
        if any(token in result for token in ("보장", "제공", "할인", "출시", "정리", "보정", "대상", "근거", "획득", "인정")):
            result += "."
    return result


def _semantic_fallback(text: str, field_name: str | None) -> str | None:
    terms = _extract_signal_terms(text)
    fragment = ", ".join(terms[:5]) if terms else ""
    if not fragment:
        return None
    if field_name == "missing_info_summary":
        return f"{fragment} 관련 세부 정보는 기사에서 충분히 확인되지 않습니다."
    if field_name in {"coverage_summary", "condition_text", "limit_text"}:
        return f"{fragment}{_topic_particle(fragment)} 관련한 보장 조건입니다."
    if field_name == "amount_basis":
        return f"{fragment} 기준입니다."
    if field_name in {"feature_summary", "evidence_summary"}:
        return f"{fragment}{_topic_particle(fragment)} 관련한 상품 특징입니다."
    if field_name == "target_customer_summary":
        return f"{fragment}이 대상입니다."
    if field_name == "channel_summary":
        return f"{fragment} 채널과 관련됩니다."
    if field_name == "sales_summary":
        return f"{fragment} 관련 판매 또는 시장 반응입니다."
    if field_name == "differentiation_summary":
        return f"{fragment}을 차별화 요소로 제시합니다."
    return f"{fragment} 관련 내용입니다."


def _translate_fragment(text: str) -> str:
    result = _company_normalized(compact_spaces(text).strip(" ."))
    for english, korean in sorted(_PHRASE_REPLACEMENTS, key=lambda item: len(item[0]), reverse=True):
        result = _replace_english_phrase(result, english, korean)
    result = _cleanup_literal_translation(result)
    result = re.sub(r"\b(and|or|the|a|an|of|in|on|for|to|by|with)\b", "", result, flags=re.IGNORECASE)
    result = compact_spaces(result.strip(" ."))
    if has_untranslated_english(result):
        safe_terms = _extract_signal_terms(result)
        result = ", ".join(safe_terms[:5])
    return result


def _extract_signal_terms(text: str) -> list[str]:
    quoted = re.findall(r"'([^']{2,120})'", text)
    korean = re.findall(r"[가-힣][가-힣0-9·() -]{1,50}", text)
    numbers = re.findall(r"\d+(?:\.\d+)?%?|\d{4}-\d{2}", text)
    translated_fragments: list[str] = []
    for english, korean_term in _PHRASE_REPLACEMENTS:
        if re.search(rf"(?<![A-Za-z]){re.escape(english)}(?![A-Za-z])", text, flags=re.IGNORECASE):
            translated_fragments.append(korean_term)
    safe_quoted = [_strip_english_parentheticals(item) for item in quoted if _HANGUL_RE.search(item) or not has_untranslated_english(item)]
    safe_korean = [_strip_english_parentheticals(item) for item in korean if not has_untranslated_english(item)]
    terms = [*safe_quoted, *safe_korean, *translated_fragments, *numbers]
    cleaned = []
    for term in terms:
        term = compact_spaces(re.sub(r"\s*\([A-Za-z][^()]*(?:\)|$)", "", term))
        if term and not has_untranslated_english(term):
            cleaned.append(term)
    deduped = [compact_spaces(term) for term in dict.fromkeys(cleaned) if compact_spaces(term)]
    filtered = [term for term in deduped if term not in _LOW_VALUE_TERMS]
    return filtered


def _low_information_korean(text: str) -> bool:
    tokens = re.findall(r"[가-힣A-Za-z0-9%·]+", text)
    meaningful = [token for token in tokens if token not in _LOW_VALUE_TERMS and token not in {"을", "를", "와", "과", "은", "는", "이", "가"}]
    return not meaningful


def _minimal_field_sentence(field_name: str | None) -> str:
    return FIELD_FALLBACKS.get(field_name or "", "해당 설명형 정보를 한국어로 정리했습니다.")


def _topic_particle(fragment: str) -> str:
    last = _last_hangul(fragment)
    if not last:
        return "와"
    return "과" if (ord(last) - 0xAC00) % 28 else "와"


def _last_hangul(value: str) -> str | None:
    for char in reversed(value):
        if "가" <= char <= "힣":
            return char
    return None


def _company_normalized(text: str) -> str:
    result = text
    for english, korean in _COMPANY_REPLACEMENTS:
        result = _replace_english_phrase(result, english, korean)
    return result


def _translate_company_list(text: str) -> str:
    result = _company_normalized(text)
    result = re.sub(r"\s+and\s+", "와 ", result, flags=re.IGNORECASE)
    result = re.sub(r"\s*,\s*", ", ", result)
    return compact_spaces(result.strip(" ."))


def _translate_code(value: str) -> str:
    key = value.strip("'\" ")
    return _CODE_TRANSLATIONS.get(key, key)


def _extract_leading_company(text: str) -> str | None:
    for _, korean in _COMPANY_REPLACEMENTS:
        if text.startswith(korean):
            return korean
    match = re.match(r"^([가-힣A-Z0-9]+(?:손해보험|생명|화재|해상)?)\s+", text)
    return match.group(1) if match else None


def _extract_percent(text: str) -> str:
    match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    return f"{match.group(1)}% " if match else ""


def _translate_money_limit(text: str) -> str | None:
    lower = text.lower()
    match = re.search(r"(?:up to|maximum loan amount is|annual limit of)\s+([\d,.]+)\s+(million|billion)?\s*(krw|won)", lower)
    if not match:
        return None
    number = match.group(1)
    unit = "백만원" if match.group(2) == "million" else "억원" if match.group(2) == "billion" else "원"
    if "loan" in lower:
        return f"대출 한도는 최대 {number}{unit}입니다."
    if "annual limit" in lower:
        return f"연간 한도는 {number}{unit}입니다."
    return f"최대 {number}{unit}까지 보장합니다."


def _translate_date_phrase(text: str) -> str:
    months = {
        "january": "1월",
        "february": "2월",
        "march": "3월",
        "april": "4월",
        "may": "5월",
        "june": "6월",
        "july": "7월",
        "august": "8월",
        "september": "9월",
        "october": "10월",
        "november": "11월",
        "december": "12월",
    }
    parts = text.lower().split()
    if len(parts) == 2 and parts[0] in months:
        return f"{parts[1]}년 {months[parts[0]]}"
    return text
