from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import exists
from sqlalchemy.orm import Session

from app.db.models import (
    DimProduct,
    DimProductAlias,
    FactArticle,
    FactExclusiveUseRight,
    FactExclusiveUseRightArticle,
    FactProductArticle,
    FactProductObservation,
    FactQwenReviewAudit,
)
from app.services.article_eligibility_filter_service import ArticleEligibilityFilterService
from app.services.exclusive_right_final_adjudication_service import ExclusiveRightFinalAdjudicationService
from app.services.final_adjudication_provider_factory import build_final_adjudication_provider, final_adjudication_llm_enabled
from app.services.product_final_adjudication_service import ProductFinalAdjudicationService
from app.utils.dates import utcnow

from scripts.run_qwen_final_adjudication import (
    ExclusiveContext,
    ProductContext,
    add_qwen_audit,
    apply_exclusive_decision,
    apply_product_decision,
    current_exclusive_json,
    current_product_json,
)


QWEN_PRODUCT_QUALITY_REVIEW_TASK_TYPE = "qwen_product_quality_review"
QWEN_EXCLUSIVE_RIGHT_QUALITY_REVIEW_TASK_TYPE = "qwen_exclusive_right_quality_review"
QWEN_QUALITY_REVIEWED_STATUS = "qwen_quality_reviewed"


@dataclass(frozen=True)
class QwenQualityReviewRequest:
    mode: str = "dry_run"
    target: str = "all"
    date_from: str | None = "2025-01-01"
    date_to: str | None = "2026-05-31"
    crawl_job_id: int | None = None
    limit_products: int | None = None
    limit_exclusive: int | None = None
    max_scan_products: int | None = None
    max_scan_exclusive: int | None = None
    skip_existing_quality_audit: bool = False
    require_live_qwen: bool = True
    output_dir: str | Path = "data/exports"
    report_path: str | Path = "docs/full-contextual-qwen-quality-goal-result.md"

    @property
    def apply(self) -> bool:
        return self.mode == "apply"


class QwenQualityReviewService:
    """Exhaustive compact-context quality review over current product and exclusive-right data."""

    def __init__(self, *, provider: Any | None = None, article_filter: ArticleEligibilityFilterService | None = None) -> None:
        self.provider = provider
        self.article_filter = article_filter or ArticleEligibilityFilterService()

    def run(self, db: Session, request: QwenQualityReviewRequest) -> dict[str, Any]:
        provider = self.provider or build_final_adjudication_provider()
        if request.require_live_qwen and provider is None:
            summary = {
                "status": "disabled",
                "message": "ENABLE_FINAL_ADJUDICATION_LLM is not true or Qwen provider is not configured",
                "live_qwen_enabled": final_adjudication_llm_enabled(),
                "apply": request.apply,
            }
            self._write_artifacts(summary, request)
            return summary

        started_at = utcnow()
        summary: dict[str, Any] = {
            "status": "running",
            "mode": request.mode,
            "target": request.target,
            "date_from": request.date_from,
            "date_to": request.date_to,
            "crawl_job_id": request.crawl_job_id,
            "started_at": started_at.isoformat(),
            "provider": "qwen" if provider is not None else "rule",
            "products": {},
            "exclusive_rights": {},
        }
        if request.target in {"all", "products"}:
            summary["products"] = self.review_products(db, request, provider=provider)
        if request.target in {"all", "exclusive_rights", "exclusive"}:
            summary["exclusive_rights"] = self.review_exclusive_rights(db, request, provider=provider)

        summary["status"] = "completed"
        summary["finished_at"] = utcnow().isoformat()
        summary["scope_counts"] = self.candidate_counts(db, request=request)
        paths = self._write_artifacts(summary, request)
        summary["artifacts"] = paths
        db.commit()
        return summary

    def review_products(self, db: Session, request: QwenQualityReviewRequest, *, provider: Any | None) -> dict[str, Any]:
        service = ProductFinalAdjudicationService(provider=provider, force_provider=provider is not None)
        query = self._product_query(db, request)
        if request.skip_existing_quality_audit:
            query = self._exclude_existing_quality_audit(
                query,
                target_type="product",
                id_column=DimProduct.product_id,
                task_type=QWEN_PRODUCT_QUALITY_REVIEW_TASK_TYPE,
            )
        max_scan = request.max_scan_products
        if max_scan:
            query = query.limit(max_scan)

        processed = provider_called = accepted = reviewed = rejected = failed = 0
        rows: list[dict[str, Any]] = []
        for product in query.all():
            if request.limit_products is not None and processed >= request.limit_products:
                break
            product_id = product.product_id
            before = current_product_json(product)
            try:
                context = self._product_context(db, product, request)
                payload = service.build_input(
                    db,
                    product_name=product.normalized_product_name,
                    company_name=product.company_name_raw,
                    product_type_code=product.primary_product_type_code,
                    release_year_month=product.release_year_month,
                    release_year_month_basis=product.release_year_month_basis,
                    partner_company_name=product.partner_company_name,
                    partner_role="distribution_partner" if product.partner_company_name else None,
                    partner_context_summary=product.partner_context_summary,
                    candidate_type="existing_dim_product",
                    article=context.article,
                    context_text=context.context_text,
                    aliases=context.aliases,
                )
                decision = service.adjudicate(db, payload)
                processed += 1
                provider_called += int(decision.provider_called)
                if request.apply:
                    if context.article and context.article_decision and not context.article_decision.is_eligible:
                        self.article_filter.mark_article(db, context.article, context.article_decision)
                    apply_product_decision(db, product, decision, context)
                    if decision.decision == "accept":
                        product.consolidation_status = QWEN_QUALITY_REVIEWED_STATUS
                    db.flush()
                after = current_product_json(product)
                add_qwen_audit(
                    db,
                    target_type="product",
                    target_id=product.product_id,
                    task_type=QWEN_PRODUCT_QUALITY_REVIEW_TASK_TYPE,
                    full_review_job_id=None,
                    crawl_job_id=request.crawl_job_id,
                    article_id=context.article.article_id if context.article else None,
                    decision=decision.decision,
                    confidence=decision.confidence,
                    reason=decision.reason,
                    evidence_text=decision.evidence_quote,
                    provider_called=decision.provider_called,
                    apply_status="applied" if request.apply else "not_applied",
                    before_json=before,
                    after_json=after,
                )
                if decision.decision == "accept":
                    accepted += 1
                elif decision.decision in {"reject", "non_insurance", "ineligible_article"}:
                    rejected += 1
                else:
                    reviewed += 1
                rows.append(self._row("product", product.product_id, decision, before, after))
                db.commit()
            except Exception as exc:
                db.rollback()
                reason = f"qwen_quality_review_failed:{exc}"
                if request.apply:
                    fallback = db.get(DimProduct, product_id)
                    if fallback is not None:
                        fallback.needs_review = True
                        fallback.product_status = "review"
                        fallback.consolidation_status = QWEN_QUALITY_REVIEWED_STATUS
                        after = current_product_json(fallback)
                        add_qwen_audit(
                            db,
                            target_type="product",
                            target_id=product_id,
                            task_type=QWEN_PRODUCT_QUALITY_REVIEW_TASK_TYPE,
                            full_review_job_id=None,
                            crawl_job_id=request.crawl_job_id,
                            article_id=None,
                            decision="review",
                            confidence=0.0,
                            reason=reason,
                            evidence_text=None,
                            provider_called=True,
                            apply_status="applied",
                            before_json=before,
                            after_json=after,
                        )
                        db.commit()
                        processed += 1
                        provider_called += 1
                        reviewed += 1
                        rows.append({"target_type": "product", "target_id": product_id, "decision": "review", "confidence": 0.0, "provider_called": True, "reason": reason, "before": json.dumps(before, ensure_ascii=False), "after": json.dumps(after, ensure_ascii=False)})
                        continue
                failed += 1
                rows.append({"target_type": "product", "target_id": product_id, "decision": "error", "reason": str(exc)})
        return {
            "processed": processed,
            "provider_called": provider_called,
            "accepted": accepted,
            "reviewed": reviewed,
            "rejected": rejected,
            "failed": failed,
            "rows": rows,
        }

    def review_exclusive_rights(self, db: Session, request: QwenQualityReviewRequest, *, provider: Any | None) -> dict[str, Any]:
        service = ExclusiveRightFinalAdjudicationService(provider=provider, force_provider=provider is not None)
        query = self._exclusive_query(db, request)
        if request.skip_existing_quality_audit:
            query = self._exclude_existing_quality_audit(
                query,
                target_type="exclusive_right",
                id_column=FactExclusiveUseRight.exclusive_right_id,
                task_type=QWEN_EXCLUSIVE_RIGHT_QUALITY_REVIEW_TASK_TYPE,
            )
        max_scan = request.max_scan_exclusive
        if max_scan:
            query = query.limit(max_scan)

        processed = provider_called = accepted = reviewed = rejected = failed = 0
        rows: list[dict[str, Any]] = []
        for item in query.all():
            if request.limit_exclusive is not None and processed >= request.limit_exclusive:
                break
            exclusive_right_id = item.exclusive_right_id
            before = current_exclusive_json(item)
            try:
                context = self._exclusive_context(db, item, request)
                payload = service.build_input(
                    db,
                    subject_name=item.subject_name,
                    company_name=item.company_name_normalized,
                    acquired_year_month=item.acquired_year_month,
                    exclusivity_months=item.exclusivity_months,
                    article=context.article,
                    context_text=context.context_text,
                    evidence_text=context.evidence_text,
                )
                decision = service.adjudicate(db, payload)
                processed += 1
                provider_called += int(decision.provider_called)
                if request.apply:
                    if context.article and context.article_decision and not context.article_decision.is_eligible:
                        self.article_filter.mark_article(db, context.article, context.article_decision)
                    apply_exclusive_decision(db, item, decision, context)
                    db.flush()
                after = current_exclusive_json(item)
                add_qwen_audit(
                    db,
                    target_type="exclusive_right",
                    target_id=item.exclusive_right_id,
                    task_type=QWEN_EXCLUSIVE_RIGHT_QUALITY_REVIEW_TASK_TYPE,
                    full_review_job_id=None,
                    crawl_job_id=request.crawl_job_id,
                    article_id=context.article.article_id if context.article else None,
                    decision=decision.decision,
                    confidence=decision.confidence,
                    reason=decision.reason,
                    evidence_text=decision.evidence_quote,
                    provider_called=decision.provider_called,
                    apply_status="applied" if request.apply else "not_applied",
                    before_json=before,
                    after_json=after,
                )
                if decision.decision == "accept":
                    accepted += 1
                elif decision.decision in {"reject", "ineligible_article"}:
                    rejected += 1
                else:
                    reviewed += 1
                rows.append(self._row("exclusive_right", item.exclusive_right_id, decision, before, after))
                db.commit()
            except Exception as exc:
                db.rollback()
                reason = f"qwen_quality_review_failed:{exc}"
                if request.apply:
                    fallback = db.get(FactExclusiveUseRight, exclusive_right_id)
                    if fallback is not None:
                        fallback.needs_review = True
                        fallback.event_status = QWEN_QUALITY_REVIEWED_STATUS
                        after = current_exclusive_json(fallback)
                        add_qwen_audit(
                            db,
                            target_type="exclusive_right",
                            target_id=exclusive_right_id,
                            task_type=QWEN_EXCLUSIVE_RIGHT_QUALITY_REVIEW_TASK_TYPE,
                            full_review_job_id=None,
                            crawl_job_id=request.crawl_job_id,
                            article_id=None,
                            decision="review",
                            confidence=0.0,
                            reason=reason,
                            evidence_text=None,
                            provider_called=True,
                            apply_status="applied",
                            before_json=before,
                            after_json=after,
                        )
                        db.commit()
                        processed += 1
                        provider_called += 1
                        reviewed += 1
                        rows.append({"target_type": "exclusive_right", "target_id": exclusive_right_id, "decision": "review", "confidence": 0.0, "provider_called": True, "reason": reason, "before": json.dumps(before, ensure_ascii=False), "after": json.dumps(after, ensure_ascii=False)})
                        continue
                failed += 1
                rows.append({"target_type": "exclusive_right", "target_id": exclusive_right_id, "decision": "error", "reason": str(exc)})
        return {
            "processed": processed,
            "provider_called": provider_called,
            "accepted": accepted,
            "reviewed": reviewed,
            "rejected": rejected,
            "failed": failed,
            "rows": rows,
        }

    def candidate_counts(self, db: Session, *, request: QwenQualityReviewRequest) -> dict[str, int]:
        return {
            "products": int(self._product_query(db, request).count()),
            "exclusive_rights": int(self._exclusive_query(db, request).count()),
        }

    def _product_query(self, db: Session, request: QwenQualityReviewRequest) -> Any:
        query = db.query(DimProduct).filter(DimProduct.merged_into_product_id.is_(None))
        if request.date_from or request.date_to or request.crawl_job_id is not None:
            query = query.join(FactProductArticle, FactProductArticle.product_id == DimProduct.product_id).join(
                FactArticle,
                FactArticle.article_id == FactProductArticle.article_id,
            )
            query = self._apply_article_scope(query, request)
        return query.order_by(DimProduct.product_id.asc()).distinct()

    def _exclusive_query(self, db: Session, request: QwenQualityReviewRequest) -> Any:
        query = db.query(FactExclusiveUseRight).filter(FactExclusiveUseRight.merged_into_exclusive_right_id.is_(None))
        if request.date_from or request.date_to or request.crawl_job_id is not None:
            query = query.join(
                FactExclusiveUseRightArticle,
                FactExclusiveUseRightArticle.exclusive_right_id == FactExclusiveUseRight.exclusive_right_id,
            ).join(FactArticle, FactArticle.article_id == FactExclusiveUseRightArticle.article_id)
            query = self._apply_article_scope(query, request)
        return query.order_by(FactExclusiveUseRight.exclusive_right_id.asc()).distinct()

    @staticmethod
    def _apply_article_scope(query: Any, request: QwenQualityReviewRequest) -> Any:
        if request.crawl_job_id is not None:
            query = query.filter(FactArticle.crawl_job_id == request.crawl_job_id)
        if request.date_from:
            query = query.filter(FactArticle.pub_date >= datetime.fromisoformat(request.date_from))
        if request.date_to:
            query = query.filter(FactArticle.pub_date < datetime.fromisoformat(request.date_to) + timedelta(days=1))
        return query

    @staticmethod
    def _exclude_existing_quality_audit(query: Any, *, target_type: str, id_column: Any, task_type: str) -> Any:
        return query.filter(
            ~exists().where(
                (FactQwenReviewAudit.target_type == target_type)
                & (FactQwenReviewAudit.target_id == id_column)
                & (FactQwenReviewAudit.task_type == task_type)
                & (FactQwenReviewAudit.apply_status == "applied")
            )
        )

    def _product_context(self, db: Session, product: DimProduct, request: QwenQualityReviewRequest) -> ProductContext:
        link_query = (
            db.query(FactProductArticle, FactArticle)
            .join(FactArticle, FactArticle.article_id == FactProductArticle.article_id)
            .filter(FactProductArticle.product_id == product.product_id)
            .order_by(FactProductArticle.is_primary_product.desc(), FactArticle.pub_date.desc().nullslast(), FactArticle.article_id.desc())
        )
        link_query = self._apply_article_scope(link_query, request)
        row = link_query.first()
        article = row[1] if row else None
        observation_query = db.query(FactProductObservation).filter(FactProductObservation.product_id == product.product_id)
        if article:
            observation_query = observation_query.filter(FactProductObservation.article_id == article.article_id)
        observation = observation_query.order_by(FactProductObservation.observation_id.desc()).first()
        context_text = observation.observation_context_text if observation else None
        if not context_text and article:
            context_text = "\n".join(part for part in [article.title, article.description] if part)
        aliases = [
            value
            for row in db.query(DimProductAlias)
            .filter(DimProductAlias.product_id == product.product_id)
            .order_by(DimProductAlias.product_alias_id.desc())
            .limit(20)
            .all()
            for value in [row.raw_product_name, row.normalized_product_name_candidate]
            if value
        ]
        article_decision = self.article_filter.classify_article(db, article) if article else None
        return ProductContext(article=article, context_text=context_text, aliases=list(dict.fromkeys(aliases)), article_decision=article_decision)

    def _exclusive_context(self, db: Session, item: FactExclusiveUseRight, request: QwenQualityReviewRequest) -> ExclusiveContext:
        link_query = (
            db.query(FactExclusiveUseRightArticle, FactArticle)
            .join(FactArticle, FactArticle.article_id == FactExclusiveUseRightArticle.article_id)
            .filter(FactExclusiveUseRightArticle.exclusive_right_id == item.exclusive_right_id)
            .order_by(FactArticle.pub_date.desc().nullslast(), FactArticle.article_id.desc())
        )
        link_query = self._apply_article_scope(link_query, request)
        row = link_query.first()
        article = row[1] if row else None
        context_text = "\n".join(part for part in [article.title, article.description, item.evidence_summary, item.evidence_text] if part) if article else item.evidence_text
        article_decision = self.article_filter.classify_article(db, article) if article else None
        return ExclusiveContext(article=article, context_text=context_text, evidence_text=item.evidence_text or item.evidence_summary, article_decision=article_decision)

    @staticmethod
    def _row(target_type: str, target_id: int, decision: Any, before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
        return {
            "target_type": target_type,
            "target_id": target_id,
            "decision": decision.decision,
            "confidence": decision.confidence,
            "provider_called": decision.provider_called,
            "reason": decision.reason,
            "before": json.dumps(before, ensure_ascii=False),
            "after": json.dumps(after, ensure_ascii=False),
        }

    def _write_artifacts(self, summary: dict[str, Any], request: QwenQualityReviewRequest) -> dict[str, str]:
        output_dir = Path(request.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = Path(request.report_path)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        suffix = utcnow().strftime("%Y%m%d_%H%M%S")
        plan_path = output_dir / f"qwen_quality_review_plan_{suffix}.csv"
        rows: list[dict[str, Any]] = []
        for scope in ("products", "exclusive_rights"):
            rows.extend((summary.get(scope) or {}).get("rows") or [])
        fieldnames = ["target_type", "target_id", "decision", "confidence", "provider_called", "reason", "before", "after"]
        with plan_path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        report_path.write_text(self._report_markdown(summary, plan_path), encoding="utf-8")
        return {"plan_csv_path": str(plan_path), "report_path": str(report_path)}

    @staticmethod
    def _report_markdown(summary: dict[str, Any], plan_path: Path) -> str:
        products = summary.get("products") or {}
        exclusive = summary.get("exclusive_rights") or {}
        scope_counts = summary.get("scope_counts") or {}
        return "\n".join(
            [
                "# Full Contextual Qwen Quality Review Result",
                "",
                f"- status: {summary.get('status')}",
                f"- mode: {summary.get('mode')}",
                f"- target: {summary.get('target')}",
                f"- date_from: {summary.get('date_from')}",
                f"- date_to: {summary.get('date_to')}",
                f"- provider: {summary.get('provider')}",
                f"- product_processed: {products.get('processed', 0)}",
                f"- product_provider_called: {products.get('provider_called', 0)}",
                f"- product_accepted: {products.get('accepted', 0)}",
                f"- product_reviewed: {products.get('reviewed', 0)}",
                f"- product_rejected: {products.get('rejected', 0)}",
                f"- exclusive_processed: {exclusive.get('processed', 0)}",
                f"- exclusive_provider_called: {exclusive.get('provider_called', 0)}",
                f"- exclusive_accepted: {exclusive.get('accepted', 0)}",
                f"- exclusive_reviewed: {exclusive.get('reviewed', 0)}",
                f"- exclusive_rejected: {exclusive.get('rejected', 0)}",
                f"- products_in_scope: {scope_counts.get('products', 0)}",
                f"- exclusive_rights_in_scope: {scope_counts.get('exclusive_rights', 0)}",
                "",
                "## Artifacts",
                "",
                f"- plan: `{plan_path}`",
                "",
                "## Summary JSON",
                "",
                "```json",
                json.dumps({k: v for k, v in summary.items() if k not in {'products', 'exclusive_rights'}}, ensure_ascii=False, indent=2),
                "```",
                "",
            ]
        )
