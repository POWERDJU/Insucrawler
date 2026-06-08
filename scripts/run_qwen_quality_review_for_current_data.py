from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import SessionLocal
from app.services.qwen_quality_review_service import QwenQualityReviewRequest, QwenQualityReviewService


def _optional_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    parsed = int(value)
    return None if parsed < 0 else parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run exhaustive compact-context Qwen quality review over current DB data.")
    parser.add_argument("--apply", action="store_true", help="Apply accepted/rejected/review decisions to DB.")
    parser.add_argument("--target", choices=["all", "products", "exclusive_rights", "exclusive"], default="all")
    parser.add_argument("--date-from", default="2025-01-01")
    parser.add_argument("--date-to", default="2026-05-31")
    parser.add_argument("--crawl-job-id", type=int, default=None)
    parser.add_argument("--limit-products", type=_optional_int, default=None, help="Max product rows to process; omit for unlimited.")
    parser.add_argument("--limit-exclusive", type=_optional_int, default=None, help="Max exclusive-right rows to process; omit for unlimited.")
    parser.add_argument("--max-scan-products", type=_optional_int, default=None)
    parser.add_argument("--max-scan-exclusive", type=_optional_int, default=None)
    parser.add_argument("--skip-existing-quality-audit", action="store_true")
    parser.add_argument("--no-require-live-qwen", action="store_true", help="Allow deterministic fallback if Qwen is disabled.")
    parser.add_argument("--output-dir", default="data/exports")
    parser.add_argument("--report-path", default="docs/full-contextual-qwen-quality-goal-result.md")
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args()
    request = QwenQualityReviewRequest(
        mode="apply" if args.apply else "dry_run",
        target=args.target,
        date_from=args.date_from,
        date_to=args.date_to,
        crawl_job_id=args.crawl_job_id,
        limit_products=args.limit_products,
        limit_exclusive=args.limit_exclusive,
        max_scan_products=args.max_scan_products,
        max_scan_exclusive=args.max_scan_exclusive,
        skip_existing_quality_audit=args.skip_existing_quality_audit,
        require_live_qwen=not args.no_require_live_qwen,
        output_dir=args.output_dir,
        report_path=args.report_path,
    )
    with SessionLocal() as db:
        summary = QwenQualityReviewService().run(db, request)
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    return 0 if summary.get("status") == "completed" else 2


if __name__ == "__main__":
    sys.exit(main())
