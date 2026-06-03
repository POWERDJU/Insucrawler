from __future__ import annotations

import re
from typing import Any


COMMON_CRAWL_QUERIES = [
    "보험 신상품",
    "보험상품 출시",
    "보험 출시",
    "보험사 신상품",
    "생명보험 신상품",
    "생명보험 상품 출시",
    "손해보험 신상품",
    "손해보험 상품 출시",
    "장기보험 신상품",
    "장기보험 출시",
    "보장성보험 신상품",
    "보장성보험 출시",
]

PRODUCT_GROUP_CRAWL_QUERIES = [
    "건강보험 출시",
    "암보험 출시",
    "실손보험 출시",
    "운전자보험 출시",
    "자동차보험 출시",
    "간편보험 출시",
    "유병자보험 출시",
    "치매보험 출시",
    "간병보험 출시",
    "어린이보험 출시",
    "어른이보험 출시",
    "치아보험 출시",
    "펫보험 출시",
    "반려동물보험 출시",
    "여행자보험 출시",
    "연금보험 출시",
    "종신보험 출시",
    "정기보험 출시",
    "변액보험 출시",
    "보증보험 출시",
]

COMPANY_CRAWL_QUERY_TEMPLATES = [
    "{company} 신상품",
    "{company} 보험 출시",
    "{company} 보험상품 출시",
    "{company} 상품 출시",
    "{company} 장기보험",
    "{company} 보장성보험",
    "{company} 다이렉트 보험",
    "{company} 무배당 보험",
    "{company} 새롭게 선보",
    "{company} 출시했다",
    "{company} 선보였다",
]

COMPANY_PRODUCT_QUERY_TERMS = [
    "건강보험",
    "건강보험 출시",
    "여성 건강보험",
    "암보험",
    "암보험 출시",
    "운전자보험",
    "운전자보험 출시",
    "간편보험",
    "유병자보험",
    "어린이보험",
    "치매보험",
    "간병보험",
    "실손보험",
    "자동차보험",
    "치아보험",
    "펫보험",
    "여행자보험",
    "연금보험",
    "종신보험",
    "면역질환보험",
]

EXCLUSIVE_RIGHT_COMMON_QUERIES = [
    "보험 배타적사용권",
    "보험 배타적 사용권",
    "보험업계 배타적사용권",
    "배타적사용권 획득 보험",
    "배타적사용권 부여 보험",
    "신상품심의위원회 보험",
    "신상품 심의위원회 보험",
    "생명보험 배타적사용권",
    "손해보험 배타적사용권",
    "보험사 배타적사용권",
    "보험 신상품 배타적사용권",
]


EXCLUSIVE_RIGHT_COMPANY_QUERY_TEMPLATES = [
    "{company} 배타적사용권",
    "{company} 배타적 사용권",
    "{company} 신상품심의위원회",
    "{company} 신상품 심의위원회",
    "{company} 배타적사용권 획득",
    "{company} 배타적사용권 부여",
    "{company} 독창성 인정",
]


MONTH_KEYWORD_PATTERNS = [
    re.compile(r"\b20\d{2}\s*년\s*(?:0?[1-9]|1[0-2])\s*월\b"),
    re.compile(r"\b20\d{2}\.(?:0[1-9]|1[0-2])\b"),
    re.compile(r"\b20\d{2}-(?:0[1-9]|1[0-2])\b"),
]


def has_month_keyword(query_text: str) -> bool:
    return any(pattern.search(query_text or "") for pattern in MONTH_KEYWORD_PATTERNS)


def append_unique_query(
    queries: list[dict[str, Any]],
    seen: set[str],
    *,
    query_group: str,
    query_text: str,
    **metadata: Any,
) -> bool:
    if not query_text or query_text in seen:
        return False
    if has_month_keyword(query_text):
        return False
    seen.add(query_text)
    queries.append({"query_group": query_group, "query_text": query_text, **metadata})
    return True
