from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs" / "signature-release-birth-coverage-goal-result.md"
PYTEST_TARGETS = [
    "tests/test_product_signature_series_version_policy.py",
    "tests/test_release_month_explicit_text_parser.py",
    "tests/test_release_month_basis_protection.py",
    "tests/test_release_month_inference.py",
    "tests/test_product_release_month_resolver_version_aware.py",
    "tests/test_product_birth_benefit_consolidation.py",
    "tests/test_major_coverage_dedupe.py",
    "tests/test_mobile_coverage_dedupe.py",
    "tests/test_product_detail_coverage_dedupe_shared.py",
]


def run_step(name: str, command: list[str]) -> tuple[str, int, str]:
    try:
        result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, encoding="utf-8", errors="replace")
        output = "\n".join(part for part in [result.stdout, result.stderr] if part)
        return name, result.returncode, output
    except OSError as exc:
        return name, 126, f"Could not start command {command!r}: {exc}"


def main() -> int:
    steps = [
        ("compileall", ["py", "-3", "-m", "compileall", "app", "scripts"]),
        ("dashboard-js-check", ["node", "--check", "app/static/dashboard.js"]),
        ("pytest", ["py", "-3", "-m", "pytest", *PYTEST_TARGETS]),
    ]
    results = [run_step(name, command) for name, command in steps]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Signature/Release/Birth/Coverage Goal Check", ""]
    exit_code = 0
    for name, code, output in results:
        status = "PASS" if code == 0 else "FAIL"
        if code != 0:
            exit_code = code
        lines.extend([f"## {name}: {status}", "", "```text", output[-8000:], "```", ""])
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {REPORT}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
