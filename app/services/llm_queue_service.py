from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import FactLLMQueue


class LLMQueueService:
    def enqueue(
        self,
        db: Session,
        *,
        target_type: str,
        target_id: int,
        task_type: str,
        priority: str = "medium",
        provider: str | None = None,
        model_name: str | None = None,
        batch_eligible_yn: bool = False,
    ) -> FactLLMQueue:
        existing = (
            db.query(FactLLMQueue)
            .filter(
                FactLLMQueue.target_type == target_type,
                FactLLMQueue.target_id == target_id,
                FactLLMQueue.task_type == task_type,
                FactLLMQueue.status.in_(["pending", "running"]),
            )
            .first()
        )
        if existing:
            return existing
        item = FactLLMQueue(
            target_type=target_type,
            target_id=target_id,
            task_type=task_type,
            priority=priority,
            provider=provider,
            model_name=model_name,
            batch_eligible_yn=batch_eligible_yn,
            status="pending",
        )
        db.add(item)
        db.flush()
        return item

    def complete(self, db: Session, queue_item: FactLLMQueue | None) -> None:
        if queue_item:
            queue_item.status = "completed"
            db.flush()

    def fail(self, db: Session, queue_item: FactLLMQueue | None, error: str) -> None:
        if queue_item:
            queue_item.status = "failed"
            queue_item.attempts += 1
            queue_item.last_error = error
            db.flush()
