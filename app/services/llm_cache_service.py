from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.db.models import FactLLMResponseCache
from app.utils.dates import utcnow
from app.utils.hashing import sha256_text


class LLMCacheService:
    @staticmethod
    def input_hash(input_text: str) -> str:
        normalized = "\n".join(line.strip() for line in (input_text or "").splitlines() if line.strip())
        return sha256_text(normalized)

    def get(
        self,
        db: Session,
        *,
        input_text: str,
        prompt_version: str,
        schema_version: str,
        provider: str,
        model_name: str,
        task_type: str,
    ) -> dict | None:
        item = (
            db.query(FactLLMResponseCache)
            .filter(
                FactLLMResponseCache.input_hash == self.input_hash(input_text),
                FactLLMResponseCache.prompt_version == prompt_version,
                FactLLMResponseCache.schema_version == schema_version,
                FactLLMResponseCache.provider == provider,
                FactLLMResponseCache.model_name == model_name,
                FactLLMResponseCache.task_type == task_type,
            )
            .first()
        )
        if not item:
            return None
        item.hit_count += 1
        item.last_used_at = utcnow()
        db.flush()
        return json.loads(item.output_json)

    def put(
        self,
        db: Session,
        *,
        input_text: str,
        prompt_version: str,
        schema_version: str,
        provider: str,
        model_name: str,
        task_type: str,
        output_json: dict,
    ) -> None:
        existing = self.get(
            db,
            input_text=input_text,
            prompt_version=prompt_version,
            schema_version=schema_version,
            provider=provider,
            model_name=model_name,
            task_type=task_type,
        )
        if existing is not None:
            return
        item = FactLLMResponseCache(
            input_hash=self.input_hash(input_text),
            prompt_version=prompt_version,
            schema_version=schema_version,
            provider=provider,
            model_name=model_name,
            task_type=task_type,
            output_json=json.dumps(output_json, ensure_ascii=False),
        )
        db.add(item)
        db.flush()
