from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import exists, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db.models import (
    DimCompany,
    DimProduct,
    DimProductAlias,
    FactArticle,
    FactExclusiveUseRight,
    FactExclusiveUseRightArticle,
    FactProductArticle,
    FactProductObservation,
    FactQwenReviewAudit,
)
from app.db.repository import company_aliases_for_company
from app.normalizers.product_name_normalizer import (
    build_product_identity_key,
    normalize_product_name,
    normalize_product_name_core,
    product_search_key,
)
from app.services.article_eligibility_filter_service import ArticleEligibilityDecision, ArticleEligibilityFilterService
from app.services.company_attribution_service import CompanyAttributionService
from app.services.exclusive_right_final_adjudication_service import ExclusiveRightFinalAdjudicationService
from app.services.exclusive_right_local_context import (
    is_valid_year_month as is_valid_exclusive_year_month,
    validate_exclusive_subject_before_save,
)
from app.services.final_adjudication_provider_factory import build_final_adjudication_provider, final_adjudication_llm_enabled
from app.services.product_company_eligibility import is_product_news_eligible_company
from app.services.product_final_adjudication_service import ProductFinalAdjudicationDecision, ProductFinalAdjudicationService
from app.services.release_month_resolver import is_valid_year_month as is_valid_release_year_month
from app.utils.text import compact_spaces, normalize_search_key


WEAK_RELEASE_BASES = {None, "", "unknown", "first_seen_only", "earliest_related_article_month"}
PRODUCT_EXCLUDED_STATUSES = {
    "merged",
    "rejected",
    "rejected_multi_company_only",
    "rejected_ineligible_article_only",
    "rejected_marketing_only",
    "excluded_invalid_industry_product_type",
}
EXCLUSIVE_EXCLUDED_STATUSES = {"merged", "rejected", "rejected_multi_company_only"}
QWEN_FINAL_REVIEWED_STATUS = "qwen_final_reviewed"
QWEN_PRODUCT_FINAL_REVIEW_TASK_TYPE = "qwen_product_final_review"
QWEN_EXCLUSIVE_RIGHT_FINAL_REVIEW_TASK_TYPE = "qwen_exclusive_right_final_review"


@dataclass(frozen=True)
class ProductContext:
    article: FactArticle | None
    context_text: str | None
    aliases: list[str]
    article_decision: ArticleEligibilityDecision | None


@dataclass(frozen=True)
class ExclusiveContext:
    article: FactArticle | None
    context_text: str | None
    evidence_text: str | None
    article_decision: ArticleEligibilityDecision | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run opt-in Qwen final adjudication over surviving DB candidates.")
    parser.add_argument("--apply", action="store_true", help="Apply accepted corrections and review flags.")
    parser.add_argument("--crawl-job-id", type=int, default=None)
    parser.add_argument("--limit-products", type=int, default=100)
    parser.add_argument("--limit-exclusive", type=int, default=50)
    parser.add_argument("--max-scan-products", type=int, default=2500)
    parser.add_argument("--max-scan-exclusive", type=int, default=1500)
    parser.add_argument("--products-only", action="store_true")
    parser.add_argument("--exclusive-only", action="store_true")
    parser.add_argument("--date-from", default=None)
    parser.add_argument("--date-to", default=None)
    parser.add_argument("--exhaustive", action="store_true", help="Review every in-scope active row, not only risky candidates.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not final_adjudication_llm_enabled():
        print(json.dumps({"status": "disabled", "message": "ENABLE_FINAL_ADJUDICATION_LLM is not true"}, ensure_ascii=False))
        return 2
    provider = build_final_adjudication_provider()
    if provider is None:
        print(json.dumps({"status": "disabled", "message": "final adjudication provider is not configured"}, ensure_ascii=False))
        return 2

    summary: dict[str, Any] = {
        "apply": bool(args.apply),
        "crawl_job_id": args.crawl_job_id,
        "products": {},
        "exclusive_rights": {},
    }
    with SessionLocal() as db:
        if not args.exclusive_only:
            summary["products"] = run_product_adjudication(
                db,
                provider=provider,
                apply=args.apply,
                crawl_job_id=args.crawl_job_id,
                date_from=args.date_from,
                date_to=args.date_to,
                exhaustive=args.exhaustive,
                limit=args.limit_products,
                max_scan=args.max_scan_products,
            )
        if not args.products_only:
            summary["exclusive_rights"] = run_exclusive_adjudication(
                db,
                provider=provider,
                apply=args.apply,
                crawl_job_id=args.crawl_job_id,
                date_from=args.date_from,
                date_to=args.date_to,
                exhaustive=args.exhaustive,
                limit=args.limit_exclusive,
                max_scan=args.max_scan_exclusive,
            )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def run_product_adjudication(
    db: Session,
    *,
    provider: Any,
    apply: bool,
    crawl_job_id: int | None,
    full_review_job_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    exhaustive: bool = False,
    limit: int = 100,
    max_scan: int = 2500,
) -> dict[str, Any]:
    service = ProductFinalAdjudicationService(provider=provider)
    filters = [
        DimProduct.merged_into_product_id.is_(None),
        DimProduct.product_status.notin_(list(PRODUCT_EXCLUDED_STATUSES)),
        or_(DimProduct.consolidation_status.is_(None), DimProduct.consolidation_status != QWEN_FINAL_REVIEWED_STATUS),
    ]
    if not exhaustive:
        filters.append(
            or_(
                DimProduct.needs_review.is_(True),
                DimProduct.product_status.in_(["review", "provisional"]),
                DimProduct.release_year_month.is_(None),
                DimProduct.release_year_month_basis.in_(list(WEAK_RELEASE_BASES - {None})),
                DimProduct.partner_company_name.isnot(None),
                DimProduct.company_id.is_(None),
            ),
        )
    query = db.query(DimProduct).filter(*filters)
    query = scope_product_query(db, query, crawl_job_id=crawl_job_id, date_from=date_from, date_to=date_to)
    if exhaustive:
        query = exclude_existing_qwen_audit(query, target_type="product", id_column=DimProduct.product_id)
    query = query.order_by(DimProduct.needs_review.desc(), DimProduct.product_id.desc()).limit(max_scan)
    scanned = 0
    processed = 0
    provider_called = 0
    accepted = reviewed = rejected = skipped_not_risky = discarded_by_rule = failed = 0
    errors: list[dict[str, Any]] = []
    for product in query.all():
        if processed >= limit:
            break
        scanned += 1
        context = product_context(db, product, crawl_job_id=crawl_job_id, date_from=date_from, date_to=date_to)
        if context.article_decision and not context.article_decision.is_eligible:
            discarded_by_rule += 1
            if apply:
                product.needs_review = True
                product.product_status = "rejected_ineligible_article_only"
                product.consolidation_status = "rejected_ineligible_article_only"
                add_qwen_audit(
                    db,
                    target_type="product",
                    target_id=product.product_id,
                    task_type=QWEN_PRODUCT_FINAL_REVIEW_TASK_TYPE,
                    full_review_job_id=full_review_job_id,
                    crawl_job_id=crawl_job_id,
                    article_id=context.article.article_id if context.article else None,
                    decision="ineligible_article",
                    confidence=context.article_decision.confidence,
                    reason=context.article_decision.exclusion_reason or "article_ineligible",
                    provider_called=False,
                    apply_status="applied",
                    before_json=current_product_json(product),
                    after_json=current_product_json(product),
                )
                db.commit()
            continue
        if not context.article and crawl_job_id is not None:
            continue
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
        name_decision = service.name_validator.validate(
            payload.current_product_name,
            article_title=str(payload.representative_article.get("title") or ""),
            evidence_text=context.context_text,
            context_text=context.context_text,
        )
        if not exhaustive and not service.requires_llm_adjudication(payload, name_reason=name_decision.reason, removed_prefixes=name_decision.removed_prefixes):
            skipped_not_risky += 1
            if apply:
                product.consolidation_status = QWEN_FINAL_REVIEWED_STATUS
                db.commit()
            continue
        try:
            before = current_product_json(product)
            decision = service.adjudicate(db, payload)
            processed += 1
            provider_called += int(decision.provider_called)
            if apply:
                result = apply_product_decision(db, product, decision, context)
                add_qwen_audit(
                    db,
                    target_type="product",
                    target_id=product.product_id,
                    task_type=QWEN_PRODUCT_FINAL_REVIEW_TASK_TYPE,
                    full_review_job_id=full_review_job_id,
                    crawl_job_id=crawl_job_id,
                    article_id=context.article.article_id if context.article else None,
                    decision=decision.decision,
                    confidence=decision.confidence,
                    reason=decision.reason,
                    evidence_text=decision.evidence_quote,
                    provider_called=decision.provider_called,
                    apply_status="applied",
                    before_json=before,
                    after_json=current_product_json(product),
                )
                db.commit()
            else:
                result = decision.decision
            if decision.decision == "accept":
                accepted += 1
            elif decision.decision in {"reject", "non_insurance", "ineligible_article"}:
                rejected += 1
            else:
                reviewed += 1
            errors.extend(result.get("errors", []) if isinstance(result, dict) else [])
        except Exception as exc:
            db.rollback()
            failed += 1
            errors.append({"product_id": product.product_id, "error": str(exc)[:300]})
            if apply:
                product = db.get(DimProduct, product.product_id)
                if product:
                    product.needs_review = True
                    product.product_status = "review"
                    product.consolidation_status = QWEN_FINAL_REVIEWED_STATUS
                    add_qwen_audit(
                        db,
                        target_type="product",
                        target_id=product.product_id,
                        task_type=QWEN_PRODUCT_FINAL_REVIEW_TASK_TYPE,
                        full_review_job_id=full_review_job_id,
                        crawl_job_id=crawl_job_id,
                        article_id=context.article.article_id if context.article else None,
                        decision="review",
                        confidence=0.0,
                        reason=f"provider_error:{str(exc)[:300]}",
                        provider_called=True,
                        apply_status="applied",
                        before_json=before,
                        after_json=current_product_json(product),
                    )
                    db.commit()
            continue
    return {
        "scanned": scanned,
        "processed": processed,
        "provider_called": provider_called,
        "accepted": accepted,
        "reviewed": reviewed,
        "rejected": rejected,
        "discarded_by_rule": discarded_by_rule,
        "skipped_not_risky": skipped_not_risky,
        "failed": failed,
        "remaining_estimate": max(
            0,
            candidate_product_count(db, crawl_job_id=crawl_job_id, date_from=date_from, date_to=date_to, exhaustive=exhaustive) - processed,
        ),
        "errors": errors[:10],
    }


def run_exclusive_adjudication(
    db: Session,
    *,
    provider: Any,
    apply: bool,
    crawl_job_id: int | None,
    full_review_job_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    exhaustive: bool = False,
    limit: int = 50,
    max_scan: int = 1500,
) -> dict[str, Any]:
    service = ExclusiveRightFinalAdjudicationService(provider=provider)
    filters = [
        FactExclusiveUseRight.merged_into_exclusive_right_id.is_(None),
        FactExclusiveUseRight.event_status.notin_(list(EXCLUSIVE_EXCLUDED_STATUSES | {QWEN_FINAL_REVIEWED_STATUS})),
    ]
    if not exhaustive:
        filters.append(
            or_(
                FactExclusiveUseRight.needs_review.is_(True),
                FactExclusiveUseRight.event_status == "review",
                FactExclusiveUseRight.company_id.is_(None),
                FactExclusiveUseRight.acquired_year_month.is_(None),
            ),
        )
    query = db.query(FactExclusiveUseRight).filter(*filters)
    query = scope_exclusive_query(db, query, crawl_job_id=crawl_job_id, date_from=date_from, date_to=date_to)
    if exhaustive:
        query = exclude_existing_qwen_audit(
            query,
            target_type="exclusive_right",
            id_column=FactExclusiveUseRight.exclusive_right_id,
        )
    query = query.order_by(FactExclusiveUseRight.needs_review.desc(), FactExclusiveUseRight.exclusive_right_id.desc()).limit(max_scan)
    scanned = processed = provider_called = accepted = reviewed = rejected = skipped_not_risky = discarded_by_rule = failed = 0
    errors: list[dict[str, Any]] = []
    for item in query.all():
        if processed >= limit:
            break
        scanned += 1
        context = exclusive_context(db, item, crawl_job_id=crawl_job_id, date_from=date_from, date_to=date_to)
        if context.article_decision and not context.article_decision.is_eligible:
            discarded_by_rule += 1
            if apply:
                item.needs_review = True
                item.event_status = "rejected"
                add_qwen_audit(
                    db,
                    target_type="exclusive_right",
                    target_id=item.exclusive_right_id,
                    task_type=QWEN_EXCLUSIVE_RIGHT_FINAL_REVIEW_TASK_TYPE,
                    full_review_job_id=full_review_job_id,
                    crawl_job_id=crawl_job_id,
                    article_id=context.article.article_id if context.article else None,
                    decision="ineligible_article",
                    confidence=context.article_decision.confidence,
                    reason=context.article_decision.exclusion_reason or "article_ineligible",
                    provider_called=False,
                    apply_status="applied",
                    before_json=current_exclusive_json(item),
                    after_json=current_exclusive_json(item),
                )
                db.commit()
            continue
        if not context.article and crawl_job_id is not None:
            continue
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
        if not exhaustive and not exclusive_needs_qwen(db, service, payload, item):
            skipped_not_risky += 1
            if apply:
                item.event_status = QWEN_FINAL_REVIEWED_STATUS
                db.commit()
            continue
        try:
            before = current_exclusive_json(item)
            decision = service.adjudicate(db, payload)
            processed += 1
            provider_called += int(decision.provider_called)
            if apply:
                apply_exclusive_decision(db, item, decision, context)
                add_qwen_audit(
                    db,
                    target_type="exclusive_right",
                    target_id=item.exclusive_right_id,
                    task_type=QWEN_EXCLUSIVE_RIGHT_FINAL_REVIEW_TASK_TYPE,
                    full_review_job_id=full_review_job_id,
                    crawl_job_id=crawl_job_id,
                    article_id=context.article.article_id if context.article else None,
                    decision=decision.decision,
                    confidence=decision.confidence,
                    reason=decision.reason,
                    evidence_text=decision.evidence_quote,
                    provider_called=decision.provider_called,
                    apply_status="applied",
                    before_json=before,
                    after_json=current_exclusive_json(item),
                )
                db.commit()
            if decision.decision == "accept":
                accepted += 1
            elif decision.decision in {"reject", "ineligible_article"}:
                rejected += 1
            else:
                reviewed += 1
        except Exception as exc:
            db.rollback()
            failed += 1
            errors.append({"exclusive_right_id": item.exclusive_right_id, "error": str(exc)[:300]})
            if apply:
                item = db.get(FactExclusiveUseRight, item.exclusive_right_id)
                if item:
                    item.needs_review = True
                    item.event_status = QWEN_FINAL_REVIEWED_STATUS
                    add_qwen_audit(
                        db,
                        target_type="exclusive_right",
                        target_id=item.exclusive_right_id,
                        task_type=QWEN_EXCLUSIVE_RIGHT_FINAL_REVIEW_TASK_TYPE,
                        full_review_job_id=full_review_job_id,
                        crawl_job_id=crawl_job_id,
                        article_id=context.article.article_id if context.article else None,
                        decision="review",
                        confidence=0.0,
                        reason=f"provider_error:{str(exc)[:300]}",
                        provider_called=True,
                        apply_status="applied",
                        before_json=before,
                        after_json=current_exclusive_json(item),
                    )
                    db.commit()
            continue
    return {
        "scanned": scanned,
        "processed": processed,
        "provider_called": provider_called,
        "accepted": accepted,
        "reviewed": reviewed,
        "rejected": rejected,
        "discarded_by_rule": discarded_by_rule,
        "skipped_not_risky": skipped_not_risky,
        "failed": failed,
        "remaining_estimate": max(
            0,
            candidate_exclusive_count(db, crawl_job_id=crawl_job_id, date_from=date_from, date_to=date_to, exhaustive=exhaustive) - processed,
        ),
        "errors": errors[:10],
    }


def product_context(
    db: Session,
    product: DimProduct,
    *,
    crawl_job_id: int | None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> ProductContext:
    link_query = (
        db.query(FactProductArticle, FactArticle)
        .join(FactArticle, FactArticle.article_id == FactProductArticle.article_id)
        .filter(
            FactProductArticle.product_id == product.product_id,
            FactArticle.multi_company_article_yn.is_(False),
            or_(FactArticle.extraction_exclusion_reason.is_(None), FactArticle.extraction_exclusion_reason == ""),
        )
        .order_by(FactProductArticle.is_primary_product.desc(), FactArticle.pub_date.desc().nullslast(), FactArticle.article_id.desc())
    )
    if crawl_job_id is not None:
        link_query = link_query.filter(FactArticle.crawl_job_id == crawl_job_id)
    link_query = apply_article_date_filters(link_query, date_from=date_from, date_to=date_to)
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
    article_decision = ArticleEligibilityFilterService().classify_article(db, article) if article else None
    return ProductContext(article=article, context_text=context_text, aliases=list(dict.fromkeys(aliases)), article_decision=article_decision)


def exclusive_context(
    db: Session,
    item: FactExclusiveUseRight,
    *,
    crawl_job_id: int | None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> ExclusiveContext:
    link_query = (
        db.query(FactExclusiveUseRightArticle, FactArticle)
        .join(FactArticle, FactArticle.article_id == FactExclusiveUseRightArticle.article_id)
        .filter(
            FactExclusiveUseRightArticle.exclusive_right_id == item.exclusive_right_id,
            FactArticle.multi_company_article_yn.is_(False),
            or_(FactArticle.extraction_exclusion_reason.is_(None), FactArticle.extraction_exclusion_reason == ""),
        )
        .order_by(FactArticle.pub_date.desc().nullslast(), FactArticle.article_id.desc())
    )
    if crawl_job_id is not None:
        link_query = link_query.filter(FactArticle.crawl_job_id == crawl_job_id)
    link_query = apply_article_date_filters(link_query, date_from=date_from, date_to=date_to)
    row = link_query.first()
    article = row[1] if row else None
    context_text = "\n".join(part for part in [article.title, article.description, item.evidence_summary, item.evidence_text] if part) if article else item.evidence_text
    article_decision = ArticleEligibilityFilterService().classify_article(db, article) if article else None
    return ExclusiveContext(article=article, context_text=context_text, evidence_text=item.evidence_text or item.evidence_summary, article_decision=article_decision)


def apply_product_decision(
    db: Session,
    product: DimProduct,
    decision: ProductFinalAdjudicationDecision,
    context: ProductContext,
) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    if decision.decision != "accept":
        product.needs_review = True
        if decision.decision in {"reject", "non_insurance", "ineligible_article"}:
            product.product_status = "rejected"
        else:
            product.product_status = "review"
            product.consolidation_status = QWEN_FINAL_REVIEWED_STATUS
        return {"status": "review", "errors": errors}

    company = db.get(DimCompany, product.company_id) if product.company_id else None
    if decision.company_name:
        attribution = CompanyAttributionService().resolve_company_for_context(
            db,
            raw_company_name=decision.company_name,
            local_text=context.context_text,
            article_title=context.article.title if context.article else None,
            article_description=context.article.description if context.article else None,
            product_or_subject_name=decision.canonical_product_name or product.normalized_product_name,
        )
        if attribution.company_id:
            company = db.get(DimCompany, attribution.company_id)
            product.company_id = attribution.company_id
            product.company_name_raw = attribution.company_name_normalized or decision.company_name
            product.insurance_type = attribution.insurance_type or product.insurance_type
        else:
            product.needs_review = True
            product.product_status = "review"
            errors.append({"product_id": product.product_id, "error": "qwen_company_not_resolved"})

    company_aliases = company_aliases_for_company(company)
    if decision.canonical_product_name:
        normalized_name = normalize_product_name(decision.canonical_product_name, company_aliases)
        company_name_for_key = company.company_name_normalized if company else None
        search_key = product_search_key(normalized_name, company_name_for_key)
        conflict = (
            db.query(DimProduct)
            .filter(
                DimProduct.product_id != product.product_id,
                DimProduct.company_id == product.company_id,
                DimProduct.product_search_key == search_key,
            )
            .first()
        )
        if conflict:
            product.needs_review = True
            product.product_status = "review"
            product.consolidation_status = QWEN_FINAL_REVIEWED_STATUS
            errors.append({"product_id": product.product_id, "error": f"qwen_name_conflicts_with_product:{conflict.product_id}"})
        else:
            product.normalized_product_name = normalized_name
            product.product_search_key = search_key
            product.product_core_key = normalize_product_name_core(normalized_name, company_aliases)
            product.product_identity_key = build_product_identity_key(product.company_id, normalized_name, company_aliases)

    if decision.release_year_month:
        if is_valid_release_year_month(decision.release_year_month):
            product.release_year_month = decision.release_year_month
            product.release_year_month_basis = decision.release_year_month_basis or "qwen_final_adjudication"
            if context.article:
                product.release_year_month_source_article_id = context.article.article_id
                product.release_year_month_source_type = "qwen_final_adjudication"
        else:
            product.needs_review = True
            product.product_status = "review"
            errors.append({"product_id": product.product_id, "error": "qwen_invalid_release_year_month"})
    if decision.product_type_code and decision.product_type_code != "UNKNOWN":
        product.primary_product_type_code = decision.product_type_code
    if decision.partner_company_name is not None:
        product.partner_company_name = compact_spaces(decision.partner_company_name) or None
    if decision.correction_summary:
        product.partner_context_summary = compact_spaces(decision.correction_summary)[:2000]
    if not errors:
        product.needs_review = False
        product.product_status = "active"
    product.consolidation_status = QWEN_FINAL_REVIEWED_STATUS
    db.flush()
    return {"status": "accepted", "errors": errors}


def apply_exclusive_decision(
    db: Session,
    item: FactExclusiveUseRight,
    decision: Any,
    context: ExclusiveContext,
) -> None:
    if decision.decision != "accept":
        item.needs_review = True
        item.event_status = "rejected" if decision.decision in {"reject", "ineligible_article"} else QWEN_FINAL_REVIEWED_STATUS
        db.flush()
        return
    if decision.subject_name:
        item.subject_name = compact_spaces(decision.subject_name)
        item.subject_core_key = normalize_search_key(item.subject_name)
    if decision.company_name:
        attribution = CompanyAttributionService().resolve_company_for_context(
            db,
            raw_company_name=decision.company_name,
            local_text=context.context_text,
            article_title=context.article.title if context.article else None,
            article_description=context.article.description if context.article else None,
            product_or_subject_name=item.subject_name,
        )
        company = db.get(DimCompany, attribution.company_id) if attribution.company_id else None
        if company and is_product_news_eligible_company(company):
            item.company_id = company.company_id
            item.company_name_normalized = company.company_name_normalized
            item.insurance_type = company.insurance_type_default or company.insurance_type or item.insurance_type
        else:
            item.needs_review = True
            item.event_status = "review"
            db.flush()
            return
    if decision.acquired_year_month:
        if is_valid_exclusive_year_month(decision.acquired_year_month):
            item.acquired_year_month = decision.acquired_year_month
        else:
            item.needs_review = True
            item.event_status = "review"
            db.flush()
            return
    item.needs_review = False
    item.event_status = "active"
    db.flush()


def exclusive_needs_qwen(
    db: Session,
    service: ExclusiveRightFinalAdjudicationService,
    payload: Any,
    item: FactExclusiveUseRight,
) -> bool:
    article_decision = payload.article_eligibility_decision
    if article_decision and (
        article_decision.detected_non_insurance_financial_institutions
        or len(article_decision.detected_insurer_companies or []) > 1
    ):
        return True
    if bool(item.needs_review) or item.event_status == "review" or not item.company_id:
        return True
    if not is_valid_exclusive_year_month(item.acquired_year_month):
        return True
    if item.company_id:
        company = db.get(DimCompany, item.company_id)
        if not is_product_news_eligible_company(company):
            return True
    subject_validation = validate_exclusive_subject_before_save(
        payload.current_subject_name,
        evidence_text=payload.evidence_text,
        window_text=payload.representative_article.get("local_exclusive_windows", [""])[0] if payload.representative_article else None,
        article_title=str(payload.representative_article.get("title") or "") if payload.representative_article else None,
    )
    if subject_validation.needs_review or not subject_validation.subject_name:
        return True
    return service._future_month(payload.acquired_year_month, payload.representative_article)


def _date_start(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.combine(date.fromisoformat(value), time.min)


def _date_end_exclusive(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.combine(date.fromisoformat(value), time.min) + timedelta(days=1)


def apply_article_date_filters(query: Any, *, date_from: str | None, date_to: str | None) -> Any:
    start = _date_start(date_from)
    end = _date_end_exclusive(date_to)
    if start is not None:
        query = query.filter(FactArticle.pub_date >= start)
    if end is not None:
        query = query.filter(FactArticle.pub_date < end)
    return query


def scope_product_query(
    db: Session,
    query: Any,
    *,
    crawl_job_id: int | None,
    date_from: str | None,
    date_to: str | None,
) -> Any:
    if crawl_job_id is None and not date_from and not date_to:
        return query
    query = query.join(FactProductArticle, FactProductArticle.product_id == DimProduct.product_id).join(
        FactArticle,
        FactArticle.article_id == FactProductArticle.article_id,
    )
    query = query.filter(
        FactArticle.multi_company_article_yn.is_(False),
        or_(FactArticle.extraction_exclusion_reason.is_(None), FactArticle.extraction_exclusion_reason == ""),
    )
    if crawl_job_id is not None:
        query = query.filter(FactArticle.crawl_job_id == crawl_job_id)
    return apply_article_date_filters(query, date_from=date_from, date_to=date_to).distinct()


def scope_exclusive_query(
    db: Session,
    query: Any,
    *,
    crawl_job_id: int | None,
    date_from: str | None,
    date_to: str | None,
) -> Any:
    if crawl_job_id is None and not date_from and not date_to:
        return query
    query = query.join(
        FactExclusiveUseRightArticle,
        FactExclusiveUseRightArticle.exclusive_right_id == FactExclusiveUseRight.exclusive_right_id,
    ).join(FactArticle, FactArticle.article_id == FactExclusiveUseRightArticle.article_id)
    query = query.filter(
        FactArticle.multi_company_article_yn.is_(False),
        or_(FactArticle.extraction_exclusion_reason.is_(None), FactArticle.extraction_exclusion_reason == ""),
    )
    if crawl_job_id is not None:
        query = query.filter(FactArticle.crawl_job_id == crawl_job_id)
    return apply_article_date_filters(query, date_from=date_from, date_to=date_to).distinct()


def exclude_existing_qwen_audit(query: Any, *, target_type: str, id_column: Any) -> Any:
    return query.filter(
        ~exists().where(
            (FactQwenReviewAudit.target_type == target_type)
            & (FactQwenReviewAudit.target_id == id_column)
            & (
                FactQwenReviewAudit.task_type.in_(
                    [
                        QWEN_PRODUCT_FINAL_REVIEW_TASK_TYPE,
                        QWEN_EXCLUSIVE_RIGHT_FINAL_REVIEW_TASK_TYPE,
                    ]
                )
            )
            & (FactQwenReviewAudit.apply_status == "applied")
        )
    )


def current_product_json(product: DimProduct) -> dict[str, Any]:
    return {
        "product_id": product.product_id,
        "normalized_product_name": product.normalized_product_name,
        "company_id": product.company_id,
        "company_name_raw": product.company_name_raw,
        "insurance_type": product.insurance_type,
        "release_year_month": product.release_year_month,
        "release_year_month_basis": product.release_year_month_basis,
        "primary_product_type_code": product.primary_product_type_code,
        "partner_company_name": product.partner_company_name,
        "needs_review": product.needs_review,
        "product_status": product.product_status,
        "consolidation_status": product.consolidation_status,
    }


def current_exclusive_json(item: FactExclusiveUseRight) -> dict[str, Any]:
    return {
        "exclusive_right_id": item.exclusive_right_id,
        "subject_name": item.subject_name,
        "company_id": item.company_id,
        "company_name_normalized": item.company_name_normalized,
        "insurance_type": item.insurance_type,
        "acquired_year_month": item.acquired_year_month,
        "exclusivity_months": item.exclusivity_months,
        "needs_review": item.needs_review,
        "event_status": item.event_status,
    }


def add_qwen_audit(
    db: Session,
    *,
    target_type: str,
    target_id: int,
    task_type: str,
    full_review_job_id: int | None,
    crawl_job_id: int | None,
    article_id: int | None,
    decision: str,
    confidence: float | None = None,
    reason: str | None = None,
    evidence_text: str | None = None,
    provider_called: bool = False,
    apply_status: str,
    before_json: dict[str, Any] | None = None,
    after_json: dict[str, Any] | None = None,
) -> None:
    db.add(
        FactQwenReviewAudit(
            full_review_job_id=full_review_job_id,
            target_type=target_type,
            target_id=target_id,
            crawl_job_id=crawl_job_id,
            article_id=article_id,
            task_type=task_type,
            provider="qwen" if provider_called else "rule",
            decision=decision,
            confidence=float(confidence or 0.0),
            reason=reason,
            evidence_text=evidence_text,
            before_json=json.dumps(before_json or {}, ensure_ascii=False),
            after_json=json.dumps(after_json or {}, ensure_ascii=False),
            hard_gate_status="passed" if decision == "accept" else "not_applicable",
            apply_status=apply_status,
        )
    )
    db.flush()


def candidate_product_count(
    db: Session,
    *,
    crawl_job_id: int | None,
    date_from: str | None = None,
    date_to: str | None = None,
    exhaustive: bool = False,
) -> int:
    filters = [
        DimProduct.merged_into_product_id.is_(None),
        DimProduct.product_status.notin_(list(PRODUCT_EXCLUDED_STATUSES)),
        or_(DimProduct.consolidation_status.is_(None), DimProduct.consolidation_status != QWEN_FINAL_REVIEWED_STATUS),
    ]
    if not exhaustive:
        filters.append(
            or_(
            DimProduct.needs_review.is_(True),
            DimProduct.product_status.in_(["review", "provisional"]),
            DimProduct.release_year_month.is_(None),
            DimProduct.release_year_month_basis.in_(list(WEAK_RELEASE_BASES - {None})),
            DimProduct.partner_company_name.isnot(None),
            DimProduct.company_id.is_(None),
            )
        )
    query = db.query(DimProduct).filter(*filters)
    query = scope_product_query(db, query, crawl_job_id=crawl_job_id, date_from=date_from, date_to=date_to)
    if exhaustive:
        query = exclude_existing_qwen_audit(query, target_type="product", id_column=DimProduct.product_id)
    return query.distinct().count()


def candidate_exclusive_count(
    db: Session,
    *,
    crawl_job_id: int | None,
    date_from: str | None = None,
    date_to: str | None = None,
    exhaustive: bool = False,
) -> int:
    filters = [
        FactExclusiveUseRight.merged_into_exclusive_right_id.is_(None),
        FactExclusiveUseRight.event_status.notin_(list(EXCLUSIVE_EXCLUDED_STATUSES | {QWEN_FINAL_REVIEWED_STATUS})),
    ]
    if not exhaustive:
        filters.append(
            or_(
            FactExclusiveUseRight.needs_review.is_(True),
            FactExclusiveUseRight.event_status == "review",
            FactExclusiveUseRight.company_id.is_(None),
            FactExclusiveUseRight.acquired_year_month.is_(None),
            )
        )
    query = db.query(FactExclusiveUseRight).filter(*filters)
    query = scope_exclusive_query(db, query, crawl_job_id=crawl_job_id, date_from=date_from, date_to=date_to)
    if exhaustive:
        query = exclude_existing_qwen_audit(
            query,
            target_type="exclusive_right",
            id_column=FactExclusiveUseRight.exclusive_right_id,
        )
    return query.distinct().count()


if __name__ == "__main__":
    sys.exit(main())
