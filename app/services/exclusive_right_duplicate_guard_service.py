from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.exclusive_right_consolidation_service import ExclusiveRightBlockingService
from app.normalizers.exclusive_right_subject_normalizer import (
    exclusive_event_similarity,
    exclusive_subject_component_set,
)


class ExclusiveRightDuplicateGuardService:
    """Find likely duplicate exclusive-use-right events without calling LLM."""

    def __init__(self, blocking_service: ExclusiveRightBlockingService | None = None) -> None:
        self.blocking_service = blocking_service or ExclusiveRightBlockingService()

    def find_duplicate_groups(self, db: Session) -> list[dict[str, Any]]:
        groups: list[dict[str, Any]] = []
        for block in self.blocking_service.build_blocks(db):
            ids = [item.exclusive_right_id for item in block.candidates]
            if len(ids) < 2:
                continue
            scores = [
                exclusive_event_similarity(left, right)
                for index, left in enumerate(block.candidates)
                for right in block.candidates[index + 1 :]
            ]
            max_component = max((score["component_overlap"] for score in scores), default=0.0)
            max_subject = max((score["subject_overlap"] for score in scores), default=0.0)
            max_evidence = max((score["evidence_overlap"] for score in scores), default=0.0)
            groups.append(
                {
                    "company_name": block.candidates[0].company_name_normalized,
                    "company_id": block.candidates[0].company_id,
                    "exclusive_right_ids": ids,
                    "subject_names": [item.subject_name for item in block.candidates],
                    "subject_signature": self._subject_signature(block.candidates),
                    "max_component_overlap": round(max_component, 4),
                    "max_subject_overlap": round(max_subject, 4),
                    "max_evidence_overlap": round(max_evidence, 4),
                    "suggested_action": "run_exclusive_right_consolidation",
                }
            )
        return groups

    @staticmethod
    def _subject_signature(candidates: list[Any]) -> str:
        components: set[str] = set()
        for item in candidates:
            components.update(exclusive_subject_component_set(item.subject_name, [], item.evidence_text))
        return " ".join(sorted(components))[:200]
