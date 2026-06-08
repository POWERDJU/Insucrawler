from __future__ import annotations

from datetime import datetime

from app.services.release_month_resolver import parse_explicit_release_year_month


def test_parse_explicit_release_month_from_korean_launch_sentence():
    assert parse_explicit_release_year_month("한화손해보험은 2026년 1월 시그니처 여성건강보험 4.0을 출시했다.") == "2026-01"


def test_parse_relative_release_month_from_article_date():
    assert (
        parse_explicit_release_year_month(
            "올해 1월 출시한 시그니처 여성건강보험 4.0의 보장을 확대했다.",
            datetime(2026, 3, 1),
        )
        == "2026-01"
    )
    assert (
        parse_explicit_release_year_month(
            "지난해 11월 출시한 상품이다.",
            datetime(2026, 1, 5),
        )
        == "2025-11"
    )
