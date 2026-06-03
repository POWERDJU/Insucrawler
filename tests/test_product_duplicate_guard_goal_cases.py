from __future__ import annotations

from app.services.product_consolidation_service import ProductConsolidationService
from app.services.product_duplicate_guard_service import ProductDuplicateGuardService
from tests.test_product_consolidation_goal_cases import _company, _product


def _seed_goal_duplicates(db_session):
    shinhan = _company(db_session, "신한라이프생명")
    for name in ["신한톤틴연금보험", "톤틴(Tontine) 연금", "한국형 톤틴연금보험"]:
        _product(db_session, shinhan, name, product_type="ANNUITY_SAVINGS")

    hanwha = _company(db_session, "한화손해보험", insurance_type="손해보험")
    for name in ["시그니처 여성 건강보험 4.0", "시그니처 여성보험 4.0"]:
        _product(db_session, hanwha, name)

    abl = _company(db_session, "ABL생명")
    for name in ["우리WON건강환급보험", "건강환급보험", "보험료 환급해주는 건강환급보험"]:
        _product(db_session, abl, name)
    _product(db_session, abl, "우리WON전신마취수술보험")
    db_session.commit()


def _group_contains(groups, *needles: str) -> bool:
    for group in groups:
        names = "\n".join(group.get("product_names") or [])
        if all(needle in names for needle in needles):
            return True
    return False


def test_duplicate_guard_detects_goal_groups_before_and_clears_after_rule_consolidation(db_session):
    _seed_goal_duplicates(db_session)
    guard = ProductDuplicateGuardService()

    before = guard.find_duplicate_family_groups(db_session)

    assert _group_contains(before, "톤틴")
    assert _group_contains(before, "시그니처", "여성")
    assert _group_contains(before, "건강환급")
    assert not _group_contains(before, "건강환급", "전신마취수술")

    ProductConsolidationService().run(db_session, mode="rule_only_apply", target="all", limit=0)
    after = guard.find_duplicate_family_groups(db_session)
    summary = guard.summarize_duplicate_risk(after)

    assert not _group_contains(after, "톤틴")
    assert not _group_contains(after, "시그니처", "여성")
    assert not _group_contains(after, "건강환급")
    assert summary["high_risk_group_count"] == 0
