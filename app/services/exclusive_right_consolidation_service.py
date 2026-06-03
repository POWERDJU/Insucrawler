from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import json
from difflib import SequenceMatcher
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import (
    FactArticle,
    FactExclusiveUseRight,
    FactExclusiveUseRightAlias,
    FactExclusiveUseRightArticle,
    FactExclusiveUseRightMergeDecision,
)
from app.services.exclusive_right_local_context import (
    has_bad_subject_tail,
    is_generic_or_weak_subject,
)
from app.normalizers.exclusive_right_subject_normalizer import (
    build_exclusive_subject_tokens,
    canonical_subject_score,
    exclusive_event_similarity,
    exclusive_subject_component_set,
    is_allowed_canonical_exclusive_subject,
)
from app.utils.text import normalize_search_key
from app.utils.dates import utcnow


@dataclass
class ExclusiveRightBlock:
    candidates: list[FactExclusiveUseRight]
    reason: str


class ExclusiveRightBlockingService:
    STOPWORDS = {
        "보험",
        "상품",
        "특약",
        "담보",
        "서비스",
        "제도",
        "배타적사용권",
        "배타적",
        "사용권",
        "획득",
        "부여",
        "인정",
        "개월",
        "신상품",
        "해당",
        "이번",
        "관련",
        "보장",
        "지급",
        "방식",
        "구조",
    }

    def build_blocks(
        self,
        db: Session,
        *,
        crawl_job_id: int | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[ExclusiveRightBlock]:
        query = db.query(FactExclusiveUseRight).filter(FactExclusiveUseRight.event_status.notin_(["merged", "rejected"]))
        if crawl_job_id is not None or date_from or date_to:
            query = query.join(FactExclusiveUseRightArticle, FactExclusiveUseRightArticle.exclusive_right_id == FactExclusiveUseRight.exclusive_right_id)
            query = query.join(FactArticle, FactArticle.article_id == FactExclusiveUseRightArticle.article_id)
            if crawl_job_id is not None:
                query = query.filter(FactArticle.crawl_job_id == crawl_job_id)
            if date_from:
                query = query.filter(FactArticle.pub_date >= datetime.fromisoformat(date_from))
            if date_to:
                query = query.filter(FactArticle.pub_date < datetime.fromisoformat(date_to) + timedelta(days=1))
        candidates = query.order_by(FactExclusiveUseRight.exclusive_right_id).distinct().all()
        if len(candidates) < 2:
            return []
        by_id = {item.exclusive_right_id: item for item in candidates}
        graph: dict[int, set[int]] = {item.exclusive_right_id: set() for item in candidates}
        for index, left in enumerate(candidates):
            for right in candidates[index + 1 :]:
                if self.same_block(left, right):
                    graph[left.exclusive_right_id].add(right.exclusive_right_id)
                    graph[right.exclusive_right_id].add(left.exclusive_right_id)

        blocks: list[ExclusiveRightBlock] = []
        visited: set[int] = set()
        for start_id in graph:
            if start_id in visited:
                continue
            stack = [start_id]
            component_ids: set[int] = set()
            while stack:
                current = stack.pop()
                if current in component_ids:
                    continue
                component_ids.add(current)
                stack.extend(graph[current] - component_ids)
            visited.update(component_ids)
            if len(component_ids) > 1:
                blocks.append(
                    ExclusiveRightBlock(
                        [by_id[item_id] for item_id in sorted(component_ids)],
                        "company_subject_month_period_component_context",
                    )
                )
        return blocks

    def same_block(self, left: FactExclusiveUseRight, right: FactExclusiveUseRight) -> bool:
        if left.company_id and right.company_id and left.company_id != right.company_id:
            return False
        if not self._month_close(left.acquired_year_month, right.acquired_year_month):
            return False
        name_similarity = self._similarity(left.subject_name, right.subject_name)
        core_equal = bool(left.subject_core_key and left.subject_core_key == right.subject_core_key)
        scores = exclusive_event_similarity(left, right)
        context_similarity = max(
            self._context_similarity(left, right),
            scores["subject_overlap"],
            scores["component_overlap"],
            scores["evidence_overlap"],
        )
        shared_tokens = self._shared_high_info_tokens(left, right)
        return (
            core_equal
            or name_similarity >= 0.82
            or scores["subject_overlap"] >= 0.55
            or scores["component_overlap"] >= 0.55
            or scores["evidence_overlap"] >= 0.50
            or context_similarity >= 0.50
            or len(shared_tokens) >= 2
        )

    @staticmethod
    def _month_close(left: str | None, right: str | None) -> bool:
        if not left or not right:
            return True
        try:
            left_year, left_month = [int(part) for part in left.split("-", 1)]
            right_year, right_month = [int(part) for part in right.split("-", 1)]
        except ValueError:
            return False
        return abs((left_year * 12 + left_month) - (right_year * 12 + right_month)) <= 3

    @staticmethod
    def _similarity(left: str | None, right: str | None) -> float:
        left_key = normalize_search_key(left)
        right_key = normalize_search_key(right)
        if not left_key or not right_key:
            return 0.0
        return SequenceMatcher(None, left_key, right_key).ratio()

    def _context_similarity(self, left: FactExclusiveUseRight, right: FactExclusiveUseRight) -> float:
        left_tokens = self._high_info_tokens(left)
        right_tokens = self._high_info_tokens(right)
        if not left_tokens or not right_tokens:
            return 0.0
        return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)

    def _shared_high_info_tokens(self, left: FactExclusiveUseRight, right: FactExclusiveUseRight) -> set[str]:
        return self._high_info_tokens(left) & self._high_info_tokens(right)

    def _high_info_tokens(self, item: FactExclusiveUseRight) -> set[str]:
        aliases = self._json_load(item.alias_names_json)
        tokens = build_exclusive_subject_tokens(
            item.subject_name,
            item.feature_summary,
            item.evidence_summary,
            item.evidence_text,
            " ".join(aliases),
        )
        tokens.update(exclusive_subject_component_set(item.subject_name, aliases, item.evidence_text))
        return {token for token in tokens if len(token) >= 2 and token not in self.STOPWORDS}

    @staticmethod
    def _json_load(value: str | None) -> list[str]:
        if not value:
            return []
        try:
            payload = json.loads(value)
            return [str(item) for item in payload if item]
        except json.JSONDecodeError:
            return []


class ExclusiveRightConsolidationService:
    def __init__(self, blocking_service: ExclusiveRightBlockingService | None = None) -> None:
        self.blocking_service = blocking_service or ExclusiveRightBlockingService()

    def run(
        self,
        db: Session,
        *,
        mode: str = "rule_only_apply",
        crawl_job_id: int | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> dict[str, Any]:
        blocks = self.blocking_service.build_blocks(db, crawl_job_id=crawl_job_id, date_from=date_from, date_to=date_to)
        auto_merge_count = 0
        review_count = 0
        for block in blocks:
            action = self._block_action(block.candidates)
            if action == "review":
                review_count += 1
                for candidate in block.candidates:
                    candidate.needs_review = True
                continue
            if mode == "dry_run":
                continue
            canonical = self._canonical_candidate(block.candidates)
            for duplicate in block.candidates:
                if duplicate.exclusive_right_id == canonical.exclusive_right_id:
                    continue
                self._merge(db, canonical, duplicate, decision_source=action)
                auto_merge_count += 1
        db.commit()
        return {
            "block_count": len(blocks),
            "auto_merge_count": auto_merge_count,
            "review_count": review_count,
            "mode": mode,
            "crawl_job_id": crawl_job_id,
            "date_from": date_from,
            "date_to": date_to,
        }

    def _block_action(self, candidates: list[FactExclusiveUseRight]) -> str:
        months = {item.exclusivity_months for item in candidates if item.exclusivity_months is not None}
        companies = {item.company_id for item in candidates if item.company_id is not None}
        if len(months) > 1 or len(companies) > 1:
            return "review"
        strong_candidates = [item for item in candidates if self._is_strong_subject(item.subject_name)]
        if not strong_candidates:
            return "review"
        cores = {item.subject_core_key for item in candidates if item.subject_core_key}
        if len(cores) == 1:
            return "deterministic_subject_core_key"
        scores = [
            exclusive_event_similarity(left, right)
            for index, left in enumerate(candidates)
            for right in candidates[index + 1 :]
        ]
        if any(score["component_overlap"] >= 0.55 for score in scores):
            return "deterministic_exclusive_component_overlap"
        if any(score["evidence_overlap"] >= 0.50 for score in scores):
            return "deterministic_exclusive_evidence_overlap"
        return "deterministic_subject_context_similarity"

    @staticmethod
    def _canonical_candidate(candidates: list[FactExclusiveUseRight]) -> FactExclusiveUseRight:
        return sorted(
            candidates,
            key=lambda item: (
                item.needs_review,
                -canonical_subject_score(item.subject_name, item.evidence_text, ExclusiveRightConsolidationService._json_load(item.alias_names_json))[0],
                -canonical_subject_score(item.subject_name, item.evidence_text, ExclusiveRightConsolidationService._json_load(item.alias_names_json))[1],
                -canonical_subject_score(item.subject_name, item.evidence_text, ExclusiveRightConsolidationService._json_load(item.alias_names_json))[2],
                -(item.confidence_total or 0),
                item.exclusive_right_id,
            ),
        )[0]

    @staticmethod
    def _is_strong_subject(subject_name: str | None) -> bool:
        return is_allowed_canonical_exclusive_subject(subject_name) and not is_generic_or_weak_subject(subject_name) and not has_bad_subject_tail(subject_name)

    def _merge(self, db: Session, canonical: FactExclusiveUseRight, duplicate: FactExclusiveUseRight, *, decision_source: str) -> None:
        duplicate.event_status = "merged"
        duplicate.merged_into_exclusive_right_id = canonical.exclusive_right_id
        duplicate.canonical_exclusive_right_id = canonical.exclusive_right_id
        aliases = set(self._json_load(canonical.alias_names_json))
        aliases.update(self._json_load(duplicate.alias_names_json))
        aliases.add(duplicate.subject_name)
        canonical.alias_names_json = json.dumps(sorted(alias for alias in aliases if alias), ensure_ascii=False)
        canonical.confidence_total = max(float(canonical.confidence_total or 0), float(duplicate.confidence_total or 0))
        for link in db.query(FactExclusiveUseRightArticle).filter(FactExclusiveUseRightArticle.exclusive_right_id == duplicate.exclusive_right_id).all():
            existing = (
                db.query(FactExclusiveUseRightArticle)
                .filter(FactExclusiveUseRightArticle.exclusive_right_id == canonical.exclusive_right_id, FactExclusiveUseRightArticle.article_id == link.article_id)
                .first()
            )
            if existing:
                db.delete(link)
                continue
            link.exclusive_right_id = canonical.exclusive_right_id
        for alias in db.query(FactExclusiveUseRightAlias).filter(FactExclusiveUseRightAlias.exclusive_right_id == duplicate.exclusive_right_id).all():
            existing_alias = (
                db.query(FactExclusiveUseRightAlias)
                .filter(
                    FactExclusiveUseRightAlias.exclusive_right_id == canonical.exclusive_right_id,
                    FactExclusiveUseRightAlias.raw_subject_name == alias.raw_subject_name,
                    FactExclusiveUseRightAlias.article_id == alias.article_id,
                )
                .first()
            )
            if existing_alias:
                db.delete(alias)
                continue
            alias.exclusive_right_id = canonical.exclusive_right_id
        db.flush()
        canonical.article_count = max(int(canonical.article_count or 0), len(set(self._article_ids(db, canonical.exclusive_right_id))))
        db.add(
            FactExclusiveUseRightMergeDecision(
                canonical_exclusive_right_id=canonical.exclusive_right_id,
                duplicate_exclusive_right_id=duplicate.exclusive_right_id,
                decision_type="auto_merge",
                decision_source=decision_source,
                confidence=0.95 if decision_source == "deterministic_subject_core_key" else 0.90,
                reason="Same company, similar subject, close acquired month, and compatible exclusive-use-right type.",
                evidence_article_ids_json=json.dumps(self._article_ids(db, canonical.exclusive_right_id), ensure_ascii=False),
                alias_names_json=canonical.alias_names_json,
                applied_at=utcnow(),
                needs_review=False,
            )
        )

    @staticmethod
    def _article_ids(db: Session, exclusive_right_id: int) -> list[int]:
        return [
            row.article_id
            for row in db.query(FactExclusiveUseRightArticle)
            .filter(FactExclusiveUseRightArticle.exclusive_right_id == exclusive_right_id)
            .all()
        ]

    @staticmethod
    def _json_load(value: str | None) -> list[str]:
        if not value:
            return []
        try:
            payload = json.loads(value)
            return [str(item) for item in payload if item]
        except json.JSONDecodeError:
            return []
