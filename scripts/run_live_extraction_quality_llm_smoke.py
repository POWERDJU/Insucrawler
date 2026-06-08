from __future__ import annotations

import json
import os
from pathlib import Path


def main() -> None:
    enabled = os.getenv("ENABLE_LIVE_EXTRACTION_QUALITY_LLM_SMOKE", "").strip().lower() in {"1", "true", "yes", "on"}
    result = {
        "enabled": enabled,
        "max_cases": int(os.getenv("LIVE_EXTRACTION_QUALITY_LLM_SMOKE_MAX_CASES", "5")),
        "max_cost_usd": float(os.getenv("LIVE_EXTRACTION_QUALITY_LLM_SMOKE_MAX_COST_USD", "1")),
        "status": "skipped",
        "reason": "Set ENABLE_LIVE_EXTRACTION_QUALITY_LLM_SMOKE=true to run a bounded dry-run smoke.",
    }
    output = Path("docs/live-extraction-quality-llm-smoke-result.md")
    output.parent.mkdir(exist_ok=True)
    if not enabled:
        output.write_text("# Live Extraction Quality LLM Smoke\n\nSkipped. Live smoke is disabled by default.\n", encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False))
        return
    result["status"] = "not_implemented"
    result["reason"] = "Live smoke is intentionally gated; wire a batch/cached provider before enabling in CI."
    output.write_text(
        "# Live Extraction Quality LLM Smoke\n\n"
        "Live smoke was enabled, but this script is a dry-run guard scaffold. "
        "Connect a bounded provider implementation before production use.\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
