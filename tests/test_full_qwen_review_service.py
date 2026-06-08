from app.db.models import FactQwenReviewAudit
from app.services.full_data_review_service import FullDataReviewService, FullReviewRequestData


def test_full_review_service_records_disabled_qwen_audit(monkeypatch, db_session, tmp_path):
    monkeypatch.setenv("ENABLE_FINAL_ADJUDICATION_LLM", "false")
    service = FullDataReviewService(output_dir=tmp_path, docs_dir=tmp_path)

    result = service.run(
        db_session,
        FullReviewRequestData(
            mode="dry_run",
            include_rule_review=False,
            include_qwen=True,
            max_products=1,
            max_exclusive=1,
        ),
    )

    audit_count = db_session.query(FactQwenReviewAudit).count()
    assert result["status"] == "completed"
    assert result["qwen_processed_count"] == 0
    assert audit_count == 1
    assert result["report_path"]
