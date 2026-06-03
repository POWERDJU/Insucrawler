from __future__ import annotations

import json

from app.db.models import FactExclusiveUseRight
from app.services.exclusive_right_consolidation_service import ExclusiveRightConsolidationService
from app.services.exclusive_right_duplicate_guard_service import ExclusiveRightDuplicateGuardService
from app.utils.text import normalize_search_key


def _event(db_session, *, subject: str, company_id: int = 2001, company: str = "교보생명") -> FactExclusiveUseRight:
    row = FactExclusiveUseRight(
        company_id=company_id,
        company_name_normalized=company,
        insurance_type="생명보험",
        subject_name=subject,
        subject_core_key=normalize_search_key(subject),
        exclusivity_months=6,
        acquired_year_month="2026-02",
        feature_summary=f"{subject} 배타적사용권",
        evidence_text=f"{company}은 {subject}에 대해 6개월 배타적사용권을 획득했다.",
        article_count=1,
        confidence_total=0.9,
        needs_review=False,
        event_status="active",
        alias_names_json=json.dumps([subject], ensure_ascii=False),
    )
    db_session.add(row)
    db_session.flush()
    row.canonical_exclusive_right_id = row.exclusive_right_id
    return row


def test_exclusive_right_duplicate_guard_finds_group_before_merge_and_clears_after(db_session):
    _event(db_session, subject="여성건강보험특약")
    _event(db_session, subject="여성건강보험")
    db_session.commit()

    guard = ExclusiveRightDuplicateGuardService()
    before = guard.find_duplicate_groups(db_session)
    assert before
    assert any({"여성건강보험특약", "여성건강보험"}.issubset(set(group["subject_names"])) for group in before)

    ExclusiveRightConsolidationService().run(db_session, mode="rule_only_apply")

    after = guard.find_duplicate_groups(db_session)
    assert not any({"여성건강보험특약", "여성건강보험"}.issubset(set(group["subject_names"])) for group in after)
