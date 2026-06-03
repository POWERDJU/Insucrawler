from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.database import SessionLocal
from app.services.product_full_list_consolidation_service import ProductFullListConsolidationService


REPORT_PATH = ROOT / "docs" / "product-consolidation-live-llm-smoke-result.md"


def _write_report(status: str, lines: list[str]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        "\n".join(["# Product Consolidation Live LLM Smoke Result", "", f"- status: {status}", *lines]) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    enabled = os.getenv("ENABLE_LIVE_LLM_CONSOLIDATION_TEST", "false").lower() in {"1", "true", "yes", "y"}
    has_key = bool(os.getenv("GEMINI_API_KEY"))
    if not enabled or not has_key:
        _write_report(
            "SKIPPED",
            [
                "- reason: live LLM smoke requires ENABLE_LIVE_LLM_CONSOLIDATION_TEST=true and GEMINI_API_KEY.",
                "- db_apply: false",
                "- max_companies: 1",
                "- max_blocks: 1",
            ],
        )
        print(f"SKIPPED: wrote {REPORT_PATH}")
        return 0

    os.environ["PRODUCT_LLM_CONSOLIDATION_ENABLED"] = "true"
    os.environ.setdefault("PRODUCT_LLM_CONSOLIDATION_MAX_COMPANIES_PER_JOB", "1")
    os.environ.setdefault("PRODUCT_LLM_CONSOLIDATION_MAX_CALLS_PER_JOB", "1")
    os.environ.setdefault("PRODUCT_LLM_CONSOLIDATION_MAX_COST_USD_PER_JOB", "1.0")

    with SessionLocal() as db:
        result = ProductFullListConsolidationService().run_full_list_consolidation(
            db,
            mode="dry_run",
            target="all",
            max_companies=1,
            max_blocks=1,
            plan_file=ROOT / "data" / "exports" / "product_live_llm_smoke_plan.csv",
        )
    _write_report(
        "COMPLETED",
        [
            f"- db_apply: false",
            f"- company_group_count: {result.get('company_group_count')}",
            f"- llm_call_count: {result.get('llm_call_count')}",
            f"- auto_apply_count: {result.get('auto_apply_count')}",
            f"- review_count: {result.get('review_count')}",
            f"- estimated_cost_usd: {result.get('estimated_cost_usd')}",
            f"- plan_file: {result.get('plan_file')}",
        ],
    )
    print(f"COMPLETED: wrote {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
