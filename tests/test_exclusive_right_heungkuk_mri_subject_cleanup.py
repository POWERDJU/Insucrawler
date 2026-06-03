from __future__ import annotations

from datetime import datetime

from app.db.models import FactArticle
from app.services.exclusive_right_service import ExclusiveRightService


def _article(db_session, title: str) -> FactArticle:
    article = FactArticle(
        source_api="test",
        title=title,
        description=title,
        url="https://example.com/heungkuk-mri",
        original_url="https://example.com/original/heungkuk-mri",
        pub_date=datetime(2026, 1, 20, 9, 0, 0),
        content_hash="exclusive-heungkuk-mri-subject-cleanup",
    )
    db_session.add(article)
    db_session.commit()
    db_session.refresh(article)
    return article


def test_exclusive_right_heungkuk_mri_subject_cleanup(db_session):
    article = _article(
        db_session,
        "흥국화재, 업계 최초 치매 치료 중 MRI 검사비 보장 6개월 배타적사용권 획득",
    )
    text = (
        "흥국화재해상보험이 업계 최초로 표적치매치료를 위한 필수 검사비인 "
        "‘자기공명영상(MRI) 검사비’ 보장 특약을 개발해 손해보험협회로부터 "
        "6개월간의 배타적사용권을 획득했다."
    )

    right = ExclusiveRightService().create_from_text(db_session, text, article=article)

    assert right is not None
    assert right.company_name_normalized == "흥국화재"
    assert "개발해" not in right.subject_name
    assert "손해보험협회" not in right.subject_name
    assert "협회" not in right.subject_name
    assert "MRI" in right.subject_name
    assert "특약" in right.subject_name
    assert right.event_status == "active"
