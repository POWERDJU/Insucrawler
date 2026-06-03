from app.db.models import FactExclusiveUseRight
from app.services.exclusive_right_consolidation_service import ExclusiveRightBlockingService, ExclusiveRightConsolidationService


def _right(name: str, *, months: int = 6, company_id: int | None = 1):
    return FactExclusiveUseRight(
        company_id=company_id,
        company_name_normalized="한화손해보험" if company_id else None,
        insurance_type="손해보험" if company_id else "unknown",
        subject_name=name,
        subject_core_key="".join(name.split()),
        exclusivity_months=months,
        acquired_year_month="2026-01",
        feature_summary=f"{name} 관련 배타적사용권",
        evidence_text=f"{name} 6개월 배타적사용권 획득",
        confidence_total=0.85,
        needs_review=False,
        event_status="active",
    )


def test_exclusive_right_consolidation_merges_same_company_subject_and_period(db_session):
    left = _right("키즈폰 미니보험")
    right = _right("키즈폰 미니 보험")
    db_session.add_all([left, right])
    db_session.commit()

    result = ExclusiveRightConsolidationService().run(db_session, mode="rule_only_apply")
    db_session.refresh(left)
    db_session.refresh(right)

    assert result["auto_merge_count"] == 1
    assert {left.event_status, right.event_status} == {"active", "merged"}


def test_exclusive_right_blocking_allows_unknown_company_context_similarity(db_session):
    left = _right("전통시장 날씨피해 보상 보험", company_id=None)
    right = _right("전통시장 날씨 보험", company_id=None)

    assert ExclusiveRightBlockingService().same_block(left, right) is True
