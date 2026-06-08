from app.db.models import FactExclusiveUseRight
from app.services.exclusive_right_consolidation_service import ExclusiveRightConsolidationService


def _right(**overrides):
    data = {
        "company_id": 1,
        "company_name_normalized": "한화손해보험",
        "insurance_type": "손해보험",
        "subject_name": "시그니처 여성건강보험 특약",
        "subject_core_key": "시그니처여성건강보험특약",
        "exclusivity_months": 6,
        "acquired_year_month": "2026-01",
        "confidence_total": 0.9,
        "needs_review": False,
        "event_status": "active",
    }
    data.update(overrides)
    return FactExclusiveUseRight(**data)


def test_exclusive_right_consolidation_dry_run_does_not_flip_review_flag(db_session):
    db_session.add_all(
        [
            _right(exclusivity_months=3),
            _right(exclusivity_months=6),
        ]
    )
    db_session.commit()

    result = ExclusiveRightConsolidationService().run(db_session, mode="dry_run")
    rows = db_session.query(FactExclusiveUseRight).order_by(FactExclusiveUseRight.exclusive_right_id).all()

    assert result["review_count"] == 1
    assert all(row.needs_review is False for row in rows)
    assert all(row.event_status == "active" for row in rows)


def test_exclusive_right_consolidation_does_not_bridge_different_companies(db_session):
    db_session.add_all(
        [
            _right(company_id=1, company_name_normalized="한화손해보험"),
            _right(company_id=2, company_name_normalized="현대해상"),
        ]
    )
    db_session.commit()

    result = ExclusiveRightConsolidationService().run(db_session, mode="rule_only_apply")
    rows = db_session.query(FactExclusiveUseRight).order_by(FactExclusiveUseRight.exclusive_right_id).all()

    assert result["block_count"] == 0
    assert all(row.needs_review is False for row in rows)
    assert all(row.event_status == "active" for row in rows)
