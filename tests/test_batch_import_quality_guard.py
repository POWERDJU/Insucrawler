import json

from app.db.models import DimProduct, FactArticle, FactLLMBatchJob, FactLLMQueue
from app.services.batch_llm_service import BatchLLMService
from app.utils.hashing import article_dedup_hash


def test_batch_import_revalidates_bad_product_name_before_save(db_session, tmp_path):
    article = FactArticle(
        source_api="test",
        title="삼성화재, 신규 보장 상품 출시",
        description="삼성화재는 신규 보장 상품을 출시했다.",
        publisher="test",
        url="https://example.com/bad-name-batch",
        original_url="https://example.com/bad-name-batch",
        query="test",
        query_group="test",
        content_hash=article_dedup_hash("https://example.com/bad-name-batch", "삼성화재, 신규 보장 상품 출시", ""),
        extraction_status="queued",
    )
    db_session.add(article)
    db_session.flush()
    queue = FactLLMQueue(
        target_type="article",
        target_id=article.article_id,
        task_type="extract",
        priority="medium",
        batch_eligible_yn=True,
        status="running",
    )
    db_session.add(queue)
    job = FactLLMBatchJob(
        provider="gemini",
        model_name="gemini-2.5-flash-lite",
        task_type="extract",
        status="provider_completed",
        provider_status="JOB_STATE_SUCCEEDED",
        request_count=1,
    )
    db_session.add(job)
    db_session.flush()

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
                                                    "raw_product_name": "먼저보험",
                                                    "normalized_product_name_candidate": "먼저보험",
                                                    "company_name_raw": "삼성화재",
                                                    "company_name_candidate": "삼성화재",
                                                    "insurance_type": "손해보험",
                                                    "release_year_month": "2026-01",
                                                    "release_year_month_basis": "explicit_in_article",
                                                },
                                                "product_type_classification": {
                                                    "primary_product_type": {
                                                        "code": "OTHER",
                                                        "name_ko": "기타",
                                                        "basis": "fixture",
                                                        "evidence_text": "먼저보험",
                                                        "confidence": 0.8,
                                                    },
                                                    "secondary_product_types": [],
                                                    "needs_human_review": False,
                                                },
                                                "evidence": {"product_name_evidence": "먼저보험", "company_evidence": "삼성화재"},
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
    output = tmp_path / "bad-product-name-output.jsonl"
    output.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")

    result = BatchLLMService().import_results(db_session, job, output)

    assert result == {"completed": 1, "failed": 0, "skipped": 0}
    assert queue.status == "completed"
    assert db_session.query(DimProduct).count() == 0
