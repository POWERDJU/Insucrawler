from __future__ import annotations

from app.services.company_attribution_service import CompanyAttributionService


def test_local_context_wins_over_article_title(db_session):
    result = CompanyAttributionService().resolve_company_for_context(
        db_session,
        raw_company_name="한화생명",
        local_text="한화손해보험은 시그니처 여성 건강보험 4.0을 출시했다.",
        article_title="한화생명, 보험 신상품 소식",
        product_or_subject_name="시그니처 여성 건강보험 4.0",
    )

    assert result.company_name_normalized == "한화손해보험"
    assert result.insurance_type == "손해보험"
    assert result.needs_review is False
    assert result.basis in {"local_full_name", "local_alias"}


def test_short_alias_does_not_force_match(db_session):
    result = CompanyAttributionService().resolve_company_for_context(
        db_session,
        raw_company_name="삼성",
        local_text="삼성은 새 보험 서비스를 소개했다.",
        product_or_subject_name="새 보험 서비스",
    )

    assert result.company_id is None
    assert result.needs_review is True
    assert result.basis == "ambiguous_review"


def test_association_industry_hint_reresolves_compatible_company(db_session):
    result = CompanyAttributionService().resolve_company_for_context(
        db_session,
        local_text="한화생명 소식도 함께 언급됐다. 한화손해보험은 새 담보로 손해보험협회 배타적사용권을 획득했다.",
        association_hint="손해보험협회 신상품심의위원회",
        product_or_subject_name="새 담보",
    )

    assert result.company_name_normalized == "한화손해보험"
    assert result.insurance_type == "손해보험"
    assert result.needs_review is False


def test_industry_conflict_is_review(db_session):
    result = CompanyAttributionService().resolve_company_for_context(
        db_session,
        local_text="한화생명은 새 특약으로 손해보험협회 배타적사용권을 획득했다고 밝혔다.",
        association_hint="손해보험협회 신상품심의위원회",
        product_or_subject_name="새 특약",
    )

    assert result.company_name_normalized == "한화생명"
    assert result.insurance_type == "생명보험"
    assert result.needs_review is True
    assert "conflict" in result.reason
