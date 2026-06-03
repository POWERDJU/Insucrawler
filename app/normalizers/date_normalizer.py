from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class YearMonthResult:
    year_month: str | None
    basis: str


def normalize_year_month(text: str | None, article_pub_date: datetime | None = None) -> YearMonthResult:
    value = text or ""
    explicit = re.search(r"(20\d{2})\s*[년./-]\s*(1[0-2]|0?[1-9])\s*월?", value)
    if explicit:
        return YearMonthResult(f"{explicit.group(1)}-{int(explicit.group(2)):02d}", "explicit_in_article")
    compact = re.search(r"\b(20\d{2})(1[0-2]|0[1-9])\b", value)
    if compact:
        return YearMonthResult(f"{compact.group(1)}-{int(compact.group(2)):02d}", "explicit_in_article")
    if "지난달" in value and article_pub_date:
        year = article_pub_date.year
        month = article_pub_date.month - 1
        if month == 0:
            year -= 1
            month = 12
        return YearMonthResult(f"{year}-{month:02d}", "inferred_from_article_date")
    if "이달" in value and article_pub_date:
        return YearMonthResult(article_pub_date.strftime("%Y-%m"), "inferred_from_article_date")
    return YearMonthResult(None, "unknown")
