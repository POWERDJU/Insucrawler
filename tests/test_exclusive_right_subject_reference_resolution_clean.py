from datetime import datetime

from app.db.models import FactArticle, FactExclusiveUseRightObservation
from app.services.exclusive_right_service import ExclusiveRightService


def _article(db, title: str) -> FactArticle:
    article = FactArticle(
        source_api="test",
        title=title,
        description=title,
        url=f"https://example.com/{title}",
        original_url=f"https://example.com/original/{title}",
        pub_date=datetime(2026, 1, 5, 9, 0, 0),
        content_hash=f"subject-resolution-{title}",
    )
    db.add(article)
    db.commit()
    db.refresh(article)
    return article


def test_samsung_weak_subject_resolves_to_robot_care_service(db_session):
    text = (
        "이번 사안의 쟁점은 삼성생명이 출시한 치매보험 상품에 포함된 ‘돌봄 로봇 제공 서비스’다. "
        "삼성생명은 해당 상품에 대해 생명보험협회 신상품심의위원회로부터 6개월간의 배타적 사용권을 인정받았다."
    )

    right = ExclusiveRightService().create_from_text(
        db_session,
        text,
        article=_article(db_session, "삼성생명 치매보험 배타적 사용권"),
    )

    assert right is not None
    assert right.company_name_normalized == "삼성생명"
    assert right.subject_name == "돌봄 로봇 제공 서비스"
    assert right.subject_name != "해당 상품"
    assert right.subject_core_key == "돌봄로봇제공서비스"
    assert right.exclusivity_months == 6
    assert right.event_status == "active"


def test_weak_subject_without_local_reference_is_review_observation_only(db_session):
    right = ExclusiveRightService().create_from_text(
        db_session,
        "한화손해보험은 해당 상품에 대해 6개월 배타적사용권을 획득했다.",
        article=_article(db_session, "한화손해보험 배타적사용권"),
    )

    observations = db_session.query(FactExclusiveUseRightObservation).all()

    assert right is None
    assert len(observations) == 1
    assert observations[0].needs_review is True
    assert observations[0].status_candidate == "rejected"
