from datetime import datetime

from app.db.models import FactArticle
from app.services.exclusive_right_final_adjudication_service import ExclusiveRightFinalAdjudicationService
from app.utils.hashing import article_dedup_hash


class MockExclusiveAdjudicator:
    def __init__(self):
        self.calls = 0

    def adjudicate_exclusive_right(self, payload):
        self.calls += 1
        return {
            "decision": "accept",
            "subject_name": "여성 법률보장 담보",
            "company_name": "한화손해보험",
            "acquired_year_month": "2026-03",
            "reason": "exclusive context supports subject",
            "evidence_quote": "여성 법률보장 담보로 배타적사용권을 획득했다.",
            "confidence": 0.9,
        }


def test_exclusive_final_adjudication_reviews_future_month(db_session):
    article = FactArticle(
        source_api="test",
        title="한화손보, 여성 법률보장 담보로 배타적사용권 획득",
        description="여성 법률보장 담보로 배타적사용권을 획득했다.",
        publisher="test",
        url="https://example.com/exclusive",
        original_url="https://example.com/exclusive",
        pub_date=datetime(2026, 3, 1),
        query="test",
        query_group="test",
        content_hash=article_dedup_hash("https://example.com/exclusive", "한화손보, 여성 법률보장 담보로 배타적사용권 획득", ""),
    )
    db_session.add(article)
    db_session.commit()
    service = ExclusiveRightFinalAdjudicationService()

    payload = service.build_input(
        db_session,
        subject_name="여성 법률보장 담보",
        company_name="한화손해보험",
        acquired_year_month="2027-06",
        article=article,
        context_text="여성 법률보장 담보로 배타적사용권을 획득했다.",
        evidence_text="여성 법률보장 담보로 배타적사용권을 획득했다.",
    )
    decision = service.adjudicate(db_session, payload)

    assert decision.decision == "review"
    assert decision.reason == "exclusive_right_future_acquired_month"


def test_exclusive_final_adjudication_uses_mock_provider_for_weak_subject(db_session):
    article = FactArticle(
        source_api="test",
        title="한화손보, 여성 법률보장 담보로 배타적사용권 획득",
        description="여성 법률보장 담보로 배타적사용권을 획득했다.",
        publisher="test",
        url="https://example.com/exclusive2",
        original_url="https://example.com/exclusive2",
        pub_date=datetime(2026, 3, 1),
        query="test",
        query_group="test",
        content_hash=article_dedup_hash("https://example.com/exclusive2", "한화손보, 여성 법률보장 담보로 배타적사용권 획득", ""),
    )
    db_session.add(article)
    db_session.commit()
    provider = MockExclusiveAdjudicator()
    service = ExclusiveRightFinalAdjudicationService(provider=provider)

    payload = service.build_input(
        db_session,
        subject_name="보험특허권",
        company_name="한화손해보험",
        acquired_year_month="2026-03",
        article=article,
        context_text="여성 법률보장 담보로 배타적사용권을 획득했다.",
        evidence_text="여성 법률보장 담보로 배타적사용권을 획득했다.",
    )
    decision = service.adjudicate(db_session, payload)

    assert provider.calls == 1
    assert decision.provider_called is True
    assert decision.decision == "accept"
    assert decision.subject_name == "여성 법률보장 담보"
