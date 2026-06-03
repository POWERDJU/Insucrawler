from datetime import datetime

from app.db.models import FactArticle
from app.services.exclusive_right_local_context import (
    select_best_exclusive_context_window,
)
from app.services.exclusive_right_service import ExclusiveRightService


def _article(db, title: str) -> FactArticle:
    article = FactArticle(
        source_api="test",
        title=title,
        description=title,
        url=f"https://example.com/{title}",
        original_url=f"https://example.com/original/{title}",
        pub_date=datetime(2026, 1, 5, 9, 0, 0),
        content_hash=f"best-context-{title}",
    )
    db.add(article)
    db.commit()
    db.refresh(article)
    return article


def test_best_context_window_prefers_item_evidence_over_first_window():
    text = (
        "한화손해보험은 A특약에 대해 3개월 배타적사용권을 획득했다. "
        "이와 별도로 삼성생명은 돌봄 로봇 제공 서비스에 대해 6개월 배타적 사용권을 인정받았다."
    )

    window = select_best_exclusive_context_window(
        "돌봄 로봇 제공 서비스",
        "삼성생명은 돌봄 로봇 제공 서비스에 대해 6개월 배타적 사용권을 인정받았다.",
        text,
        company_name="삼성생명",
        exclusivity_months=6,
    )

    assert window is not None
    assert "삼성생명" in window.window_text
    assert "돌봄 로봇 제공 서비스" in window.window_text
    assert "6개월" in window.window_text


def test_lotte_crew_title_does_not_steal_heungkuk_fire_exclusive_subject(db_session):
    text = (
        "롯데손해보험은 CREW 스크린골프보험을 출시했다. "
        "한편 흥국화재는 표적치매 MRI검사비 특약에 대해 6개월 배타적사용권을 획득했다."
    )

    right = ExclusiveRightService().create_from_text(
        db_session,
        text,
        article=_article(db_session, "롯데손보 CREW 스크린골프보험 출시"),
    )

    assert right is not None
    assert right.company_name_normalized == "흥국화재"
    assert right.subject_name == "표적치매 MRI검사비 특약"
    assert "CREW" not in right.subject_name
