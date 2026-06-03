from __future__ import annotations

from app.services.company_attribution_service import CompanyAttributionService


def test_nonlife_association_does_not_accept_life_company_without_review(db_session):
    result = CompanyAttributionService().resolve_company_for_context(
        db_session,
        local_text="삼성생명은 새 서비스로 손해보험협회 배타적사용권을 획득했다.",
        association_hint="손해보험협회",
        product_or_subject_name="새 서비스",
    )

    assert result.company_name_normalized == "삼성생명"
    assert result.insurance_type == "생명보험"
    assert result.needs_review is True


def test_life_association_accepts_life_company(db_session):
    result = CompanyAttributionService().resolve_company_for_context(
        db_session,
        local_text="삼성생명은 돌봄 로봇 제공 서비스로 생명보험협회 배타적사용권을 획득했다.",
        association_hint="생명보험협회",
        product_or_subject_name="돌봄 로봇 제공 서비스",
    )

    assert result.company_name_normalized == "삼성생명"
    assert result.insurance_type == "생명보험"
    assert result.needs_review is False
