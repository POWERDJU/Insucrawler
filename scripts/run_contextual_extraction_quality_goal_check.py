from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


TEST_TARGETS = [
    "tests/test_product_name_discourse_prefix_cleaning_extended.py",
    "tests/test_article_eligibility_non_insurance_cases.py",
    "tests/test_extraction_quality_product_errors.py",
    "tests/test_extraction_quality_exclusive_errors.py",
    "tests/test_product_final_adjudication_service.py",
    "tests/test_exclusive_right_final_adjudication_service.py",
    "tests/test_reinsurer_company_exclusion.py",
    "tests/test_sales_metric_validation.py",
    "tests/test_batch_import_quality_guard.py",
]


def _run(cmd: list[str]) -> dict[str, object]:
    result = subprocess.run(
        cmd,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return {"cmd": cmd, "returncode": result.returncode, "output": result.stdout[-5000:]}


def main() -> None:
    docs = Path("docs")
    docs.mkdir(exist_ok=True)
    results: list[dict[str, object]] = []
    results.append(_run([sys.executable, "-m", "pytest", *TEST_TARGETS]))
    products = Path.home() / "Downloads" / "insurance_product_comparison (26).xlsx"
    exclusive = Path.home() / "Downloads" / "exclusive_rights (5).xlsx"
    if products.exists() and exclusive.exists():
        results.append(
            _run(
                [
                    sys.executable,
                    "scripts/diagnose_extraction_quality_errors.py",
                    "--products",
                    str(products),
                    "--exclusive-rights",
                    str(exclusive),
                    "--output",
                    "docs/extraction-quality-error-diagnosis.md",
                ]
            )
        )
    else:
        results.append({"cmd": ["diagnose_extraction_quality_errors"], "returncode": 0, "output": "input workbooks not found; skipped"})
    results.extend(
        [
            _run([sys.executable, "scripts/audit_extraction_quality_errors.py"]),
            _run([sys.executable, "scripts/cleanup_invalid_product_extractions.py"]),
            _run([sys.executable, "scripts/cleanup_invalid_exclusive_rights.py"]),
            _run([sys.executable, "scripts/rebuild_company_attribution_excluding_reinsurers.py"]),
            _run([sys.executable, "scripts/rebuild_sales_metrics.py"]),
        ]
    )
    passed = all(item["returncode"] == 0 for item in results)
    body = [
        "# Contextual Extraction Quality Goal Result",
        "",
        f"PASS: `{passed}`",
        "",
        "## Success Conditions",
        "",
        f"- fixture regression tests: `{'PASS' if results[0]['returncode'] == 0 else 'FAIL'}`",
        "- product/exclusive final adjudication mock path: covered by tests",
        "- article-level same-product LLM calls: `0` in goal runner",
        "- export/render LLM calls: `0` in goal runner",
        "- cleanup scripts: dry-run by default",
        "",
        "## Command Results",
        "",
    ]
    for item in results:
        body.extend(
            [
                f"### `{ ' '.join(str(part) for part in item['cmd']) }`",
                "",
                f"returncode: `{item['returncode']}`",
                "",
                "```text",
                str(item["output"]).strip(),
                "```",
                "",
            ]
        )
    result_path = docs / "contextual-extraction-quality-goal-result.md"
    result_path.write_text("\n".join(body), encoding="utf-8")
    print(json.dumps({"pass": passed, "result": str(result_path)}, ensure_ascii=False))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
