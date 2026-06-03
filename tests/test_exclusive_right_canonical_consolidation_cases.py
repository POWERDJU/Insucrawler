from __future__ import annotations

from datetime import datetime

from app.db.models import FactArticle, FactExclusiveUseRight
from app.services.exclusive_right_consolidation_service import ExclusiveRightConsolidationService
from app.services.exclusive_right_service import ExclusiveRightService


def _seed_event(db_session, *, company: str, subject: str, months: int, title: str, pub_day: int = 5):
    article = FactArticle(
        source_api="test",
        title=title,
        description=title,
        url=f"https://example.com/{title}",
        original_url=f"https://example.com/original/{title}",
        pub_date=datetime(2026, 1, pub_day, 9, 0, 0),
        content_hash=f"exclusive-consolidation-{title}",
    )
    db_session.add(article)
    db_session.commit()
    db_session.refresh(article)
    return ExclusiveRightService().create_from_text(
        db_session,
        f"{company}는 {subject}에 대해 {months}개월 배타적사용권을 획득했다.",
        article=article,
    )


def _active_subjects(db_session) -> list[str]:
    return [
        row.subject_name
        for row in db_session.query(FactExclusiveUseRight)
        .filter(FactExclusiveUseRight.event_status == "active")
        .order_by(FactExclusiveUseRight.exclusive_right_id)
        .all()
    ]


def test_heungkuk_fire_mri_subject_variants_merge_to_one_canonical_event(db_session):
    variants = [
        "표적치매 MRI검사비 특약",
        "치매 치료 중 MRI 검사비 보장 특약",
        "표적치매치료 MRI 검사비용 보장 특약",
        "MRI 검사 지원비 보장 특약",
    ]
    for index, subject in enumerate(variants):
        _seed_event(db_session, company="흥국화재", subject=subject, months=6, title=f"흥국화재 {index}", pub_day=5 + index)

    result = ExclusiveRightConsolidationService().run(db_session, mode="rule_only_apply")
    active = db_session.query(FactExclusiveUseRight).filter(FactExclusiveUseRight.event_status == "active").one()

    assert result["auto_merge_count"] == 3
    assert _active_subjects(db_session) == [active.subject_name]
    assert active.company_name_normalized == "흥국화재"
    assert active.exclusivity_months == 6
    for subject in variants:
        assert subject in (active.alias_names_json or "")


def test_period_conflict_is_not_auto_merged(db_session):
    _seed_event(db_session, company="한화손해보험", subject="암진단비확대특약", months=3, title="한화 3개월")
    _seed_event(db_session, company="한화손해보험", subject="암진단비 확대 특약", months=6, title="한화 6개월")

    result = ExclusiveRightConsolidationService().run(db_session, mode="rule_only_apply")

    assert result["auto_merge_count"] == 0
    assert result["review_count"] >= 1
    assert len(_active_subjects(db_session)) == 2
