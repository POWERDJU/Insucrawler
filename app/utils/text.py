from __future__ import annotations

import re


def compact_spaces(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_search_key(value: str | None) -> str:
    text = (value or "").casefold()
    text = re.sub(r"[\s\-_·ㆍ•\.,'\"()\[\]{}<>/\\|:;!@#$%^&*+=~`?]", "", text)
    return text


def strip_html(value: str | None) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    return compact_spaces(text)
