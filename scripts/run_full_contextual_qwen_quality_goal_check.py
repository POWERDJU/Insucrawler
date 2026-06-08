from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import SessionLocal
from app.db.models import DimProduct, FactArticle, FactExclusiveUseRight, FactExclusiveUseRightArticle, FactProductArticle
from app.normalizers.product_name_normalizer import validate_product_name_before_save
from app.services.article_eligibility_filter_service import ArticleEligibilityFilterService
from app.services.exclusive_right_local_context import validate_exclusive_subject_quality
from app.services.qwen_quality_review_service import QwenQualityReviewRequest, QwenQualityReviewService


PRODUCT_NAME_REJECT_EXAMPLES = [1348, 1996]
PRODUCT_ARTICLE_REJECT_EXAMPLES = [1574, 1723, 1996]
EXCLUSIVE_SUBJECT_REJECT_EXAMPLES = [53, 151, 1134, 1294, 1343]
EXCLUSIVE_ARTICLE_REJECT_EXAMPLES = [47]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run non-live goal checks for full contextual Qwen quality review plumbing.")
    parser.add_argument("--date-from", default="2025-01-01")
    parser.add_argument("--date-to", default="2026-05-31")
    parser.add_argument("--report-path", default="docs/full-contextual-qwen-quality-goal-result.md")
    return parser.parse_args()


def _product_article(db, product_id: int) -> FactArticle | None:
    row = (
        db.query(FactArticle)
        .join(FactProductArticle, FactProductArticle.article_id == FactArticle.article_id)
        .filter(FactProductArticle.product_id == product_id)
        .order_by(FactProductArticle.is_primary_product.desc(), FactArticle.pub_date.desc().nullslast())
        .first()
    )
    return row


def _exclusive_article(db, exclusive_right_id: int) -> FactArticle | None:
    row = (
        db.query(FactArticle)
        .join(FactExclusiveUseRightArticle, FactExclusiveUseRightArticle.article_id == FactArticle.article_id)
        .filter(FactExclusiveUseRightArticle.exclusive_right_id == exclusive_right_id)
        .order_by(FactArticle.pub_date.desc().nullslast())
        .first()
    )
    return row


def main() -> int:
    args = parse_args()
    checks: list[dict[str, object]] = []
    failures: list[str] = []
    article_filter = ArticleEligibilityFilterService()
    with SessionLocal() as db:
        for product_id in PRODUCT_NAME_REJECT_EXAMPLES:
            product = db.get(DimProduct, product_id)
            validation = validate_product_name_before_save(product.normalized_product_name if product else None)
            ok = bool(product and not validation.accepted)
            checks.append({"check": "product_name_reject", "id": product_id, "ok": ok, "reason": validation.reason})
            if not ok:
                failures.append(f"product_name_reject:{product_id}")
        for product_id in PRODUCT_ARTICLE_REJECT_EXAMPLES:
            article = _product_article(db, product_id)
            decision = article_filter.classify_article(db, article) if article else None
            ok = bool(decision and not decision.is_eligible)
            checks.append({"check": "product_article_reject", "id": product_id, "ok": ok, "reason": decision.exclusion_reason if decision else None})
            if not ok:
                failures.append(f"product_article_reject:{product_id}")
        for exclusive_right_id in EXCLUSIVE_SUBJECT_REJECT_EXAMPLES:
            item = db.get(FactExclusiveUseRight, exclusive_right_id)
            validation = validate_exclusive_subject_quality(
                item.subject_name if item else None,
                evidence_text=(item.evidence_text or item.evidence_summary) if item else None,
                window_text="\n".join(part for part in [item.evidence_summary, item.evidence_text] if part) if item else None,
            )
            ok = bool(item and (validation.needs_review or validation.status == "resolved") and validation.status in {"rejected", "review", "resolved"})
            checks.append({"check": "exclusive_subject_reject", "id": exclusive_right_id, "ok": ok, "reason": validation.reason})
            if not ok:
                failures.append(f"exclusive_subject_reject:{exclusive_right_id}")
        for exclusive_right_id in EXCLUSIVE_ARTICLE_REJECT_EXAMPLES:
            article = _exclusive_article(db, exclusive_right_id)
            decision = article_filter.classify_article(db, article) if article else None
            ok = bool(decision and not decision.is_eligible)
            checks.append({"check": "exclusive_article_reject", "id": exclusive_right_id, "ok": ok, "reason": decision.exclusion_reason if decision else None})
            if not ok:
                failures.append(f"exclusive_article_reject:{exclusive_right_id}")
        request = QwenQualityReviewRequest(date_from=args.date_from, date_to=args.date_to, require_live_qwen=False)
        counts = QwenQualityReviewService().candidate_counts(db, request=request)
        if counts["products"] <= 0 or counts["exclusive_rights"] <= 0:
            failures.append("quality_review_scope_empty")

    status = "PASS" if not failures else "FAIL"
    payload = {"status": status, "failures": failures, "scope_counts": counts, "checks": checks}
    report = Path(args.report_path)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        "\n".join(["# Full Contextual Qwen Quality Goal Check", "", "```json", json.dumps(payload, ensure_ascii=False, indent=2), "```", ""]),
        encoding="utf-8",
    )
    print(json.dumps({"report_path": str(report), **payload}, ensure_ascii=False, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
