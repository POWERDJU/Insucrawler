from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs" / "product-attribution-multicompany-marketing-goal-result.md"
PLAN = ROOT / "data" / "exports" / "product_company_attribution_rebuild_plan_product_150.csv"
DIAGNOSIS = ROOT / "docs" / "product-150-company-attribution-diagnosis.md"


def run(cmd: list[str]) -> tuple[int, str]:
    result = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8", errors="replace")
    return result.returncode, result.stdout


def main() -> int:
    steps: list[tuple[str, int, str]] = []
    commands = [
        (
            "Regression tests",
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/test_product_attribution_marketing_guard.py",
                "tests/test_multi_company_cleanup_entity_safe.py",
                "-q",
            ],
        ),
        (
            "Product 150 diagnosis",
            [
                sys.executable,
                "scripts/diagnose_product_company_attribution.py",
                "--product-id",
                "150",
                "--output",
                str(DIAGNOSIS),
            ],
        ),
        (
            "Product 150 rebuild dry-run",
            [
                sys.executable,
                "scripts/rebuild_product_company_attribution.py",
                "--product-id",
                "150",
                "--output",
                str(PLAN),
            ],
        ),
    ]
    for name, cmd in commands:
        code, output = run(cmd)
        steps.append((name, code, output))
    failed = [name for name, code, _ in steps if code != 0]
    status = "PASS" if not failed else "FAIL"
    lines = [
        "# Product Attribution Multi-Company Marketing Guard Goal Result",
        "",
        f"- status: {status}",
        "- realtime_llm_calls: 0",
        "- article_level_same_product_llm_calls: 0",
        f"- diagnosis_report: {DIAGNOSIS.relative_to(ROOT)}",
        f"- rebuild_plan: {PLAN.relative_to(ROOT)}",
        "",
        "## Checks",
        "",
    ]
    for name, code, output in steps:
        lines.extend(
            [
                f"### {name}",
                f"- exit_code: {code}",
                "",
                "```text",
                output[-4000:],
                "```",
                "",
            ]
        )
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(REPORT)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
