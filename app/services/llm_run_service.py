from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models import FactLLMRun


class LLMRunService:
    def list_runs(self, db: Session, limit: int = 100) -> list[FactLLMRun]:
        return db.query(FactLLMRun).order_by(FactLLMRun.llm_run_id.desc()).limit(limit).all()

    def metrics(self, db: Session) -> dict:
        by_model = db.execute(
            text(
                """
                SELECT provider, model_name, task_type,
                       COUNT(*) AS run_count,
                       AVG(latency_ms) AS avg_latency_ms,
                       SUM(COALESCE(token_input, 0)) AS token_input,
                       SUM(COALESCE(token_output, 0)) AS token_output,
                       SUM(CASE WHEN validation_status = 'schema_fail' THEN 1 ELSE 0 END) AS schema_fail_count,
                       SUM(CASE WHEN validation_status = 'pass' THEN 1 ELSE 0 END) AS pass_count
                FROM fact_llm_run
                GROUP BY provider, model_name, task_type
                ORDER BY run_count DESC
                """
            )
        ).mappings().all()
        field_errors = db.execute(
            text(
                """
                SELECT field_path, verifier_verdict, COUNT(*) AS count
                FROM fact_extraction_field_audit
                GROUP BY field_path, verifier_verdict
                ORDER BY count DESC
                """
            )
        ).mappings().all()
        return {"by_model": [dict(row) for row in by_model], "field_errors": [dict(row) for row in field_errors]}
