from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from app.utils.text import compact_spaces, normalize_search_key, strip_html


VERSION_DOT_PLACEHOLDER = "\ue000"
VERSION_PATTERN = re.compile(
    r"(?:\bv\s*\d+(?:\.\d+)?\b|\b\d+\.\d+\b|\b\d+\s*세대\b)",
    re.IGNORECASE,
)
FAMILY_TOKEN_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"tontine|톤\s*틴", "톤틴"),
    (r"우리\s*won|우리\s*원|won", "우리won"),
    (r"건강\s*환급", "건강환급"),
    (r"전신\s*마취\s*수술|전신\s*마취|마취\s*수술", "전신마취수술"),
    (r"시그니처|signature", "시그니처"),
    (r"여성", "여성"),
    (r"환급", "환급"),
    (r"연금", "연금"),
    (r"암", "암"),
    (r"치매", "치매"),
    (r"mri|자기공명영상", "mri"),
    (r"전통\s*시장", "전통시장"),
    (r"날씨\s*피해", "날씨피해"),
    (r"전이\s*암", "전이암"),
    (r"미리\s*받는\s*서비스|미리받는서비스", "미리받는서비스"),
)
FAMILY_NOISE_TERMS = {
    "무배당",
    "무",
    "갱신형",
    "비갱신형",
    "해약환급금",
    "해지환급금",
    "미지급형",
    "일부지급형",
    "원금보장형",
    "플랜",
    "상품",
    "보험",
    "보험상품",
    "신상품",
    "다이렉트",
    "온라인",
    "전용",
    "한국형",
    "형",
    "납입",
    "특약보험료",
    "보험료",
}
FAMILY_NOISE_TERMS_ORDERED = sorted(FAMILY_NOISE_TERMS, key=len, reverse=True)
GENERIC_FAMILY_SIGNATURES = {
    "연금",
    "환급",
    "암",
    "치매",
    "건강",
    "건강보험",
    "암보험",
    "보험",
    "상품",
    "건강",
    "종합",
}
DEFAULT_IDENTITY_RULES = {
    "company_stem_suffixes": ["손해보험", "생명보험", "생명", "화재", "손보"],
    "channel_prefixes": ["삼성 인터넷", "삼성인터넷", "삼성 다이렉트", "삼성다이렉트", "인터넷", "다이렉트"],
    "legal_noise_terms": ["무배당", "무 배당", "보험상품", "보험 상품"],
    "optional_leading_modifiers": ["신간편", "크루", "CREW", "HI", "하이", "NEW", "뉴", "더", "The", "시그니처", "Signature"],
    "anchor_required_leading_modifiers": ["HI", "하이", "NEW", "뉴", "더", "The", "시그니처", "Signature"],
    "optional_class_before_version": ["건강보험"],
    "generic_loose_keys": ["보험", "건강보험", "암보험", "실손보험", "자동차보험", "운전자보험", "간편보험", "치아보험", "펫보험", "여행자보험", "연금보험", "종신보험", "정기보험", "상품"],
}

CLEAN_FAMILY_TOKEN_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"톤\s*틴|tontine", "톤틴"),
    (r"우리\s*won", "우리won"),
    (r"건강\s*환급", "건강환급"),
    (r"전신\s*마취\s*수술", "전신마취수술"),
    (r"시그니처|signature", "시그니처"),
    (r"여성", "여성"),
    (r"스텝\s*업\s*700|스텝업\s*700|step\s*up\s*700", "스텝업700"),
    (r"금쪽\s*같은", "금쪽같은"),
    (r"펫", "펫"),
    (r"mri|자기\s*공명\s*영상", "mri"),
    (r"전통\s*시장", "전통시장"),
    (r"날씨\s*피해", "날씨피해"),
    (r"미리\s*받는\s*서비스", "미리받는서비스"),
)
CLEAN_FAMILY_NOISE_TERMS = {
    "무배당",
    "무",
    "갱신형",
    "비갱신형",
    "보험",
    "보험상품",
    "상품",
    "건강",
    "종합",
    "보장",
    "플랜",
    "라이트",
    "온라인",
    "전용",
    "고객",
    "대상",
    "위한",
    "납입",
    "특약보험료",
    "보험료",
    "해주는",
    "해지",
    "사망",
    "일부지급형",
    "nh",
}
CLEAN_GENERIC_FAMILY_SIGNATURES = {
    "보험",
    "상품",
    "건강",
    "건강보험",
    "종합",
    "연금",
    "연금보험",
    "환급",
    "펫",
    "펫보험",
    "종신",
    "종신보험",
}


@dataclass(frozen=True)
class ProductNameValidationResult:
    accepted: bool
    cleaned_name: str
    reason: str = ""


WEAK_PRODUCT_NAME_EXACTS = {
    "해당상품",
    "해당특약",
    "해당서비스",
    "이번상품",
    "이번보험",
    "이번특약",
    "이번서비스",
    "이상품",
    "이보험",
    "신상품",
    "종합보험",
    "보험상품",
    "상품",
    "보험",
    "특약",
    "담보",
    "서비스",
    "구조",
    "보장",
    "할인",
    "할인특약",
}
BAD_PRODUCT_NAME_FRAGMENTS = {
    "지키면보험",
    "다만건강보험",
}
BAD_PRODUCT_NAME_PREFIXES = {
    "다만",
}


def _guard_compact(value: str | None) -> str:
    return re.sub(r"[^0-9A-Za-z\uac00-\ud7a3]+", "", unicodedata.normalize("NFKC", value or "")).casefold()


def clean_product_name_candidate(name: str | None, company_aliases: list[str] | None = None) -> str:
    cleaned = normalize_product_name(name, company_aliases)
    cleaned = re.sub(r"^[,.;:·\-\s]+|[,.;:·\-\s]+$", "", cleaned)
    return compact_spaces(cleaned)


def is_bad_product_name_fragment(name: str | None) -> bool:
    compact = _guard_compact(name)
    if not compact:
        return True
    if compact in BAD_PRODUCT_NAME_FRAGMENTS:
        return True
    if any(fragment in compact for fragment in BAD_PRODUCT_NAME_FRAGMENTS):
        return True
    if any(compact.startswith(prefix) and "보험" in compact for prefix in BAD_PRODUCT_NAME_PREFIXES):
        return True
    return False


def is_generic_or_weak_product_name(name: str | None) -> bool:
    compact = _guard_compact(name)
    if not compact:
        return True
    if compact in WEAK_PRODUCT_NAME_EXACTS:
        return True
    if re.fullmatch(r"(해당|이번|이|신규?)?(상품|보험|특약|담보|서비스|구조|보장)", compact):
        return True
    if len(compact) < 4 and not re.search(r"[A-Za-z0-9]", compact):
        return True
    tokens = build_product_family_tokens(name)
    if not tokens and compact.endswith(("보험", "특약", "담보", "서비스", "상품")):
        return len(compact) <= 6
    return False


def validate_product_name_before_save(
    raw_product_name: str | None,
    article_title: str | None = None,
    evidence_text: str | None = None,
    context_text: str | None = None,
    company_aliases: list[str] | None = None,
) -> ProductNameValidationResult:
    cleaned = clean_product_name_candidate(raw_product_name, company_aliases)
    if is_bad_product_name_fragment(cleaned):
        return ProductNameValidationResult(False, cleaned, "bad_sentence_fragment")
    if is_generic_or_weak_product_name(cleaned):
        return ProductNameValidationResult(False, cleaned, "weak_or_generic_product_name")
    compact = _guard_compact(cleaned)
    if len(compact) < 4:
        return ProductNameValidationResult(False, cleaned, "too_short_product_name")

    source_text = "\n".join(item for item in [evidence_text, context_text] if item)
    if source_text:
        source_compact = _guard_compact(source_text)
        title_compact = _guard_compact(article_title)
        if compact not in source_compact and compact in title_compact:
            return ProductNameValidationResult(False, cleaned, "article_title_only_without_extraction_context")
    return ProductNameValidationResult(True, cleaned, "")


@lru_cache(maxsize=1)
def _identity_rules() -> dict[str, list[str]]:
    config_path = Path(__file__).resolve().parents[2] / "config" / "product_name_identity_rules.yaml"
    loaded: dict[str, list[str]] = {}
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        if isinstance(raw, dict):
            for key, value in raw.items():
                if isinstance(value, list):
                    loaded[key] = [str(item) for item in value if str(item).strip()]
    merged: dict[str, list[str]] = {}
    for key, default_values in DEFAULT_IDENTITY_RULES.items():
        merged[key] = list(dict.fromkeys([*default_values, *loaded.get(key, [])]))
    return merged


def _rule_list(name: str) -> list[str]:
    return _identity_rules().get(name, [])


def _base_text(value: str | None) -> str:
    text = unicodedata.normalize("NFKC", html.unescape(strip_html(value)))
    text = re.sub(r"[\u2018\u2019\u201c\u201d\"'`]", "", text)
    text = re.sub(r"[·ㆍ•\[\]{}()<>]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _alias_variants(company_aliases: list[str] | None) -> list[str]:
    variants: set[str] = set()
    for alias in company_aliases or []:
        cleaned = _base_text(alias)
        if cleaned:
            variants.add(cleaned)
            variants.add(re.sub(r"\s+", "", cleaned))
            compact = re.sub(r"\s+", "", cleaned)
            for suffix in _rule_list("company_stem_suffixes"):
                if compact.endswith(suffix) and len(compact) > len(suffix) + 1:
                    variants.add(compact[: -len(suffix)])
    return sorted(variants, key=len, reverse=True)


def remove_company_aliases(raw_product_name: str | None, company_aliases: list[str] | None) -> str:
    text = _base_text(raw_product_name)
    for alias in _alias_variants(company_aliases):
        if not alias:
            continue
        text = re.sub(re.escape(alias), " ", text, flags=re.IGNORECASE)
    text = _remove_channel_prefixes(text)
    return compact_spaces(text)


def normalize_product_name(name: str | None, company_aliases: list[str] | None = None) -> str:
    text = remove_company_aliases(name, company_aliases)
    text = re.sub(r"[·ㆍ•]", " ", text)
    text = re.sub(r"\s+(보험|공제)", r"\1", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" -_/.,")


def normalize_product_name_core(raw_product_name: str | None, company_aliases: list[str] | None = None) -> str:
    text = normalize_product_name(raw_product_name, company_aliases)
    for alias in _alias_variants(company_aliases):
        alias_key = _core_key(alias)
        if alias_key:
            text = _core_key(text).replace(alias_key, "")
    return _core_key(text)


def product_core_key_candidates(raw_product_name: str | None, company_aliases: list[str] | None = None) -> list[str]:
    """Return strict and conservative fallback identity keys for one product name.

    The first key preserves the normalized product name. Later keys only remove
    channel/prefix noise that is often omitted by news snippets.
    """
    normalized = normalize_product_name(raw_product_name, company_aliases)
    text_variants = _identity_text_variants(normalized)
    candidates: list[str] = []
    for variant in text_variants:
        candidates.append(normalize_product_name_core(variant, company_aliases))
        for without_optional_class in _strip_optional_class_before_version(variant):
            if without_optional_class != variant:
                candidates.append(normalize_product_name_core(without_optional_class, company_aliases))
    return [item for item in dict.fromkeys(candidates) if _is_safe_candidate_key(item)]


def build_product_identity_key(company_id: int | None, raw_product_name: str | None, company_aliases: list[str] | None = None) -> str | None:
    if company_id is None:
        return None
    core_key = normalize_product_name_core(raw_product_name, company_aliases)
    if not core_key:
        return None
    return f"company:{company_id}|product:{core_key}"


def product_search_key(name: str | None, company_name: str | None = None) -> str:
    return normalize_search_key(f"{company_name or ''}{name or ''}")


def normalize_product_family_signature(raw_product_name: str | None, company_aliases: list[str] | None = None) -> str:
    """Return a broad deterministic signature for product consolidation.

    This is intentionally looser than ``product_core_key``. It is only used for
    blocking/merge decisions, never for exact upsert.
    """
    tokens = build_product_family_tokens(raw_product_name, company_aliases)
    version = version_signature(raw_product_name)
    if not tokens:
        return ""

    ordered = _ordered_family_tokens(tokens)
    signature = "".join(ordered)
    if signature in GENERIC_FAMILY_SIGNATURES or signature in CLEAN_GENERIC_FAMILY_SIGNATURES:
        return ""
    if version:
        signature = f"{signature}|v:{','.join(sorted(version))}"
    return signature


def build_product_family_tokens(raw_product_name: str | None, company_aliases: list[str] | None = None) -> set[str]:
    text = _family_base_text(raw_product_name, company_aliases)
    tokens: set[str] = set()
    for pattern, token in (*FAMILY_TOKEN_PATTERNS, *CLEAN_FAMILY_TOKEN_PATTERNS):
        if re.search(pattern, text, flags=re.IGNORECASE):
            tokens.add(token)

    for raw_token in re.findall(r"[0-9A-Za-z\uac00-\ud7a3]+", text):
        token = _normalize_family_token(raw_token)
        if not token or token in FAMILY_NOISE_TERMS or token in CLEAN_FAMILY_NOISE_TERMS or token in GENERIC_FAMILY_SIGNATURES or token in CLEAN_GENERIC_FAMILY_SIGNATURES:
            continue
        if any(known in token and known != token for known in tokens):
            continue
        if tokens and not _family_token_is_informative(token):
            continue
        if len(token) < 2:
            continue
        tokens.add(token)

    if "우리won" in tokens:
        tokens.add("won")
    if "건강환급" in tokens:
        tokens.add("환급")
    if "톤틴" in tokens and "tontine" in tokens:
        tokens.discard("tontine")
    return tokens


def version_signature(raw_product_name: str | None) -> set[str]:
    versions: set[str] = set()
    for match in VERSION_PATTERN.finditer(raw_product_name or ""):
        value = match.group(0).lower().replace(" ", "")
        value = value.replace("세대", "세대")
        versions.add(value)
    return versions


def is_generic_product_family_signature(signature: str | None) -> bool:
    if not signature:
        return True
    base = signature.split("|v:", 1)[0]
    return base in GENERIC_FAMILY_SIGNATURES or base in CLEAN_GENERIC_FAMILY_SIGNATURES or len(base) < 4


def _core_key(value: str | None) -> str:
    text = _base_text(value)
    text = re.sub(r"(?<=\d)\.(?=\d)", VERSION_DOT_PLACEHOLDER, text)
    text = re.sub(r"[^0-9A-Za-z\uac00-\ud7a3\ue000]+", "", text)
    text = text.replace(VERSION_DOT_PLACEHOLDER, ".")
    return text.casefold()


def _family_base_text(raw_product_name: str | None, company_aliases: list[str] | None = None) -> str:
    text = unicodedata.normalize("NFKC", html.unescape(strip_html(raw_product_name)))
    text = text.casefold()
    text = re.sub(r"tontine", "톤틴", text, flags=re.IGNORECASE)
    text = re.sub(r"우리\s*원", "우리won", text)
    text = re.sub(r"우리\s*won", "우리won", text, flags=re.IGNORECASE)
    text = remove_company_aliases(text, company_aliases)
    for alias in _alias_variants(company_aliases):
        text = re.sub(re.escape(alias.casefold()), " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"\[[^\]]*\]", " ", text)
    for term in FAMILY_NOISE_TERMS_ORDERED:
        text = re.sub(re.escape(term), " ", text, flags=re.IGNORECASE)
    for term in sorted(CLEAN_FAMILY_NOISE_TERMS, key=len, reverse=True):
        text = re.sub(rf"(?<![0-9A-Za-z?-?]){re.escape(term)}(?![0-9A-Za-z?-?])", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"[^0-9A-Za-z\uac00-\ud7a3.]+", " ", text)
    return compact_spaces(text)


def _normalize_family_token(token: str) -> str:
    token = token.casefold().strip()
    token = re.sub(r"tontine", "톤틴", token, flags=re.IGNORECASE)
    token = re.sub(r"우리won|우리원", "우리won", token, flags=re.IGNORECASE)
    token = re.sub(r"(보험상품|보험|상품|플랜|전용|온라인|다이렉트)$", "", token)
    if re.fullmatch(r"\d+(?:일|월|개월|만원|원|위)?", token):
        return ""
    return token.strip()


def _family_token_is_informative(token: str) -> bool:
    if token in GENERIC_FAMILY_SIGNATURES or token in CLEAN_GENERIC_FAMILY_SIGNATURES or token in FAMILY_NOISE_TERMS or token in CLEAN_FAMILY_NOISE_TERMS:
        return False
    if len(token) <= 2 and not re.search(r"[A-Za-z0-9]", token):
        return False
    descriptive_noise = {"사망", "해지", "일부지급", "지급", "납입", "납입특약", "특약보험료", "보험료", "해주는", "보장", "형", "배당"}
    return token not in descriptive_noise


def _ordered_family_tokens(tokens: set[str]) -> list[str]:
    preferred = [
        "우리won",
        "won",
        "시그니처",
        "여성",
        "톤틴",
        "건강환급",
        "전신마취수술",
        "연금",
        "환급",
        "암",
        "치매",
        "mri",
        "전통시장",
        "날씨피해",
        "전이암",
        "미리받는서비스",
    ]
    result = [token for token in preferred if token in tokens]
    result.extend(sorted(token for token in tokens if token not in set(preferred)))
    if "우리won" in result and "won" in result:
        result.remove("won")
    if "건강환급" in result and "환급" in result:
        result.remove("환급")
    return result


def _remove_channel_prefixes(text: str) -> str:
    cleaned = text
    for pattern in _rule_list("channel_prefixes"):
        compact_pattern = r"\s*".join(re.escape(part) for part in re.split(r"\s+", pattern.strip()) if part)
        cleaned = re.sub(rf"^\s*{compact_pattern}\s+", " ", cleaned, flags=re.IGNORECASE)
    return cleaned


def _strip_leading_optional_modifier(value: str) -> str:
    text = compact_spaces(value)
    changed = True
    while changed:
        changed = False
        for modifier in _rule_list("optional_leading_modifiers"):
            next_text = re.sub(rf"^\s*{re.escape(modifier)}\s+", "", text, flags=re.IGNORECASE)
            next_text = compact_spaces(next_text)
            if next_text != text:
                text = next_text
                changed = True
    return compact_spaces(text)


def _strip_optional_class_before_version(value: str) -> list[str]:
    text = compact_spaces(value)
    variants: list[str] = []
    for term in _rule_list("optional_class_before_version"):
        spaced_term = r"\s*".join(re.escape(char) for char in term)
        pattern = re.compile(
            rf"(?P<prefix>.+?)(?P<class>{spaced_term})\s+(?P<version>{VERSION_PATTERN.pattern})\s*$",
            re.IGNORECASE,
        )
        match = pattern.match(text)
        if not match:
            continue
        prefix = compact_spaces(match.group("prefix"))
        if len(_core_key(prefix)) < 2:
            continue
        variants.append(compact_spaces(f"{prefix} {match.group('version')}"))
    return variants


def _identity_text_variants(normalized: str) -> list[str]:
    variants = [compact_spaces(normalized)]
    queue = list(variants)
    while queue:
        text = queue.pop(0)
        next_candidates = [_strip_identity_noise(text), *_strip_leading_optional_modifier_variants(text)]
        for next_text in next_candidates:
            next_text = compact_spaces(next_text)
            if next_text and next_text not in variants:
                variants.append(next_text)
                queue.append(next_text)
    return variants


def _strip_identity_noise(value: str) -> str:
    text = compact_spaces(value)
    for term in _rule_list("legal_noise_terms"):
        text = _remove_phrase(text, term)
    text = re.sub(r"(^|\s)무(?=\s|$)", " ", text)
    return compact_spaces(text)


def _strip_leading_optional_modifier_variants(value: str) -> list[str]:
    text = compact_spaces(value)
    variants: list[str] = []
    changed = True
    while changed:
        changed = False
        for modifier in _rule_list("optional_leading_modifiers"):
            next_text = re.sub(rf"^\s*{re.escape(modifier)}\s+", "", text, flags=re.IGNORECASE)
            next_text = compact_spaces(next_text)
            if next_text != text and _can_strip_leading_modifier(modifier, next_text):
                variants.append(next_text)
                text = next_text
                changed = True
                break
    return variants


def _remove_phrase(value: str, phrase: str) -> str:
    parts = [part for part in re.split(r"\s+", phrase.strip()) if part]
    if not parts:
        return value
    flexible = r"\s*".join(re.escape(part) for part in parts)
    return re.sub(flexible, " ", value, flags=re.IGNORECASE)


def _can_strip_leading_modifier(modifier: str, remainder: str) -> bool:
    anchor_required = {_core_key(item) for item in _rule_list("anchor_required_leading_modifiers")}
    if _core_key(modifier) not in anchor_required:
        return True
    return _has_identity_anchor(remainder)


def _has_identity_anchor(value: str) -> bool:
    text = compact_spaces(value)
    return bool(VERSION_PATTERN.search(text) or re.search(r"[A-Za-z0-9]", text))


def _is_safe_candidate_key(key: str) -> bool:
    if not key or len(key) < 4:
        return False
    generic_keys = {_core_key(item) for item in _rule_list("generic_loose_keys")}
    if key in generic_keys:
        return False
    return True
