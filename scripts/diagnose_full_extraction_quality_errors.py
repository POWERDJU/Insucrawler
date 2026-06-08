from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import SessionLocal
from app.db.models import DimProduct, FactExclusiveUseRight
from app.normalizers.product_name_normalizer import validate_product_name_before_save
from app.services.exclusive_right_local_context import validate_exclusive_subject_quality
from app.services.qwen_quality_review_service import QwenQualityReviewRequest, QwenQualityReviewService


PRODUCT_EXAMPLE_IDS = [1996, 1574, 1348, 1723]
EXCLUSIVE_EXAMPLE_IDS = [47, 294, 295, 53, 361, 364, 151, 375, 1134, 1124, 1040, 1343, 980, 772, 762, 764, 652, 503, 1410, 1413, 1294, 979, 944, 851, 750, 259, 205, 746]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diagnose known extraction quality error classes without LLM calls.")
    parser.add_argument("--date-from", default="2025-01-01")
    parser.add_argument("--date-to", default="2026-05-31")
    parser.add_argument("--report-path", default="docs/full-extraction-quality-diagnosis.md")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    with SessionLocal() as db:
        request = QwenQualityReviewRequest(date_from=args.date_from, date_to=args.date_to, require_live_qwen=False)
        counts = QwenQualityReviewService().candidate_counts(db, request=request)
        products = []
        for product_id in PRODUCT_EXAMPLE_IDS:
            product = db.get(DimProduct, product_id)
            if not product:
                products.append({"product_id": product_id, "found": False})
                continue
            validation = validate_product_name_before_save(product.normalized_product_name)
            products.append(
                {
                    "product_id": product_id,
                    "found": True,
                    "name": product.normalized_product_name,
                    "status": product.product_status,
                    "needs_review": product.needs_review,
                    "validator_accepted": validation.accepted,
                    "validator_reason": validation.reason,
                }
            )
        exclusive_rights = []
        for exclusive_right_id in EXCLUSIVE_EXAMPLE_IDS:
            item = db.get(FactExclusiveUseRight, exclusive_right_id)
            if not item:
                exclusive_rights.append({"exclusive_right_id": exclusive_right_id, "found": False})
                continue
            validation = validate_exclusive_subject_quality(
                item.subject_name,
                evidence_text=item.evidence_text or item.evidence_summary,
                window_text="\n".join(part for part in [item.evidence_summary, item.evidence_text] if part),
            )
            exclusive_rights.append(
                {
                    "exclusive_right_id": exclusive_right_id,
                    "found": True,
                    "subject_name": item.subject_name,
                    "event_status": item.event_status,
                    "needs_review": item.needs_review,
                    "validator_status": validation.status,
                    "validator_reason": validation.reason,
                }
            )

    payload = {"scope_counts": counts, "product_examples": products, "exclusive_right_examples": exclusive_rights}
    report = Path(args.report_path)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        "\n".join(
            [
                "# Full Extraction Quality Diagnosis",
                "",
                "```json",
                json.dumps(payload, ensure_ascii=False, indent=2),
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps({"status": "completed", "report_path": str(report), **payload}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
