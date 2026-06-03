from __future__ import annotations

from datetime import datetime

from app.db.models import FactArticle
from app.services.exclusive_right_service import ExclusiveRightService


def _article(db_session, title: str = "배타적사용권 기사") -> FactArticle:
    article = FactArticle(
        source_api="test",
        title=title,
        description=title,
        url="https://example.com/exclusive",
        original_url="https://example.com/original-exclusive",
        pub_date=datetime(2026, 5, 3, 9, 0, 0),
        content_hash=f"hash-{title}",
    )
    db_session.add(article)
    db_session.commit()
    db_session.refresh(article)
    return article


def test_exclusive_right_canonical_stores_normalized_company_only(db_session):
    text = "한화손해보험은 OO보험에 대해 6개월 배타적사용권을 획득했다."
    right = ExclusiveRightService().create_from_text(db_session, text, article=_article(db_session))

    assert right is not None
    assert right.company_id is not None
    assert right.company_name_normalized == "한화손해보험"
    assert right.insurance_type == "손해보험"
    assert not hasattr(right, "company_name_raw")
    assert not hasattr(right, "company_display_name")
    assert right.exclusivity_months == 6
    assert right.acquired_year_month == "2026-05"
    assert right.needs_review is False


def test_exclusive_right_life_company_alias_is_normalized(db_session):
    text = "신한라이프는 OO특약에 대해 3개월 배타적사용권을 획득했다."
    right = ExclusiveRightService().create_from_text(db_session, text, article=_article(db_session, "신한라이프 배타적사용권"))

    assert right is not None
    assert right.company_id is not None
    assert right.company_name_normalized == "신한라이프생명"
    assert right.insurance_type == "생명보험"


def test_exclusive_right_company_alias_normalizes_nonghyup_nonlife(db_session):
    text = "농협손보가 신규 담보에 대해 배타적사용권을 획득했다."
    right = ExclusiveRightService().create_from_text(db_session, text, article=_article(db_session, "농협손보 배타적사용권"))

    assert right is None
    observation = ExclusiveRightService().detail(db_session, 1)
    assert observation is None


def test_local_nonghyup_without_exclusive_context_does_not_create_event(db_session):
    text = "경남농협은 보험 관련 행사를 열었다. 배타적사용권 관련 내용은 없다."
    right = ExclusiveRightService().create_from_text(db_session, text, article=_article(db_session, "경남농협 행사"))

    assert right is None


def test_local_org_is_not_confirmed_when_known_insurer_exists_in_article(db_session):
    text = "경남농협과 NH농협손해보험이 참여한 기사에서 NH농협손해보험이 OO특약 배타적사용권을 획득했다."
    right = ExclusiveRightService().create_from_text(
        db_session,
        text,
        article=_article(db_session, "NH농협손해보험 배타적사용권"),
        company_name_candidate="경남농협",
    )

    assert right is not None
    assert right.company_name_normalized == "NH농협손해보험"
    assert right.insurance_type == "손해보험"
