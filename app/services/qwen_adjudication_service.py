from __future__ import annotations

import json
import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import FactQwenReviewAudit
from app.services.final_adjudication_provider_factory import (
    build_final_adjudication_provider,
    final_adjudication_llm_enabled,
)
from app.utils.dates import utcnow


QWEN_PRODUCT_FINAL_REVIEW_TASK_TYPE = "qwen_product_final_review"
QWEN_EXCLUSIVE_RIGHT_FINAL_REVIEW_TASK_TYPE = "qwen_exclusive_right_final_review"
QWEN_ARTICLE_ELIGIBILITY_REVIEW_TASK_TYPE = "qwen_article_eligibility_review"
QWEN_SALES_METRIC_REVIEW_TASK_TYPE = "qwen_sales_metric_review"
QWEN_COVERAGE_DEDUPE_REVIEW_TASK_TYPE = "qwen_coverage_dedupe_review"

QWEN_FINAL_TASK_TYPES = {
    QWEN_PRODUCT_FINAL_REVIEW_TASK_TYPE,
    QWEN_EXCLUSIVE_RIGHT_FINAL_REVIEW_TASK_TYPE,
    QWEN_ARTICLE_ELIGIBILITY_REVIEW_TASK_TYPE,
    QWEN_SALES_METRIC_REVIEW_TASK_TYPE,
    QWEN_COVERAGE_DEDUPE_REVIEW_TASK_TYPE,
}


@dataclass(frozen=True)
class FinalDecisionChoice:
    decision: str
    source: str
    reason: str
    confidence: float = 0.0
    payload: dict[str, Any] | None = None


@contextmanager
def final_adjudication_disabled() -> Any:
    """Temporarily disable live final LLM during Gemini batch import."""

    previous = os.environ.get("ENABLE_FINAL_ADJUDICATION_LLM")
    os.environ["ENABLE_FINAL_ADJUDICATION_LLM"] = "false"
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("ENABLE_FINAL_ADJUDICATION_LLM", None)
        else:
            os.environ["ENABLE_FINAL_ADJUDICATION_LLM"] = previous


class QwenAdjudicationService:
    """Run compact-context Qwen final review in chunks and summarize audit."""

    def run_chunk(
        self,
        db: Session,
        *,
        full_review_job_id: int | None = None,
        crawl_job_id: int | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        apply: bool = False,
        limit_products: int = 50,
        limit_exclusive: int = 30,
        max_scan_products: int = 2500,
        max_scan_exclusive: int = 1500,
        exhaustive: bool = False,
        products_only: bool = False,
        exclusive_only: bool = False,
        provider: Any | None = None,
    ) -> dict[str, Any]:
        if not final_adjudication_llm_enabled() and provider is None:
            summary = {
                "status": "disabled",
                "message": "ENABLE_FINAL_ADJUDICATION_LLM is not true",
                "apply": apply,
                "crawl_job_id": crawl_job_id,
                "date_from": date_from,
                "date_to": date_to,
                "exhaustive": exhaustive,
                "products": {},
                "exclusive_rights": {},
            }
            self._audit_summary(db, full_review_job_id=full_review_job_id, crawl_job_id=crawl_job_id, summary=summary)
            db.commit()
            return summary
        active_provider = provider or build_final_adjudication_provider()
        if active_provider is None:
            summary = {
                "status": "disabled",
                "message": "final adjudication provider is not configured",
                "apply": apply,
                "crawl_job_id": crawl_job_id,
                "date_from": date_from,
                "date_to": date_to,
                "exhaustive": exhaustive,
                "products": {},
                "exclusive_rights": {},
            }
            self._audit_summary(db, full_review_job_id=full_review_job_id, crawl_job_id=crawl_job_id, summary=summary)
            db.commit()
            return summary

        from scripts.run_qwen_final_adjudication import (
            run_exclusive_adjudication,
            run_product_adjudication,
        )

        summary: dict[str, Any] = {
            "status": "completed",
            "apply": apply,
            "crawl_job_id": crawl_job_id,
            "date_from": date_from,
            "date_to": date_to,
            "exhaustive": exhaustive,
            "products": {},
            "exclusive_rights": {},
        }
        if not exclusive_only and limit_products > 0:
            summary["products"] = run_product_adjudication(
                db,
                provider=active_provider,
                apply=apply,
                crawl_job_id=crawl_job_id,
                full_review_job_id=full_review_job_id,
                date_from=date_from,
                date_to=date_to,
                exhaustive=exhaustive,
                limit=limit_products,
                max_scan=max_scan_products,
            )
        if not products_only and limit_exclusive > 0:
            summary["exclusive_rights"] = run_exclusive_adjudication(
                db,
                provider=active_provider,
                apply=apply,
                crawl_job_id=crawl_job_id,
                full_review_job_id=full_review_job_id,
                date_from=date_from,
                date_to=date_to,
                exhaustive=exhaustive,
                limit=limit_exclusive,
                max_scan=max_scan_exclusive,
            )
        self._audit_summary(db, full_review_job_id=full_review_job_id, crawl_job_id=crawl_job_id, summary=summary)
        db.commit()
        return summary

    def candidate_counts(
        self,
        db: Session,
        *,
        crawl_job_id: int | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        exhaustive: bool = False,
    ) -> dict[str, int]:
        from scripts.run_qwen_final_adjudication import candidate_exclusive_count, candidate_product_count

        return {
            "products": int(candidate_product_count(db, crawl_job_id=crawl_job_id, date_from=date_from, date_to=date_to, exhaustive=exhaustive)),
            "exclusive_rights": int(candidate_exclusive_count(db, crawl_job_id=crawl_job_id, date_from=date_from, date_to=date_to, exhaustive=exhaustive)),
        }

    def choose_final_decision(
        self,
        *,
        rule_decision: dict[str, Any] | None,
        qwen_decision: dict[str, Any] | None,
        hard_gate_errors: list[str] | tuple[str, ...] | None = None,
    ) -> FinalDecisionChoice:
        hard_gates = [item for item in (hard_gate_errors or []) if item]
        if hard_gates:
            return FinalDecisionChoice(
                decision="review",
                source="hard_gate",
                reason=";".join(hard_gates),
                confidence=0.0,
                payload={"rule": rule_decision, "qwen": qwen_decision},
            )
        if qwen_decision:
            return FinalDecisionChoice(
                decision=str(qwen_decision.get("decision") or "review"),
                source="qwen",
                reason=str(qwen_decision.get("reason") or "qwen_priority"),
                confidence=float(qwen_decision.get("confidence") or 0.0),
                payload=qwen_decision,
            )
        rule = rule_decision or {}
        return FinalDecisionChoice(
            decision=str(rule.get("decision") or "review"),
            source="rule",
            reason=str(rule.get("reason") or "rule_only"),
            confidence=float(rule.get("confidence") or 0.0),
            payload=rule,
        )

    def validate_hard_gates(self, payload: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        decision = str(payload.get("decision") or "").lower()
        if decision == "accept":
            if not payload.get("company_id") and not payload.get("company_name"):
                errors.append("company_master_absent")
            if payload.get("article_suitability") in {"non_insurance", "ineligible_article"}:
                errors.append("non_insurance_accept_blocked")
        for key in ("release_year_month", "acquired_year_month"):
            value = payload.get(key)
            if value is not None and not self._valid_year_month(str(value)):
                errors.append(f"invalid_{key}")
        if payload.get("company_role") in {"reinsurer", "foreign_branch"} and decision == "accept":
            errors.append("ineligible_company_role")
        return errors

    @staticmethod
    def _valid_year_month(value: str) -> bool:
        if len(value) != 7 or value[4] != "-":
            return False
        try:
            year = int(value[:4])
            month = int(value[5:7])
        except ValueError:
            return False
        return 1900 <= year <= 2100 and 1 <= month <= 12

    def _audit_summary(
        self,
        db: Session,
        *,
        full_review_job_id: int | None,
        crawl_job_id: int | None,
        summary: dict[str, Any],
    ) -> None:
        products = summary.get("products") or {}
        exclusive = summary.get("exclusive_rights") or {}
        db.add(
            FactQwenReviewAudit(
                full_review_job_id=full_review_job_id,
                target_type="summary",
                target_id=None,
                crawl_job_id=crawl_job_id,
                task_type="qwen_final_review_summary",
                provider="qwen",
                model_name=os.getenv("QWEN_FINAL_ADJUDICATION_MODEL") or os.getenv("FINAL_ADJUDICATION_MODEL"),
                decision=str(summary.get("status") or "completed"),
                confidence=0.0,
                reason=summary.get("message"),
                before_json=None,
                after_json=json.dumps(summary, ensure_ascii=False),
                warnings_json=json.dumps(
                    {
                        "product_errors": products.get("errors", []),
                        "exclusive_errors": exclusive.get("errors", []),
                    },
                    ensure_ascii=False,
                ),
                hard_gate_status="summary",
                apply_status="applied" if summary.get("apply") else "not_applied",
                override_reason="qwen_priority" if summary.get("status") == "completed" else None,
            )
        )
