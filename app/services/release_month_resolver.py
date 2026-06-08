from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable


VALID_YEAR_MONTH_PATTERN = re.compile(r"^(20\d{2})-(0[1-9]|1[0-2])$")

EXPLICIT_RELEASE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"(?P<year>20\d{2})\s*년\s*(?P<month>0?[1-9]|1[0-2])\s*월"
        r"(?P<context>.{0,40}?(?:출시|선보|내놨|판매\s*개시|판매한다|개정\s*출시|신규\s*출시))"
    ),
    re.compile(
        r"(?:출시|선보|내놨|판매\s*개시|판매한다|개정\s*출시|신규\s*출시)"
        r"(?P<context>.{0,40}?)(?P<year>20\d{2})\s*년\s*(?P<month>0?[1-9]|1[0-2])\s*월"
    ),
)
RELATIVE_RELEASE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"올해\s*(?P<month>0?[1-9]|1[0-2])\s*월.{0,40}?(?:출시|선보|내놨|판매\s*개시|판매한다)"),
    re.compile(r"지난해\s*(?P<month>0?[1-9]|1[0-2])\s*월.{0,40}?(?:출시|선보|내놨|판매\s*개시|판매한다)"),
)


@dataclass(frozen=True)
class ReleaseMonthResolution:
    year_month: str | None
    basis: str
    source_text: str | None = None


def is_valid_year_month(value: str | None) -> bool:
    return bool(value and VALID_YEAR_MONTH_PATTERN.match(str(value)))


def parse_explicit_release_year_month(text: str | None, article_pub_date: datetime | None = None) -> str | None:
    value = " ".join(str(text or "").split())
    if not value:
        return None
    for pattern in EXPLICIT_RELEASE_PATTERNS:
        match = pattern.search(value)
        if match:
            return _format_year_month(match.group("year"), match.group("month"))
    if article_pub_date:
        for pattern in RELATIVE_RELEASE_PATTERNS:
            match = pattern.search(value)
            if not match:
                continue
            year = article_pub_date.year - (1 if "지난해" in match.group(0) else 0)
            return _format_year_month(str(year), match.group("month"))
    return None


def resolve_product_release_year_month(
    article_texts: Iterable[tuple[str | None, datetime | None]] | None,
    *,
    fallback_month: str | None = None,
) -> ReleaseMonthResolution:
    for text, pub_date in article_texts or []:
        parsed = parse_explicit_release_year_month(text, pub_date)
        if parsed:
            return ReleaseMonthResolution(parsed, "explicit_in_article", text)
    if is_valid_year_month(fallback_month):
        return ReleaseMonthResolution(fallback_month, "earliest_related_article_month", None)
    return ReleaseMonthResolution(None, "unknown", None)


def release_basis_priority(basis: str | None) -> int:
    priorities = {
        "unknown": 0,
        "first_seen_only": 10,
        "earliest_related_article_month": 20,
        "inferred_from_article_date": 30,
        "explicit_in_article": 80,
        "external_grounded_source": 90,
        "manual": 100,
    }
    return priorities.get((basis or "unknown").strip(), 0)


def _format_year_month(year: str, month: str) -> str | None:
    try:
        month_int = int(month)
    except (TypeError, ValueError):
        return None
    if not 1 <= month_int <= 12:
        return None
    return f"{int(year):04d}-{month_int:02d}"
