from datetime import datetime

from app.db.models import DimCompany, FactArticle
from app.services.exclusive_right_final_adjudication_service import ExclusiveRightFinalAdjudicationService
from app.services.exclusive_right_local_context import validate_exclusive_subject_before_save
from app.services.product_company_eligibility import is_product_news_eligible_company
from app.utils.hashing import article_dedup_hash


def test_weak_exclusive_subject_is_reviewed():
    result = validate_exclusive_subject_before_save(
        "보험특허권",
        evidence_text="보험특허권을 획득했다.",
        window_text="보험특허권을 획득했다.",
        article_title="보험특허권 획득",
    )

    assert result.needs_review is True


def test_exclusive_future_month_from_article_is_reviewed(db_session):
    article = FactArticle(
        source_api="test",
        title="삼성화재, 날씨 피해 보장 담보로 배타적사용권 획득",
        description="날씨 피해 보장 담보로 배타적사용권을 획득했다.",
        publisher="test",
        url="https://example.com/future-month",
        original_url="https://example.com/future-month",
        pub_date=datetime(2026, 5, 1),
        query="test",
        query_group="test",
        content_hash=article_dedup_hash("https://example.com/future-month", "삼성화재, 날씨 피해 보장 담보로 배타적사용권 획득", ""),
    )
    db_session.add(article)
    db_session.commit()

    service = ExclusiveRightFinalAdjudicationService()
    decision = service.adjudicate(
        db_session,
        service.build_input(
            db_session,
            subject_name="날씨 피해 보장 담보",
            company_name="삼성화재",
            acquired_year_month="2027-06",
            article=article,
            context_text="날씨 피해 보장 담보로 배타적사용권을 획득했다.",
            evidence_text="날씨 피해 보장 담보로 배타적사용권을 획득했다.",
        ),
    )

    assert decision.decision == "review"
    assert decision.reason == "exclusive_right_future_acquired_month"


def test_generali_is_not_valid_active_exclusive_owner(db_session):
    generali = db_session.query(DimCompany).filter(DimCompany.company_name_normalized == "제너럴리").one()

    assert is_product_news_eligible_company(generali) is False
