from __future__ import annotations

from datetime import datetime

from app.db.models import FactArticle
from app.services.exclusive_right_local_context import (
    fallback_earliest_article_month,
    is_valid_year_month,
    parse_explicit_acquired_year_month,
)
from app.services.exclusive_right_service import ExclusiveRightService


def _article(db_session, title: str, pub_date: datetime) -> FactArticle:
    article = FactArticle(
        source_api="test",
        title=title,
        description=title,
        url=f"https://example.com/{title}",
        original_url=f"https://example.com/original/{title}",
        pub_date=pub_date,
        content_hash=f"exclusive-month-{title}",
    )
    db_session.add(article)
    db_session.commit()
    db_session.refresh(article)
    return article


def test_relative_acquired_month_uses_article_pub_date():
    assert parse_explicit_acquired_year_month("지난해 11월 배타적사용권을 획득했다.", datetime(2026, 1, 5)) == "2025-11"
    assert parse_explicit_acquired_year_month("올해 1월 배타적사용권을 획득했다.", datetime(2026, 5, 5)) == "2026-01"


def test_missing_explicit_month_falls_back_to_earliest_article_month(db_session):
    articles = [
        _article(db_session, "late", datetime(2026, 1, 10, 9, 0, 0)),
        _article(db_session, "early", datetime(2026, 1, 5, 9, 0, 0)),
    ]

    assert fallback_earliest_article_month(articles) == "2026-01"


def test_acquired_year_month_never_uses_placeholder_month(db_session):
    right = ExclusiveRightService().create_from_text(
        db_session,
        "KB손해보험은 KB전통시장 날씨피해 보상 보험에 대해 지난해 11월 18개월 배타적사용권을 획득했다.",
        article=_article(db_session, "KB 전통시장 날씨", datetime(2026, 1, 5, 9, 0, 0)),
    )

    assert right is not None
    assert right.acquired_year_month == "2025-11"
    assert is_valid_year_month(right.acquired_year_month)
    assert "XX" not in right.acquired_year_month
    assert "MM" not in right.acquired_year_month
