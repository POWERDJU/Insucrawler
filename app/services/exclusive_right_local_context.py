from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re

from app.db.models import FactArticle
from app.utils.text import compact_spaces, normalize_search_key


EXCLUSIVE_CONTEXT_KEYWORDS = (
    "배타적사용권",
    "배타적 사용권",
    "독점사용권",
    "독점 사용권",
    "신상품심의위원회",
    "신상품 심의위원회",
    "부여",
    "획득",
    "승인",
    "인정받",
)
ACQUIRED_CONTEXT_KEYWORDS = ("획득", "부여", "부여받", "취득", "승인", "인정", "인정받", "받았다")

GENERIC_WEAK_SUBJECTS = (
    "상품",
    "보험",
    "특약",
    "담보",
    "서비스",
    "제도",
    "구조",
    "신상품",
    "보험상품",
    "해당 상품",
    "이번 상품",
    "이 상품",
    "해당 보험",
    "이번 보험",
    "이 보험",
    "해당 특약",
    "이번 특약",
    "해당 서비스",
    "이번 서비스",
    "급부보험",
    "사망 보장 상품",
    "보장 특약",
    "특화 상품",
    "배타적사용권",
    "배타적 사용권",
    "배타적사용권 대상 미확인",
)
WEAK_SUBJECT_KEYS = {normalize_search_key(value) for value in GENERIC_WEAK_SUBJECTS}

BAD_SUBJECT_FRAGMENTS = (
    "개발해",
    "개발하여",
    "개발",
    "출시",
    "출시해",
    "출시하여",
    "선보여",
    "선보여",
    "손해보험협회",
    "손해 보험협회",
    "손해 보험 협회",
    "생명보험협회",
    "생명 보험협회",
    "생명 보험 협회",
    "신상품심의위원회",
    "신상품 심의위원회",
    "협회로부터",
    "협회",
    "로부터",
    "통해",
    "받아",
    "받았",
    "인정받",
    "부여받",
    "획득했",
    "획득",
    "배타적사용권",
    "배타적 사용권",
)
BAD_TAIL_SPLIT_RE = re.compile(
    r"\s*(?:"
    r"개발해|개발하여|출시해|출시하여|선보여|"
    r"손해\s*보험\s*협회|생명\s*보험\s*협회|신상품\s*심의위원회|"
    r"협회로부터|협회|로부터|통해|받아|받았|인정받|부여받|획득했|획득|배타적\s*사용권"
    r").*$"
)

GENERIC_PREFIX_RE = re.compile(r"^(?:신규|새로운|해당|이번|이)\s+")
SUBJECT_SUFFIXES = ("보험", "특약", "서비스", "제도", "담보", "급부방식")
QUOTE_CHARS = "'\"‘’“”"
TOKEN_RE = re.compile(r"[가-힣A-Za-z0-9]{2,}")


@dataclass(frozen=True)
class ExclusiveRightContextWindow:
    window_text: str
    evidence_text: str
    previous_text: str
    sentence_index: int


@dataclass(frozen=True)
class SubjectCandidate:
    name: str
    source: str
    score: int = 0
    evidence: str | None = None


@dataclass(frozen=True)
class SubjectValidationResult:
    subject_name: str | None
    status: str
    needs_review: bool
    reason: str
    original_subject_name: str | None = None

    @property
    def ok(self) -> bool:
        return self.status in {"pass", "resolved"}

    @property
    def resolved_subject_name(self) -> str | None:
        return self.subject_name


def extract_exclusive_right_context_windows(
    article_text: str | None,
    *,
    title: str | None = None,
    description: str | None = None,
    context_sentences: int = 3,
) -> list[ExclusiveRightContextWindow]:
    text = "\n".join(part for part in [description, article_text] if part)
    sentences = _split_sentences(text)
    windows: list[ExclusiveRightContextWindow] = []
    for index, sentence in enumerate(sentences):
        if not any(keyword in sentence for keyword in EXCLUSIVE_CONTEXT_KEYWORDS):
            continue
        start = max(0, index - context_sentences)
        end = min(len(sentences), index + context_sentences + 1)
        previous = " ".join(sentences[start:index])
        window = " ".join(sentences[start:end])
        windows.append(
            ExclusiveRightContextWindow(
                window_text=compact_spaces(window),
                evidence_text=compact_spaces(sentence),
                previous_text=compact_spaces(previous),
                sentence_index=index,
            )
        )
    if not windows and (title or description or article_text):
        fallback = compact_spaces("\n".join(part for part in [title, description, article_text] if part))
        windows.append(ExclusiveRightContextWindow(fallback, fallback[:500], "", 0))
    return windows


def select_best_exclusive_context_window(
    subject_name: str | None,
    evidence_text: str | None,
    full_text: str | None,
    *,
    article_title: str | None = None,
    article_description: str | None = None,
    company_name: str | None = None,
    exclusivity_months: int | None = None,
) -> ExclusiveRightContextWindow | None:
    windows = extract_exclusive_right_context_windows(
        full_text,
        title=article_title,
        description=article_description,
    )
    if not windows:
        return None
    scored = [
        (
            score_exclusive_context_window(
                window,
                subject_name=subject_name,
                evidence_text=evidence_text,
                company_name=company_name,
                exclusivity_months=exclusivity_months,
                article_title=article_title,
            ),
            window,
        )
        for window in windows
    ]
    return sorted(scored, key=lambda item: (-item[0], item[1].sentence_index))[0][1]


def score_exclusive_context_window(
    window: ExclusiveRightContextWindow | str,
    *,
    subject_name: str | None = None,
    evidence_text: str | None = None,
    company_name: str | None = None,
    exclusivity_months: int | None = None,
    article_title: str | None = None,
) -> int:
    window_text = window.window_text if isinstance(window, ExclusiveRightContextWindow) else str(window or "")
    score = 0
    window_key = normalize_search_key(window_text)
    evidence = compact_spaces(evidence_text)
    evidence_key = normalize_search_key(evidence)
    subject = compact_spaces(subject_name)
    subject_key = normalize_search_key(subject)
    company_key = normalize_search_key(company_name)
    title_key = normalize_search_key(article_title)

    if evidence and (evidence in window_text or (evidence_key and evidence_key in window_key)):
        score += 5
    elif evidence_key and _token_overlap(evidence_key, window_key):
        score += 2

    if subject_key and subject_key in window_key:
        score += 4
    elif subject_key and _subject_token_overlap(subject, window_text):
        score += 3

    if company_key and company_key in window_key:
        score += 3

    if exclusivity_months is not None and re.search(rf"{int(exclusivity_months)}\s*개월", window_text):
        score += 3
    elif re.search(r"(?:3|6|9|12|18)\s*개월", window_text):
        score += 2

    if any(keyword in window_text for keyword in EXCLUSIVE_CONTEXT_KEYWORDS):
        score += 3
    if any(keyword in window_text for keyword in ACQUIRED_CONTEXT_KEYWORDS):
        score += 2

    if subject_key and subject_key in title_key and subject_key not in window_key:
        score -= 5
    if is_generic_or_weak_subject(subject) or has_bad_subject_tail(subject):
        score -= 5
    return score


def validate_exclusive_subject_before_save(
    subject_name: str | None,
    *,
    evidence_text: str | None,
    window_text: str | None,
    article_title: str | None = None,
) -> SubjectValidationResult:
    return validate_exclusive_subject_quality(
        subject_name,
        evidence_text=evidence_text,
        window_text=window_text,
        article_title=article_title,
    )


def validate_exclusive_subject_quality(
    subject_name: str | None,
    evidence_text: str | None,
    window_text: str | None,
    article_title: str | None = None,
) -> SubjectValidationResult:
    original = compact_spaces(subject_name)
    window = compact_spaces(window_text)
    evidence = compact_spaces(evidence_text)
    candidate = clean_exclusive_subject_candidate(original)

    if is_generic_or_weak_subject(candidate) or not candidate:
        resolved = resolve_subject_reference(candidate, window, evidence, article_title=article_title)
        if resolved:
            return SubjectValidationResult(resolved, "resolved", False, "weak_subject_resolved", original)
        reason = "missing_subject" if not candidate else "weak_subject_without_resolved_reference"
        return SubjectValidationResult(None, "rejected", True, reason, original)

    if has_bad_subject_tail(original):
        resolved = resolve_subject_reference(candidate, window, evidence, article_title=article_title)
        if resolved and normalize_search_key(resolved) != normalize_search_key(candidate):
            return SubjectValidationResult(resolved, "resolved", False, "bad_subject_tail_resolved", original)
        if has_bad_subject_tail(candidate) or is_generic_or_weak_subject(candidate):
            return SubjectValidationResult(None, "rejected", True, "bad_subject_tail_unresolved", original)

    weak_reference_conflict = _weak_reference_type_conflict(candidate, f"{window} {evidence}")
    if weak_reference_conflict:
        return SubjectValidationResult(candidate, "review", True, weak_reference_conflict, original)

    subject_key = normalize_search_key(candidate)
    window_key = normalize_search_key(window)
    evidence_key = normalize_search_key(evidence)
    title_key = normalize_search_key(article_title)
    if subject_key and subject_key not in window_key and subject_key not in evidence_key:
        local_context = f"{window} {evidence}"
        local_sentence = _sentence_containing(local_context, candidate)
        if (
            looks_like_formal_exclusive_subject(candidate)
            and _subject_token_overlap(candidate, local_context)
            and any(keyword in local_context for keyword in EXCLUSIVE_CONTEXT_KEYWORDS)
            and any(keyword in local_context for keyword in ACQUIRED_CONTEXT_KEYWORDS)
            and not _is_subject_company_like(candidate)
            and not has_bad_subject_tail(candidate)
        ):
            reason = "subject_supported_by_local_tokens"
            if local_sentence:
                reason = f"{reason}_near_exclusive_context"
            return SubjectValidationResult(candidate, "pass", False, reason, original)
        resolved = resolve_subject_reference(candidate, window, evidence, article_title=article_title)
        if resolved and normalize_search_key(resolved) != subject_key:
            return SubjectValidationResult(resolved, "resolved", False, "subject_replaced_by_local_context", original)
        if subject_key in title_key and _subject_token_overlap(candidate, f"{window} {evidence}"):
            return SubjectValidationResult(candidate, "review", True, "subject_title_only_with_partial_context_overlap", original)
        if subject_key in title_key:
            return SubjectValidationResult(candidate, "review", True, "subject_only_in_article_title", original)
        return SubjectValidationResult(candidate, "review", True, "subject_not_in_local_exclusive_context", original)

    if not looks_like_formal_exclusive_subject(candidate):
        resolved = resolve_subject_reference(candidate, window, evidence, article_title=article_title)
        if resolved and normalize_search_key(resolved) != subject_key:
            return SubjectValidationResult(resolved, "resolved", False, "non_formal_subject_replaced", original)
        return SubjectValidationResult(candidate, "review", True, "subject_not_formal_enough", original)

    return SubjectValidationResult(candidate, "pass", False, "subject_in_local_context", original)


def resolve_subject_reference(
    subject_candidate: str | None,
    window_text: str | None,
    evidence_text: str | None = None,
    *,
    article_title: str | None = None,
    article_description: str | None = None,
) -> str | None:
    candidates = collect_exclusive_subject_candidates(
        window_text,
        article_title,
        article_description=article_description,
        evidence_text=evidence_text,
        llm_subject_name=subject_candidate,
    )
    best = select_best_exclusive_subject(candidates, evidence_text or "", window_text or "", article_title=article_title)
    return best.name if best else None


def collect_exclusive_subject_candidates(
    window_text: str | None,
    article_title: str | None,
    article_description: str | None = None,
    *,
    evidence_text: str | None = None,
    llm_subject_name: str | None = None,
) -> list[SubjectCandidate]:
    window = compact_spaces(window_text)
    evidence = compact_spaces(evidence_text)
    title = compact_spaces(article_title)
    description = compact_spaces(article_description)
    candidates: list[SubjectCandidate] = []

    for source, text, base_score in [
        ("local_quote", f"{window} {evidence}", 50),
        ("title_quote", title, 42),
        ("previous_sentence_quote", description, 34),
    ]:
        for name, quote_evidence in _quoted_subjects(text):
            candidates.append(SubjectCandidate(name=name, source=source, score=base_score, evidence=quote_evidence))

    for source, text, base_score in [
        ("local_pattern", f"{window} {evidence}", 34),
        ("title_pattern", title, 30),
        ("description_pattern", description, 24),
    ]:
        for name, pattern_evidence in _pattern_subjects(text):
            candidates.append(SubjectCandidate(name=name, source=source, score=base_score, evidence=pattern_evidence))

    if llm_subject_name:
        cleaned = clean_exclusive_subject_candidate(llm_subject_name)
        if cleaned:
            candidates.append(SubjectCandidate(name=cleaned, source="llm_output", score=12, evidence=evidence or window))

    deduped: dict[str, SubjectCandidate] = {}
    for candidate in candidates:
        cleaned = clean_exclusive_subject_candidate(candidate.name)
        if not cleaned:
            continue
        key = normalize_search_key(cleaned)
        if not key:
            continue
        scored = SubjectCandidate(cleaned, candidate.source, candidate.score, candidate.evidence)
        current = deduped.get(key)
        if current is None or scored.score > current.score:
            deduped[key] = scored
    return list(deduped.values())


def select_best_exclusive_subject(
    candidates: list[SubjectCandidate],
    evidence_text: str | None,
    window_text: str | None,
    article_title: str | None = None,
) -> SubjectCandidate | None:
    scored: list[SubjectCandidate] = []
    for candidate in candidates:
        name = clean_exclusive_subject_candidate(candidate.name)
        if not name:
            continue
        score = candidate.score + _subject_specificity_score(name)
        text_for_context = f"{window_text or ''} {evidence_text or ''}"
        key = normalize_search_key(name)
        context_key = normalize_search_key(text_for_context)
        title_key = normalize_search_key(article_title)

        if is_generic_or_weak_subject(name):
            score -= 80
        if has_bad_subject_tail(name):
            score -= 80
        if looks_like_formal_exclusive_subject(name):
            score += 18
        if key and key in context_key:
            score += 16
        elif _subject_token_overlap(name, text_for_context):
            score += 8
        if key and key in title_key:
            score += 10
        if key and key in title_key and key not in context_key and not _subject_token_overlap(name, text_for_context):
            score -= 20
        subject_sentence = _sentence_containing(text_for_context, name)
        if subject_sentence and any(keyword in subject_sentence for keyword in EXCLUSIVE_CONTEXT_KEYWORDS):
            score += 18
        elif subject_sentence and "출시" in subject_sentence and not any(keyword in subject_sentence for keyword in EXCLUSIVE_CONTEXT_KEYWORDS):
            score -= 28
        elif candidate.source in {"local_pattern", "local_quote", "llm_output"}:
            score -= 8
        if len(normalize_search_key(name)) < 4:
            score -= 30
        if score <= 0:
            continue
        scored.append(SubjectCandidate(name=name, source=candidate.source, score=score, evidence=candidate.evidence))

    if not scored:
        return None
    return sorted(scored, key=lambda item: (-item.score, -len(normalize_search_key(item.name)), item.source))[0]


def is_generic_or_weak_subject(subject_name: str | None) -> bool:
    key = normalize_search_key(subject_name)
    if not key:
        return True
    if key in WEAK_SUBJECT_KEYS:
        return True
    text = compact_spaces(subject_name)
    if re.fullmatch(r"[가-힣A-Za-z0-9·\s]{1,20}(?:손해보험|생명보험|화재|생명|손보|생보)", text):
        return True
    if len(key) <= 3 and any(suffix in text for suffix in SUBJECT_SUFFIXES):
        return True
    return False


def is_weak_subject(value: str | None) -> bool:
    return is_generic_or_weak_subject(value)


def has_bad_subject_tail(subject_name: str | None) -> bool:
    text = compact_spaces(subject_name)
    if not text:
        return False
    return any(fragment in text for fragment in BAD_SUBJECT_FRAGMENTS)


def clean_exclusive_subject_candidate(subject_name: str | None) -> str:
    text = compact_spaces(subject_name)
    if not text:
        return ""
    text = text.strip(" \t\r\n'\"‘’“”[]()")
    text = re.sub(r"^(?:한편\s*)?[가-힣A-Za-z0-9·\s]{2,30}(?:은|는|이|가)\s+", "", text)
    text = re.sub(r"^.*?(?:쟁점|핵심|대상)(?:은|는)\s*", "", text)
    text = re.sub(r"^.*?포함된\s+", "", text)
    text = re.sub(r"^\(?무\)?\s*", "(무)", text) if text.startswith(("무)", "(무")) else text
    text = GENERIC_PREFIX_RE.sub("", text)
    text = BAD_TAIL_SPLIT_RE.sub("", text)
    text = re.sub(r"\s*(?:에\s*대해|에\s*대한|을|를|은|는|이|가)$", "", text)
    text = re.sub(r"\s+", " ", text).strip(" ,'\"‘’“”")
    return compact_spaces(text)


def looks_like_formal_exclusive_subject(subject_name: str | None) -> bool:
    text = clean_exclusive_subject_candidate(subject_name)
    key = normalize_search_key(text)
    if len(key) < 4 or is_generic_or_weak_subject(text) or has_bad_subject_tail(text):
        return False
    if any(suffix in text for suffix in SUBJECT_SUFFIXES):
        return True
    if re.search(r"(MRI|암|치매|전이암|건강환급|WON|전통시장|날씨|로봇|연금|수술|검사비|지원비)", text, re.I):
        return True
    return False


def parse_explicit_acquired_year_month(text: str | None, article_pub_date: datetime | None = None) -> str | None:
    value = compact_spaces(text)
    if not value:
        return None
    explicit = re.search(r"(20\d{2})\s*(?:년|[./-])\s*(0?[1-9]|1[0-2])\s*(?:월)?", value)
    if explicit:
        return f"{explicit.group(1)}-{int(explicit.group(2)):02d}"
    if article_pub_date:
        previous = re.search(r"지난해\s*(0?[1-9]|1[0-2])\s*월", value)
        if previous:
            return f"{article_pub_date.year - 1}-{int(previous.group(1)):02d}"
        current = re.search(r"올해\s*(0?[1-9]|1[0-2])\s*월", value)
        if current:
            return f"{article_pub_date.year}-{int(current.group(1)):02d}"
    return None


def fallback_earliest_article_month(articles: list[FactArticle | None]) -> str | None:
    dates = [article.pub_date for article in articles if article is not None and article.pub_date is not None]
    if not dates:
        return None
    return min(dates).strftime("%Y-%m")


def is_valid_year_month(value: str | None) -> bool:
    return bool(value and re.fullmatch(r"20\d{2}-(0[1-9]|1[0-2])", value))


def _quoted_subjects(text: str | None) -> list[tuple[str, str]]:
    source = compact_spaces(text)
    if not source:
        return []
    results: list[tuple[str, str]] = []
    quote_re = re.compile(r"['\"‘“](?P<name>[^'\"’”]{2,100})['\"’”]")
    for match in quote_re.finditer(source):
        raw = compact_spaces(match.group("name"))
        end = match.end()
        tail = source[end : end + 30]
        combined = raw
        tail_match = re.match(r"\s*(?P<tail>(?:보장\s*)?(?:보험|특약|서비스|제도|담보|급부방식))", tail)
        if tail_match and not any(suffix in raw for suffix in SUBJECT_SUFFIXES):
            combined = f"{raw} {compact_spaces(tail_match.group('tail'))}"
        results.append((combined, source[max(0, match.start() - 80) : min(len(source), end + 80)]))
    return results


def _pattern_subjects(text: str | None) -> list[tuple[str, str]]:
    source = compact_spaces(text)
    if not source:
        return []
    results: list[tuple[str, str]] = []
    patterns = [
        r"(?:쟁점|핵심|대상)은\s*(?:[^'\"‘’“”]{0,50})?[‘'\"“](?P<name>[^’'\"”]{2,100})[’'\"”]",
        r"포함된\s+[‘'\"“](?P<name>[^’'\"”]{2,100})[’'\"”]",
        r"(?P<name>[가-힣A-Za-z0-9·() \[\]-]{2,90}?)에\s*대해\s*(?:\d{1,2}\s*개월(?:간)?의?\s*)?배타적\s*사용권",
        r"(?P<name>[가-힣A-Za-z0-9·() \[\]-]{2,90}?)에\s*대해\s*(?:\d{1,2}\s*개월(?:간)?의?\s*)?배타적사용권",
        r"(?P<name>(?:[가-힣A-Za-z0-9·() \[\]-]{0,30}\s*)?[가-힣A-Za-z0-9·()\[\]-]{2,40}\s*(?:보험|특약|서비스|제도|담보|급부방식))",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, source):
            raw = compact_spaces(match.group("name"))
            if raw:
                results.append((raw, source[max(0, match.start() - 80) : min(len(source), match.end() + 80)]))
    return results


def _subject_specificity_score(value: str) -> int:
    text = clean_exclusive_subject_candidate(value)
    key = normalize_search_key(text)
    score = min(len(key), 40)
    if any(suffix in text for suffix in SUBJECT_SUFFIXES):
        score += 20
    if re.search(r"(WON|MRI|KB|NH|AIA|ABL|암|치매|전이암|건강환급|검사비|지원비|돌봄|로봇|전통시장|날씨)", text, re.I):
        score += 10
    if is_generic_or_weak_subject(text) or has_bad_subject_tail(text):
        score -= 80
    return score


def _sentence_containing(text: str | None, subject_name: str | None) -> str:
    key = normalize_search_key(subject_name)
    if not key:
        return ""
    for sentence in _split_sentences(text):
        sentence_key = normalize_search_key(sentence)
        if key in sentence_key or _subject_token_overlap(subject_name, sentence):
            return sentence
    return ""


def _weak_reference_type_conflict(subject_name: str, context_text: str) -> str | None:
    subject = compact_spaces(subject_name)
    context = compact_spaces(context_text)
    if not subject or not context:
        return None
    reference_types = [
        ("특약", ("보험", "서비스", "제도", "담보")),
        ("서비스", ("보험", "특약", "담보")),
        ("담보", ("보험", "특약", "서비스")),
        ("제도", ("보험", "특약", "담보")),
    ]
    for reference_type, conflicting_suffixes in reference_types:
        if not re.search(rf"(?:이번|해당|이)\s*{reference_type}", context):
            continue
        if reference_type in subject:
            continue
        if any(suffix in subject for suffix in conflicting_suffixes):
            return f"weak_reference_type_conflict_{reference_type}"
    return None


def _subject_token_overlap(left: str | None, right: str | None) -> bool:
    left_tokens = _high_info_tokens(left)
    right_tokens = _high_info_tokens(right)
    return bool(left_tokens and right_tokens and left_tokens & right_tokens)


def _is_subject_company_like(subject_name: str | None) -> bool:
    subject = compact_spaces(subject_name)
    if not subject:
        return False
    key = normalize_search_key(subject)
    if any(fragment in key for fragment in ("손해보험협회", "생명보험협회", "신상품심의위원회", "보험협회")):
        return True
    if re.search(r"(?:손해보험|생명보험|화재|생명|손보|생보)$", subject):
        return True
    return False


def _token_overlap(left_key: str, right_key: str) -> bool:
    if not left_key or not right_key:
        return False
    left_tokens = set(TOKEN_RE.findall(left_key))
    right_tokens = set(TOKEN_RE.findall(right_key))
    return bool(left_tokens and right_tokens and left_tokens & right_tokens)


def _high_info_tokens(value: str | None) -> set[str]:
    stopwords = {
        "보험",
        "상품",
        "해당",
        "이번",
        "신상품",
        "배타적사용권",
        "배타적",
        "사용권",
        "독점사용권",
        "독점",
        "획득",
        "부여",
        "인정",
        "개월",
        "특약",
        "담보",
        "서비스",
        "제도",
        "손해보험협회",
        "생명보험협회",
        "신상품심의위원회",
    }
    tokens = {normalize_search_key(token) for token in TOKEN_RE.findall(compact_spaces(value))}
    return {token for token in tokens if len(token) >= 2 and token not in stopwords}


def _split_sentences(text: str | None) -> list[str]:
    cleaned = compact_spaces(text)
    if not cleaned:
        return []
    normalized = re.sub(r"([.!?。])\s+", r"\1\n", cleaned)
    normalized = re.sub(r"(다\.|요\.|다\.)\s+", r"\1\n", normalized)
    rough = re.split(r"\n+", normalized)
    return [compact_spaces(part) for part in rough if compact_spaces(part)]
