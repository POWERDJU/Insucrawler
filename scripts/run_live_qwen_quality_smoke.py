from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import SessionLocal
from app.services.qwen_quality_review_service import QwenQualityReviewRequest, QwenQualityReviewService


def main() -> int:
    request = QwenQualityReviewRequest(
        mode="dry_run",
        target="all",
        limit_products=1,
        limit_exclusive=1,
        max_scan_products=5,
        max_scan_exclusive=5,
        require_live_qwen=True,
        report_path="docs/full-contextual-qwen-quality-smoke.md",
    )
    with SessionLocal() as db:
        summary = QwenQualityReviewService().run(db, request)
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    return 0 if summary.get("status") == "completed" else 2


if __name__ == "__main__":
    sys.exit(main())
