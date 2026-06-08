from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db.models import DimProduct
from app.services.final_adjudication_provider_factory import build_final_adjudication_provider
from app.services.product_final_adjudication_service import ProductFinalAdjudicationService
from scripts.run_qwen_final_adjudication import (
    QWEN_PRODUCT_FINAL_REVIEW_TASK_TYPE,
    add_qwen_audit,
    apply_product_decision,
    current_product_json,
    product_context,
)


BRAND_RULE_TASK_TYPE = "product_company_brand_rule_review"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Qwen final review for product company-brand rule review rows.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--product-ids", default=None, help="Comma-separated product IDs. Defaults to pending brand-rule review rows.")
    parser.add_argument("--limit", type=int, default=None)
    return parser.parse_args()


def _target_ids(db: Session, product_ids_arg: str | None, limit: int | None) -> list[int]:
    if product_ids_arg:
        values = [int(part.strip()) for part in product_ids_arg.split(",") if part.strip()]
        return values[:limit] if limit else values
    rows = (
        db.execute(
            text(
                """
            SELECT target_id
            FROM fact_qwen_review_audit
            WHERE task_type = :task_type
              AND decision = 'mark_review_for_qwen'
              AND apply_status = 'review'
            ORDER BY target_id
            """
            ),
            {"task_type": BRAND_RULE_TASK_TYPE},
        )
        .scalars()
        .all()
    )
    values = [int(value) for value in rows if value is not None]
    return values[:limit] if limit else values


def _run_one(db: Session, service: ProductFinalAdjudicationService, product_id: int, apply: bool) -> dict[str, Any]:
    product = db.get(DimProduct, product_id)
    if not product:
        return {"product_id": product_id, "status": "missing"}
    context = product_context(db, product, crawl_job_id=None)
    before = current_product_json(product)
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
        candidate_type="company_brand_rule_review",
        article=context.article,
        context_text=context.context_text,
        aliases=context.aliases,
    )
    decision = service.adjudicate(db, payload)
    result: dict[str, Any] | str = "dry_run"
    if apply:
        result = apply_product_decision(db, product, decision, context)
        add_qwen_audit(
            db,
            target_type="product",
            target_id=product.product_id,
            task_type=QWEN_PRODUCT_FINAL_REVIEW_TASK_TYPE,
            full_review_job_id=None,
            crawl_job_id=None,
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
    return {
        "product_id": product_id,
        "status": "processed",
        "decision": decision.decision,
        "canonical_product_name": decision.canonical_product_name,
        "company_name": decision.company_name,
        "insurance_type": decision.insurance_type,
        "release_year_month": decision.release_year_month,
        "partner_company_name": decision.partner_company_name,
        "provider_called": decision.provider_called,
        "confidence": decision.confidence,
        "reason": decision.reason,
        "result": result,
    }


def main() -> int:
    args = parse_args()
    os.environ["ENABLE_FINAL_ADJUDICATION_LLM"] = "true"
    os.environ.setdefault("FINAL_ADJUDICATION_PROVIDER", "qwen")
    provider = build_final_adjudication_provider()
    if provider is None:
        print(json.dumps({"status": "disabled", "message": "Qwen provider is not configured"}, ensure_ascii=False))
        return 2

    summary: dict[str, Any] = {"apply": bool(args.apply), "targets": [], "processed": 0, "failed": 0, "results": []}
    with SessionLocal() as db:
        target_ids = _target_ids(db, args.product_ids, args.limit)
        summary["targets"] = target_ids
        service = ProductFinalAdjudicationService(provider=provider, force_provider=True)
        for product_id in target_ids:
            try:
                result = _run_one(db, service, product_id, args.apply)
                summary["processed"] += int(result.get("status") == "processed")
            except Exception as exc:
                db.rollback()
                summary["failed"] += 1
                result = {"product_id": product_id, "status": "failed", "error": str(exc)[:500]}
            summary["results"].append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
