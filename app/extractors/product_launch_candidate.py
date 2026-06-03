from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass


NEGATIVE_PRODUCT_NAME_PATTERNS = [
    "신한SOL",
    "신한 SOL",
    "신한SOL 다이렉트",
    "신한 SOL 다이렉트",
    "신한SOL EZ손보",
    "신한 SOL EZ손보",
    "쏠Drive",
    "쏠드라이브",
    "쏠Walk",
    "쏠워크",
    "삼성 인터넷",
    "삼성인터넷",
    "삼성생명 다이렉트",
    "삼성생명다이렉트",
    "다이렉트",
    "모바일 앱",
    "앱",
    "플랫폼",
    "서비스",
    "할인",
    "할인 구조",
    "보험료 할인",
    "이벤트",
    "네이버페이",
    "포인트",
    "계좌이체",
    "걷기",
    "안전운전",
]

LAUNCH_TRIGGERS = [
    "신규 출시했다",
    "신규 출시",
    "출시했다",
    "출시",
    "선보였다고",
    "선보였다",
    "선보여",
    "내놨다",
    "내놓았다",
]


@dataclass(frozen=True)
class ProductLaunchCandidate:
    raw_name: str
    normalized_name: str
    evidence_text: str
    trigger: str
    confidence: float
    candidate_type: str


def extract_launch_product_candidates(text: str | None) -> list[ProductLaunchCandidate]:
    if not text:
        return []
    normalized_text = _clean_text(text)
    candidates: list[ProductLaunchCandidate] = []
    for sentence in _sentences(normalized_text):
        if not _contains_launch_trigger(sentence):
            continue
        candidates.extend(_quoted_candidates(sentence))
        candidates.extend(_unquoted_candidates(sentence))

    deduped: dict[str, ProductLaunchCandidate] = {}
    for candidate in sorted(candidates, key=lambda item: item.confidence, reverse=True):
        if is_negative_product_name(candidate.normalized_name):
            continue
        deduped.setdefault(candidate.normalized_name, candidate)
    return list(deduped.values())


def best_launch_candidate(text: str | None) -> ProductLaunchCandidate | None:
    candidates = extract_launch_product_candidates(text)
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: item.confidence, reverse=True)[0]


def is_negative_product_name(name: str | None) -> bool:
    normalized = _compact(_strip_product_noise(name))
    if not normalized:
        return False
    negative_compacts = {_compact(pattern) for pattern in NEGATIVE_PRODUCT_NAME_PATTERNS}
    if normalized in negative_compacts:
        return True
    if "보험" in normalized and not _service_name_with_insurance_suffix(normalized):
        return False
    return any(normalized == pattern or normalized.startswith(pattern) for pattern in negative_compacts)


def normalize_launch_product_name(name: str | None) -> str | None:
    cleaned = _strip_product_noise(name)
    if not cleaned:
        return None
    for pattern in sorted(NEGATIVE_PRODUCT_NAME_PATTERNS, key=len, reverse=True):
        cleaned = re.sub(rf"^\s*{re.escape(pattern)}\s+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned or is_negative_product_name(cleaned):
        return None
    if "보험" not in cleaned:
        return None
    return cleaned


def _quoted_candidates(sentence: str) -> list[ProductLaunchCandidate]:
    found: list[ProductLaunchCandidate] = []
    pattern = re.compile(r"[\"'“”‘’]([^\"'“”‘’]{1,80})[\"'“”‘’](.{0,80}?)(" + "|".join(map(re.escape, LAUNCH_TRIGGERS)) + r")")
    for match in pattern.finditer(sentence):
        raw = match.group(1)
        trigger = match.group(3)
        normalized = normalize_launch_product_name(raw)
        if not normalized:
            continue
        found.append(
            ProductLaunchCandidate(
                raw_name=raw.strip(),
                normalized_name=normalized,
                evidence_text=sentence.strip(),
                trigger=trigger,
                confidence=0.96,
                candidate_type="quoted_launch_sentence",
            )
        )
    return found


def _unquoted_candidates(sentence: str) -> list[ProductLaunchCandidate]:
    found: list[ProductLaunchCandidate] = []
    trigger_union = "|".join(map(re.escape, LAUNCH_TRIGGERS))
    pattern = re.compile(r"([가-힣A-Za-z0-9·\s]{2,50}?보험)\s*(?:을|를|도|은|는|으로|로)?\s*(.{0,30}?)(" + trigger_union + r")")
    for match in pattern.finditer(sentence):
        raw = _trim_to_last_product_name(match.group(1))
        trigger = match.group(3)
        normalized = normalize_launch_product_name(raw)
        if not normalized:
            continue
        found.append(
            ProductLaunchCandidate(
                raw_name=raw.strip(),
                normalized_name=normalized,
                evidence_text=sentence.strip(),
                trigger=trigger,
                confidence=0.9,
                candidate_type="unquoted_launch_sentence",
            )
        )
    return found


def _clean_text(text: str) -> str:
    value = unicodedata.normalize("NFKC", html.unescape(text))
    value = re.sub(r"<[^>]+>", " ", value)
    value = value.replace("\r", "\n")
    value = re.sub(r"[ \t]+", " ", value)
    return value.strip()


def _sentences(text: str) -> list[str]:
    chunks = re.split(r"(?<=[.!?。])\s+|\n+", text)
    return [chunk.strip() for chunk in chunks if chunk.strip()]


def _contains_launch_trigger(sentence: str) -> bool:
    return any(trigger in sentence for trigger in LAUNCH_TRIGGERS)


def _strip_product_noise(name: str | None) -> str:
    if not name:
        return ""
    value = unicodedata.normalize("NFKC", html.unescape(str(name)))
    value = re.sub(r"<[^>]+>", " ", value)
    value = value.strip(" \t\r\n\"'“”‘’[](){}<>")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _compact(value: str | None) -> str:
    return re.sub(r"\s+", "", (value or "").lower())


def _service_name_with_insurance_suffix(compacted: str) -> bool:
    service_prefixes = {
        _compact("신한SOL 다이렉트"),
        _compact("신한 SOL 다이렉트"),
        _compact("신한SOL EZ손보"),
        _compact("신한 SOL EZ손보"),
    }
    return any(compacted.startswith(prefix) for prefix in service_prefixes)


def _trim_to_last_product_name(value: str) -> str:
    parts = re.split(r"[,，]|(?:\s+및\s+)|(?:\s+또는\s+)|(?:\s+함께\s+)", value)
    candidate = parts[-1].strip() if parts else value.strip()
    match = re.search(r"([가-힣A-Za-z0-9·\s]{2,40}?보험)$", candidate)
    return match.group(1).strip() if match else candidate
