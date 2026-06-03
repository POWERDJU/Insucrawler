from __future__ import annotations

from app.utils.text import strip_html


def clean_article_text(html_or_text: str | None) -> str:
    return strip_html(html_or_text)
