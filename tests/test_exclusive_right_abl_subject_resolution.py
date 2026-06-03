from __future__ import annotations

from datetime import datetime

from app.db.models import FactArticle
from app.services.exclusive_right_service import ExclusiveRightService


def _article(db_session, title: str) -> FactArticle:
    article = FactArticle(
        source_api="test",
        title=title,
        description=title,
        url="https://example.com/abl",
        original_url="https://example.com/original/abl",
        pub_date=datetime(2026, 1, 5, 10, 0, 0),
        content_hash="exclusive-abl-subject-resolution",
    )
    db_session.add(article)
    db_session.commit()
    db_session.refresh(article)
    return article


def test_exclusive_right_abl_won_health_refund_subject_resolution(db_session):
    article = _article(
        db_session,
        "우리금융그룹 ABL생명, 납입한 특약보험료 건강환급금으로 돌려주는 '(무)우리WON건강환급보험' 배타적사용권 획득",
    )
    text = (
        "ABL생명은 납입한 특약보험료를 건강환급금으로 돌려주는 상품에 대해 "
        "생명보험협회로부터 9개월간의 배타적사용권을 부여받았다."
    )

    right = ExclusiveRightService().create_from_text(db_session, text, article=article)

    assert right is not None
    assert right.company_name_normalized == "ABL생명"
    assert right.exclusivity_months == 9
    assert right.subject_name != "상품"
    assert "우리WON건강환급보험" in right.subject_name
    assert right.event_status == "active"
