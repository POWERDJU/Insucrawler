from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "docs" / "product-version-birth-mobile-goal-result.md"
TESTS = [
    "tests/test_product_signature_series_version_policy.py",
    "tests/test_product_birth_benefit_consolidation.py",
    "tests/test_product_release_month_resolver_version_aware.py",
    "tests/test_product_detail_coverage_dedupe_shared.py",
]


def main() -> int:
    command = [sys.executable, "-m", "pytest", "-q", *TESTS]
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    status = "PASS" if result.returncode == 0 else "FAIL"
    REPORT_PATH.write_text(
        "\n".join(
            [
                "# Product Version/Birth/Mobile Goal Check",
                "",
                f"- status: {status}",
                f"- checked_at: {datetime.now().isoformat(timespec='seconds')}",
                f"- command: `{' '.join(command)}`",
                "",
                "## Scope",
                "",
                "- Signature Women 3.0/4.0 remain separate.",
                "- Same-version Signature Women variants merge without LLM.",
                "- Birth/pregnancy benefit component variants merge together.",
                "- Birth benefit components do not merge into the body product.",
                "- Release month prefers version-compatible direct launch articles.",
                "- Product detail coverage rows are deduplicated for PC and mobile views.",
                "",
                "## Pytest Output",
                "",
                "```text",
                result.stdout.strip(),
                result.stderr.strip(),
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(REPORT_PATH)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
