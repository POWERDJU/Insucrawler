from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class LLMRunResponse(BaseModel):
    llm_run_id: int
    task_type: str
    provider: str
    model_name: str
    validation_status: str | None = None
    latency_ms: int | None = None
    token_input: int | None = None
    token_output: int | None = None
    created_at: datetime
