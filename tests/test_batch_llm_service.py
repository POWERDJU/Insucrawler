import json

from app.db.models import FactArticle, FactLLMBatchJob, FactLLMCostLog, FactLLMQueue, FactLLMRun
from app.services.batch_llm_service import BatchLLMService


def extraction_payload(raw_product_name="배치 테스트 보험"):
    return {
        "article_relevance": {"is_relevant": True, "relevance_type": "new_product", "reason": "batch test"},
        "products": [
            {
                "identity": {
                    "raw_product_name": raw_product_name,
                    "normalized_product_name_candidate": raw_product_name,
                    "insurance_type": "unknown",
                    "release_year_month": "2026-01",
                    "release_year_month_basis": "explicit_in_article",
                },
                "product_type_classification": {
                    "primary_product_type": {"code": "OTHER", "name_ko": "기타", "basis": "unit", "evidence_text": raw_product_name, "confidence": 0.8},
                    "secondary_product_types": [],
                    "needs_human_review": False,
                },
                "evidence": {"product_name_evidence": raw_product_name},
                "confidence": {"identity": 0.8, "product_type": 0.8, "features": 0.5, "coverage": 0.5, "sales": 0.5, "narrative": 0.5},
            }
        ],
    }


class MockGeminiBatchAdapter:
    def __init__(self):
        self.state = "JOB_STATE_RUNNING"
        self.output_file_name = "files/mock-output"

    def submit_jsonl(self, *, input_file_path, model_name, display_name):
        return type(
            "Result",
            (),
            {"provider_batch_id": "batches/mock-1", "provider_status": "JOB_STATE_PENDING", "provider_input_file_name": "files/mock-input"},
        )()

    def get_status(self, provider_batch_id):
        return type(
            "Status",
            (),
            {
                "provider_batch_id": provider_batch_id,
                "provider_status": self.state,
                "completed": self.state == "JOB_STATE_SUCCEEDED",
                "output_file_name": self.output_file_name if self.state == "JOB_STATE_SUCCEEDED" else None,
                "completed_count": 1 if self.state == "JOB_STATE_SUCCEEDED" else 0,
                "failed_count": 0,
                "error_message": None,
            },
        )()

    def download_results(self, *, output_file_name, output_file_path):
        line = {
            "key": "1",
            "response": {
                "candidates": [{"content": {"parts": [{"text": json.dumps(extraction_payload(), ensure_ascii=False)}]}}],
                "usageMetadata": {"promptTokenCount": 100, "candidatesTokenCount": 80},
            },
        }
        with open(output_file_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
        return output_file_path


def add_article(db_session, article_id=1):
    article = FactArticle(
        article_id=article_id,
        source_api="naver",
        title="배치 테스트 보험 출시",
        description="보험 신상품 출시 기사",
        url=f"https://example.test/{article_id}",
        content_hash=f"batch-hash-{article_id}",
    )
    db_session.add(article)
    db_session.flush()
    return article


def test_batch_input_jsonl_and_job_record_created(db_session, tmp_path):
    article = add_article(db_session)
    queue = FactLLMQueue(target_type="article", target_id=article.article_id, task_type="extract", priority="medium", batch_eligible_yn=True)
    db_session.add(queue)
    db_session.flush()

    job = BatchLLMService().create_batch_input(
        db_session,
        queue_items=[queue],
        provider="gemini",
        model_name="default",
        task_type="extract",
        output_dir=tmp_path,
    )

    assert job.request_count == 1
    assert job.input_file_path
    text = open(job.input_file_path, encoding="utf-8").read()
    assert '"key":' in text
    assert '"request":' in text
    assert queue.status == "running"
    assert queue.llm_batch_job_id == job.llm_batch_job_id


def test_batch_submit_status_and_import_results(db_session, tmp_path):
    article = add_article(db_session)
    queue = FactLLMQueue(target_type="article", target_id=article.article_id, task_type="extract", priority="medium", batch_eligible_yn=True)
    db_session.add(queue)
    db_session.flush()
    adapter = MockGeminiBatchAdapter()
    service = BatchLLMService(adapter=adapter)
    job = service.create_batch_input(db_session, queue_items=[queue], provider="gemini", model_name="default", task_type="extract", output_dir=tmp_path)
    service.submit_batch(db_session, job)

    assert job.provider_batch_id == "batches/mock-1"
    assert job.status == "submitted"

    adapter.state = "JOB_STATE_SUCCEEDED"
    service.refresh_status(db_session, job)
    result = service.import_results(db_session, job)

    assert job.provider_status == "JOB_STATE_SUCCEEDED"
    assert result == {"completed": 1, "failed": 0, "skipped": 0}
    assert queue.status == "completed"
    run = db_session.query(FactLLMRun).filter(FactLLMRun.llm_queue_id == queue.llm_queue_id).one()
    assert run.batch_yn is True
    assert run.llm_batch_job_id == job.llm_batch_job_id
    cost = db_session.query(FactLLMCostLog).filter(FactLLMCostLog.llm_run_id == run.llm_run_id).one()
    assert cost.batch_yn is True
    assert cost.estimated_cost_usd > 0


def test_batch_import_is_idempotent(db_session, tmp_path):
    article = add_article(db_session)
    queue = FactLLMQueue(target_type="article", target_id=article.article_id, task_type="extract", priority="medium", batch_eligible_yn=True)
    db_session.add(queue)
    db_session.flush()
    service = BatchLLMService()
    job = service.create_batch_input(db_session, queue_items=[queue], provider="gemini", model_name="default", task_type="extract", output_dir=tmp_path)
    output = tmp_path / "out.jsonl"
    line = {
        "key": str(queue.llm_queue_id),
        "response": {"candidates": [{"content": {"parts": [{"text": json.dumps(extraction_payload(), ensure_ascii=False)}]}}]},
    }
    output.write_text(json.dumps(line, ensure_ascii=False) + "\n", encoding="utf-8")

    first = service.import_results(db_session, job, output)
    second = service.import_results(db_session, job, output)

    assert first == {"completed": 1, "failed": 0, "skipped": 0}
    assert second == {"completed": 0, "failed": 0, "skipped": 1}
    assert db_session.query(FactLLMRun).filter(FactLLMRun.llm_queue_id == queue.llm_queue_id).count() == 1


def test_batch_import_marks_failed_output(db_session, tmp_path):
    article = add_article(db_session)
    queue = FactLLMQueue(target_type="article", target_id=article.article_id, task_type="extract", priority="medium", batch_eligible_yn=True)
    db_session.add(queue)
    db_session.flush()
    job = BatchLLMService().create_batch_input(db_session, queue_items=[queue], provider="gemini", model_name="default", task_type="extract", output_dir=tmp_path)
    output = tmp_path / "failed.jsonl"
    output.write_text(json.dumps({"key": str(queue.llm_queue_id), "error": {"message": "bad request"}}, ensure_ascii=False) + "\n", encoding="utf-8")

    result = BatchLLMService().import_results(db_session, job, output)

    assert result["failed"] == 1
    assert queue.status == "failed"
    assert "bad request" in queue.last_error
    assert job.status == "completed_with_errors"
