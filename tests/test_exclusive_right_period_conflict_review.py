from app.db.models import FactExclusiveUseRight
from app.services.exclusive_right_consolidation_service import ExclusiveRightConsolidationService


def test_exclusive_right_period_conflict_is_reported_without_flipping_review_flags(db_session):
    base = {
        "company_id": 1,
        "company_name_normalized": "한화손해보험",
        "insurance_type": "손해보험",
        "subject_name": "OO보험",
        "subject_core_key": "OO보험",
        "acquired_year_month": "2026-01",
        "confidence_total": 0.8,
        "needs_review": False,
        "event_status": "active",
    }
    db_session.add_all(
        [
            FactExclusiveUseRight(**base, exclusivity_months=3),
            FactExclusiveUseRight(**base, exclusivity_months=6),
        ]
    )
    db_session.commit()

    result = ExclusiveRightConsolidationService().run(db_session, mode="rule_only_apply")
    rows = db_session.query(FactExclusiveUseRight).all()

    assert result["review_count"] == 1
    assert result["auto_merge_count"] == 0
    assert all(row.needs_review is False for row in rows)
    assert all(row.event_status != "merged" for row in rows)
