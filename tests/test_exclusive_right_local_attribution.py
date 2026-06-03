from __future__ import annotations

from datetime import datetime

from app.db.models import FactArticle, FactExclusiveUseRightObservation
from app.services.exclusive_right_local_context import validate_exclusive_subject_before_save
from app.services.exclusive_right_service import ExclusiveRightService


def _article(db_session, title: str, pub_date: datetime | None = None) -> FactArticle:
    article = FactArticle(
        source_api="test",
        title=title,
        description=title,
        url=f"https://example.com/{title}",
        original_url=f"https://example.com/original/{title}",
        pub_date=pub_date or datetime(2026, 1, 5, 9, 0, 0),
        content_hash=f"exclusive-local-{title}",
    )
    db_session.add(article)
    db_session.commit()
    db_session.refresh(article)
    return article


def test_lotte_crew_article_does_not_steal_exclusive_right_subject(db_session):
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


def test_samsung_weak_subject_is_resolved_to_local_service_name(db_session):
    text = (
        "이번 사안의 쟁점은 삼성생명이 출시한 치매보험 상품에 포함된 ‘돌봄 로봇 제공 서비스’다. "
        "삼성생명은 해당 상품에 대해 생명보험협회 신상품심의위원회로부터 6개월간의 배타적 사용권을 인정받았지만..."
    )

    right = ExclusiveRightService().create_from_text(
        db_session,
        text,
        article=_article(db_session, "삼성생명 치매보험 배타적사용권"),
    )

    assert right is not None
    assert right.company_name_normalized == "삼성생명"
    assert right.subject_name == "돌봄 로봇 제공 서비스"
    assert right.subject_core_key == "돌봄로봇제공서비스"
    assert right.exclusivity_months == 6
    assert right.event_status == "active"


def test_weak_subject_alone_is_observation_only(db_session):
    article = _article(db_session, "신상품 배타적사용권")
    right = ExclusiveRightService().create_from_text(
        db_session,
        "한화손해보험은 해당 상품에 대해 6개월 배타적사용권을 획득했다.",
        article=article,
    )

    observations = db_session.query(FactExclusiveUseRightObservation).all()

    assert right is None
    assert len(observations) == 1
    assert observations[0].needs_review is True
    assert observations[0].status_candidate == "rejected"


def test_crew_screen_golf_is_review_when_local_reference_is_rider():
    validation = validate_exclusive_subject_before_save(
        "CREW 스크린골프 보험",
        evidence_text="롯데손보 'CREW 스크린골프 보험' 출시 6개월 배타적 사용권을 획득했다고 밝혔다.",
        window_text=(
            "롯데손보 'CREW 스크린골프 보험' 출시 6개월 배타적 사용권을 획득했다고 밝혔다. "
            "이번 특약은 한국에자이 HED팀과의 협업을 통해 개발했다."
        ),
        article_title="[보험 현미경] 롯데손보 'CREW 스크린골프 보험' 출시",
    )

    assert validation.status == "review"
    assert validation.needs_review is True
    assert validation.reason == "weak_reference_type_conflict_특약"
