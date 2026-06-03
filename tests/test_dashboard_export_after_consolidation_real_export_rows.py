from __future__ import annotations

from app.services.dashboard_service import DashboardService
from app.services.product_consolidation_service import ProductConsolidationService
from tests.test_product_consolidation_real_export_rows import _company, _product


def _dashboard_request() -> dict:
    return {
        "include_review": True,
        "include_changed_companies": True,
        "include_short_term_insurers": True,
        "include_excluded_policy_products": True,
    }


def test_real_export_row_fixtures_export_as_canonical_rows_only(db_session):
    nh = _company(db_session, "NH농협생명")
    _product(db_session, nh, "스텝업700 종신보험", product_type="DEATH_WHOLELIFE")
    _product(db_session, nh, "스텝업 700 NH 종신보험", product_type="DEATH_WHOLELIFE", status="provisional")

    kb = _company(db_session, "KB손해보험", insurance_type="손해보험")
    for index, name in enumerate(["KB 금쪽같은 펫보험", "금쪽같은 펫보험", "펫보험", "KB 금쪽같은 펫 보험 개정"]):
        _product(db_session, kb, name, product_type="PET", status="active" if index == 0 else "provisional")
    db_session.commit()

    ProductConsolidationService().run(db_session, mode="rule_only_apply", target="all", limit=0)

    products = DashboardService()._products(db_session, _dashboard_request())
    rows = [
        "\n".join(str(value or "") for value in item.values())
        for item in products
    ]

    assert len([row for row in rows if "스텝업" in row]) == 1
    assert len([row for row in rows if "금쪽같은" in row or "펫보험" in row]) == 1
    assert all("merged" not in str(item.get("product_status") or "") for item in products)
