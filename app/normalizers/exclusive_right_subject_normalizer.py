from __future__ import annotations

import json
import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any

from app.utils.text import compact_spaces, normalize_search_key


TOKEN_RE = re.compile(r"[가-힣A-Za-z0-9]{2,}")
COMPONENT_SPLIT_RE = re.compile(r"\s*(?:,|·|/|\+| 및 | 그리고 | 등 | 와 | 과 )\s*")

SUBJECT_STOPWORDS = {
    "보험",
    "상품",
    "특약",
    "담보",
    "보장",
    "서비스",
    "제도",
    "급부",
    "배타적사용권",
    "배타적",
    "사용권",
    "획득",
    "부여",
    "인정",
    "개월",
    "신상품",
    "해당",
    "이번",
    "관련",
    "여성",
}

WEAK_CANONICAL_KEYS = {
    normalize_search_key(value)
    for value in {
        "상품",
        "해당 상품",
        "신상품",
        "보험",
        "특약",
        "서비스",
        "법률 관련 상품 및 서비스",
        "여성 보험",
        "여성보험",
        "시그니처 여성보험 4.0",
        "한화 시그니처 여성 건강보험 4.0 신규 법률 담보 및 서비스",
    }
}

BRAND_CONTEXT_KEYS = {
    normalize_search_key(value)
    for value in {
        "시그니처 여성보험 4.0",
        "여성 건강보험 시그니처 시리즈",
        "한화 시그니처 여성 건강보험 4.0",
    }
}


def normalize_exclusive_subject_name(subject_name: str | None) -> str:
    value = unicodedata.normalize("NFKC", compact_spaces(subject_name))
    value = value.strip(" \t\r\n'\"“”‘’[]()")
    value = re.sub(r"\s+", " ", value)
    return value


def split_exclusive_subject_components(subject_name: str | None) -> list[str]:
    subject = normalize_exclusive_subject_name(subject_name)
    if not subject:
        return []
    components: list[str] = []
    for part in COMPONENT_SPLIT_RE.split(subject):
        normalized = compact_spaces(part)
        if normalized:
            components.append(normalized)
    return components or [subject]


def normalize_exclusive_component(component: str | None) -> str:
    value = normalize_search_key(unicodedata.normalize("NFKC", component or ""))
    value = value.replace("법률비용담보", "법률비용")
    value = value.replace("법률비용보장", "법률비용")
    value = value.replace("상담서비스", "상담")
    value = value.replace("변호사상담서비스", "변호사상담")
    value = value.replace("lady", "")
    return value


def build_exclusive_subject_tokens(*values: str | None) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        for match in TOKEN_RE.findall(value or ""):
            key = normalize_search_key(match)
            if len(key) >= 2 and key not in SUBJECT_STOPWORDS:
                tokens.add(key)
    return tokens


def exclusive_subject_component_set(subject_name: str | None, aliases: list[str] | None = None, evidence_text: str | None = None) -> set[str]:
    components: set[str] = set()
    for source in [subject_name, *(aliases or [])]:
        for component in split_exclusive_subject_components(source):
            key = normalize_exclusive_component(component)
            if len(key) >= 2 and key not in WEAK_CANONICAL_KEYS:
                components.add(key)
    if not components and evidence_text:
        components.update(build_exclusive_subject_tokens(evidence_text))
    return components


def component_set_overlap(left_components: set[str], right_components: set[str]) -> float:
    if not left_components or not right_components:
        return 0.0
    matched = 0
    used: set[str] = set()
    for left in left_components:
        for right in right_components:
            if right in used:
                continue
            if _component_match(left, right):
                matched += 1
                used.add(right)
                break
    return matched / max(1, min(len(left_components), len(right_components)))


def is_component_superset_event(left_components: set[str], right_components: set[str]) -> bool:
    return component_set_overlap(left_components, right_components) >= 0.999


def build_exclusive_event_signature(event_or_observation: Any) -> dict[str, Any]:
    aliases = _json_load(getattr(event_or_observation, "alias_names_json", None))
    subject_name = getattr(event_or_observation, "subject_name", None) or getattr(event_or_observation, "raw_subject_name", None)
    evidence_text = getattr(event_or_observation, "evidence_text", None)
    return {
        "company_id": getattr(event_or_observation, "company_id", None),
        "company_name_normalized": getattr(event_or_observation, "company_name_normalized", None),
        "insurance_type": getattr(event_or_observation, "insurance_type", None),
        "exclusivity_months": getattr(event_or_observation, "exclusivity_months", None),
        "acquired_year_month": getattr(event_or_observation, "acquired_year_month", None),
        "subject_tokens": build_exclusive_subject_tokens(subject_name, *(aliases or [])),
        "component_tokens": exclusive_subject_component_set(subject_name, aliases, evidence_text),
        "evidence_tokens": build_exclusive_subject_tokens(evidence_text, getattr(event_or_observation, "feature_summary", None)),
        "alias_tokens": build_exclusive_subject_tokens(*(aliases or [])),
    }


def exclusive_event_similarity(left: Any, right: Any) -> dict[str, float]:
    left_sig = build_exclusive_event_signature(left)
    right_sig = build_exclusive_event_signature(right)
    left_subject = getattr(left, "subject_name", None) or ""
    right_subject = getattr(right, "subject_name", None) or ""
    return {
        "subject_overlap": _jaccard(left_sig["subject_tokens"], right_sig["subject_tokens"]),
        "component_overlap": component_set_overlap(left_sig["component_tokens"], right_sig["component_tokens"]),
        "evidence_overlap": _jaccard(left_sig["evidence_tokens"], right_sig["evidence_tokens"]),
        "alias_overlap": _jaccard(left_sig["alias_tokens"], right_sig["alias_tokens"]),
        "name_similarity": _similarity(left_subject, right_subject),
    }


def exclusive_subject_compatible(left: Any, right: Any) -> bool:
    scores = exclusive_event_similarity(left, right)
    if _insurance_company_conflict(left, right):
        return False
    if _period_conflict(left, right):
        return False
    return (
        scores["subject_overlap"] >= 0.55
        or scores["component_overlap"] >= 0.55
        or scores["evidence_overlap"] >= 0.50
        or scores["name_similarity"] >= 0.82
    )


def is_allowed_canonical_exclusive_subject(subject_name: str | None) -> bool:
    key = normalize_search_key(subject_name)
    if not key or key in WEAK_CANONICAL_KEYS or key in BRAND_CONTEXT_KEYS:
        return False
    if len(key) < 4:
        return False
    if key.endswith("시그니처여성보험40") or "시그니처여성건강보험40" in key:
        return False
    return True


def canonical_subject_score(subject_name: str | None, evidence_text: str | None = None, aliases: list[str] | None = None) -> tuple[int, int, int]:
    subject = normalize_exclusive_subject_name(subject_name)
    components = exclusive_subject_component_set(subject, aliases, evidence_text)
    tokens = build_exclusive_subject_tokens(subject)
    score = 0
    if is_allowed_canonical_exclusive_subject(subject):
        score += 100
    if any(suffix in subject for suffix in ("보험", "특약", "서비스", "제도", "담보")):
        score += 20
    score += min(30, len(components) * 8)
    score += min(20, len(tokens) * 4)
    if "특약" in subject:
        score += 5
    if normalize_search_key(subject) in BRAND_CONTEXT_KEYS:
        score -= 80
    return (score, len(components), len(normalize_search_key(subject)))


def _component_match(left: str, right: str) -> bool:
    if not left or not right:
        return False
    if left == right or left in right or right in left:
        return True
    left_tokens = set(TOKEN_RE.findall(left))
    right_tokens = set(TOKEN_RE.findall(right))
    if left_tokens and right_tokens and len(left_tokens & right_tokens) / min(len(left_tokens), len(right_tokens)) >= 0.5:
        return True
    return SequenceMatcher(None, left, right).ratio() >= 0.74


def _similarity(left: str | None, right: str | None) -> float:
    left_key = normalize_search_key(left)
    right_key = normalize_search_key(right)
    if not left_key or not right_key:
        return 0.0
    return SequenceMatcher(None, left_key, right_key).ratio()


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _insurance_company_conflict(left: Any, right: Any) -> bool:
    left_company = getattr(left, "company_id", None)
    right_company = getattr(right, "company_id", None)
    return bool(left_company and right_company and left_company != right_company)


def _period_conflict(left: Any, right: Any) -> bool:
    left_months = getattr(left, "exclusivity_months", None)
    right_months = getattr(right, "exclusivity_months", None)
    return bool(left_months is not None and right_months is not None and left_months != right_months)


def _json_load(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        payload = json.loads(value)
        return [str(item) for item in payload if item]
    except json.JSONDecodeError:
        return []
