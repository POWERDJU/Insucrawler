from __future__ import annotations

import re


VISIBLE_RELEASE_YEAR_MIN = 2023
VISIBLE_RELEASE_YEAR_MAX = 2026


def visible_release_years() -> list[str]:
    return [str(year) for year in range(VISIBLE_RELEASE_YEAR_MIN, VISIBLE_RELEASE_YEAR_MAX + 1)]


def display_release_year_month(value: str | None) -> str:
    if not value:
        return ""
    match = re.match(r"^(20\d{2})-(0[1-9]|1[0-2])$", str(value))
    if not match:
        return ""
    year = int(match.group(1))
    if VISIBLE_RELEASE_YEAR_MIN <= year <= VISIBLE_RELEASE_YEAR_MAX:
        return str(value)
    return ""
