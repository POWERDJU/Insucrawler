import json
from datetime import datetime

from app.db.models import FactArticle, FactLLMBatchJob, FactLLMQueue, DimProduct
from app.services.article_eligibility_filter_service import ArticleEligibilityFilterService
from app.services.batch_llm_service import BatchLLMService
from app.services.extract_service import ExtractService
from app.utils.hashing import article_dedup_hash


def _roundup_article(db_session) -> FactArticle:
    title = "[금융단신] 신한은행 새 예금 출시 / 삼성화재 건강보험 안내"
    description = (
        "신한은행은 모바일 전용 예금 상품을 출시했다. / "
        "삼성화재는 건강보험 신상품을 소개했다. / "
        "카드사와 증권사 이벤트 소식도 함께 전했다."
    )
    url = "https://example.com/product-632-roundup"
    article = FactArticle(
        source_api="test",
        title=title,
        description=description,
        publisher="Test News",
        url=url,
        original_url=url,
        pub_date=datetime(2026, 1, 8, 9, 0, 0),
        query="test",
        query_group="test",
        content_hash=article_dedup_hash(url, title, ""),
        extraction_status="pending",
    )
    db_session.add(article)
    db_session.commit()
    return article


def test_product_632_type_shinhan_bank_roundup_is_ineligible(db_session):
    article = _roundup_article(db_session)

    decision = ArticleEligibilityFilterService().classify_article(db_session, article)

    assert decision.eligible_for_product_extraction is False
    assert decision.eligible_for_exclusive_right_extraction is False
    assert decision.exclusion_reason == "multi_financial_institution_roundup"
    assert "신한은행" in decision.detected_non_insurance_financial_institutions


def test_product_632_type_bank_card_primary_article_with_insurance_aside_is_ineligible(db_session):
    title = "신한은행, '나라사랑카드' 3기 사업자 중 최초로 발급 30만좌 돌파"
    description = (
        "슈퍼SOL에서는 장병과 청년 고객을 위한 금융정보와 금융교육 콘텐츠를 제공하고 있으며, "
        "한화 EZ 손해보험과의 협업을 통해 군 복무 중 발생할 수 있는 상해 및 질병 보장 서비스도 선보였다. "
        "아울러 정부와 금융당국의 정책 안내도 제공한다."
    )
    article = FactArticle(
        source_api="test",
        title=title,
        description=description,
        publisher="Test News",
        url="https://example.com/product-632-bank-card",
        original_url="https://example.com/product-632-bank-card",
        pub_date=datetime(2026, 1, 8, 9, 0, 0),
        query="test",
        query_group="test",
        content_hash=article_dedup_hash("https://example.com/product-632-bank-card", title, ""),
        extraction_status="pending",
    )
    db_session.add(article)
    db_session.commit()

    decision = ArticleEligibilityFilterService().classify_article(db_session, article)

    assert decision.eligible_for_product_extraction is False
    assert decision.eligible_for_exclusive_right_extraction is False
    assert decision.exclusion_reason == "multi_financial_institution_roundup"
    assert "신한은행" in decision.detected_non_insurance_financial_institutions


def test_product_632_type_roundup_does_not_create_queue(db_session):
    article = _roundup_article(db_session)

    result = ExtractService().enqueue_article_extraction(db_session, article.article_id, force_batch_eligible=True)

    assert result["status"] == "excluded_article_eligibility"
    assert result["llm_queue_id"] is None
    assert article.extraction_exclusion_reason == "multi_financial_institution_roundup"
    assert db_session.query(FactLLMQueue).count() == 0


def test_ineligible_article_batch_import_output_is_skipped(db_session, tmp_path):
    article = _roundup_article(db_session)
    queue = FactLLMQueue(
        target_type="article",
        target_id=article.article_id,
        task_type="extract",
        priority="medium",
        batch_eligible_yn=True,
        status="pending",
    )
    db_session.add(queue)
    db_session.flush()
    job = FactLLMBatchJob(
        provider="gemini",
        model_name="gemini-2.0-flash",
        task_type="extract",
        status="provider_completed",
        provider_status="JOB_STATE_SUCCEEDED",
        request_count=1,
    )
    db_session.add(job)
    db_session.flush()

    output = tmp_path / "batch-output.jsonl"
    payload = {
        "key": str(queue.llm_queue_id),
        "response": {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": json.dumps(
                                    {
                                        "article_relevance": {
                                            "is_relevant": True,
                                            "relevance_type": "new_product",
                                            "reason": "fixture",
                                        },
                                        "products": [
                                            {
                                                "identity": {
                                                    "raw_product_name": "삼성화재 건강보험",
                                                    "normalized_product_name_candidate": "삼성화재 건강보험",
                                                    "company_name_raw": "삼성화재",
                                                    "company_name_candidate": "삼성화재",
                                                    "insurance_type": "손해보험",
                                                    "release_year_month": "2026-01",
                                                    "release_year_month_basis": "explicit_in_article",
                                                },
                                                "product_type_classification": {
                                                    "primary_product_type": {
                                                        "code": "HEALTH_COMPREHENSIVE",
                                                        "name_ko": "건강(종합)",
                                                        "basis": "fixture",
                                                        "evidence_text": "삼성화재 건강보험",
                                                        "confidence": 0.8,
                                                    },
                                                    "secondary_product_types": [],
                                                    "needs_human_review": False,
                                                },
                                                "evidence": {"product_name_evidence": "삼성화재 건강보험"},
                                                "confidence": {
                                                    "identity": 0.8,
                                                    "product_type": 0.8,
                                                    "features": 0.5,
                                                    "coverage": 0.5,
                                                    "sales": 0.5,
                                                    "narrative": 0.5,
                                                },
                                            }
                                        ],
                                    },
                                    ensure_ascii=False,
                                )
                            }
                        ]
                    }
                }
            ]
        },
    }
    output.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")

    result = BatchLLMService().import_results(db_session, job, output)

    assert result == {"completed": 0, "failed": 0, "skipped": 1}
    assert queue.status == "excluded_multi_company"
    assert article.extraction_exclusion_reason == "multi_financial_institution_roundup"
    assert db_session.query(DimProduct).count() == 0
