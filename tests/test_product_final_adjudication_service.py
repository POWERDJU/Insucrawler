from datetime import datetime

from app.db.models import FactArticle
from app.services.product_final_adjudication_service import ProductFinalAdjudicationService
from app.utils.hashing import article_dedup_hash


class MockProductAdjudicator:
    def __init__(self):
        self.calls = 0

    def adjudicate_product(self, payload):
        self.calls += 1
        return {
            "decision": "reassign_company",
            "canonical_product_name": "시그니처 여성건강보험",
            "company_name": "한화손해보험",
            "insurance_type": "손해보험",
            "product_type_code": "HEALTH_COMPREHENSIVE",
            "reason": "local context names Hanwha product",
            "evidence_quote": "한화손해보험은 시그니처 여성건강보험을 출시했다.",
            "confidence": 0.92,
        }


def test_product_final_adjudication_uses_mock_llm_for_risky_candidate(db_session):
    article = FactArticle(
        source_api="test",
        title="한화손해보험, 시그니처 여성건강보험 출시",
        description="한화손해보험은 시그니처 여성건강보험을 출시했다.",
        publisher="test",
        url="https://example.com/hanwha-signature",
        original_url="https://example.com/hanwha-signature",
        pub_date=datetime(2026, 3, 1),
        query="test",
        query_group="test",
        content_hash=article_dedup_hash("https://example.com/hanwha-signature", "한화손해보험, 시그니처 여성건강보험 출시", ""),
    )
    db_session.add(article)
    db_session.commit()
    provider = MockProductAdjudicator()
    service = ProductFinalAdjudicationService(provider=provider)

    payload = service.build_input(
        db_session,
        product_name="이에 손해보험",
        company_name="DB손해보험",
        article=article,
        context_text="한화손해보험은 시그니처 여성건강보험을 출시했다.",
    )
    decision = service.adjudicate(db_session, payload)

    assert provider.calls == 1
    assert decision.provider_called is True
    assert decision.decision == "accept"
    assert decision.company_name == "한화손해보험"
    assert decision.canonical_product_name == "시그니처 여성건강보험"
