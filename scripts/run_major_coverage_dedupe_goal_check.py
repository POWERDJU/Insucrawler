from __future__ import annotations

import subprocess
import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.coverage_dedupe_service import dedupe_major_coverages


REPORT = ROOT / "docs" / "major-coverage-dedupe-goal-result.md"


def _coverage(name: str, **kwargs):
    return {
        "coverage_id": kwargs.pop("coverage_id", None),
        "coverage_name_raw": name,
        "coverage_name_normalized": name,
        "risk_area": kwargs.pop("risk_area", ""),
        "benefit_type": kwargs.pop("benefit_type", ""),
        "max_amount_krw": kwargs.pop("max_amount_krw", None),
        "condition_text": kwargs.pop("condition_text", ""),
        "coverage_summary": kwargs.pop("coverage_summary", f"{name} 보장"),
        "confidence": kwargs.pop("confidence", 0.9),
        **kwargs,
    }


def run_checks() -> dict[str, object]:
    cases = {
        "pregnancy_support": [
            _coverage("임신지원금", coverage_id=1),
            _coverage("임신 지원금 특약", coverage_id=2),
        ],
        "birth_support": [
            _coverage("출산지원금", coverage_id=3),
            _coverage("출산 축하금", coverage_id=4),
        ],
        "cancer_no_overmerge": [
            _coverage("암진단비", coverage_id=5),
            _coverage("유사암진단비", coverage_id=6),
            _coverage("고액암진단비", coverage_id=7),
        ],
        "surgery_no_overmerge": [
            _coverage("수술비", coverage_id=8),
            _coverage("1종 수술비", coverage_id=9),
            _coverage("2종 수술비", coverage_id=10),
        ],
        "driver_no_overmerge": [
            _coverage("벌금", coverage_id=11, risk_area="운전자"),
            _coverage("변호사선임비용", coverage_id=12, risk_area="운전자"),
            _coverage("교통사고처리지원금", coverage_id=13, risk_area="운전자"),
        ],
    }
    counts = {}
    for name, coverages in cases.items():
        deduped, summary = dedupe_major_coverages(coverages)
        counts[name] = {"raw": summary["raw_count"], "deduped": summary["deduped_count"]}
    assertions = {
        "pregnancy_support displayed once": counts["pregnancy_support"]["deduped"] == 1,
        "birth_support displayed once": counts["birth_support"]["deduped"] == 1,
        "cancer diagnosis does not merge minor/high/general": counts["cancer_no_overmerge"]["deduped"] == 3,
        "surgery classes do not overmerge": counts["surgery_no_overmerge"]["deduped"] == 3,
        "driver legal components do not overmerge": counts["driver_no_overmerge"]["deduped"] == 3,
    }
    return {"counts": counts, "assertions": assertions, "status": "PASS" if all(assertions.values()) else "FAIL"}


def run_pytest() -> tuple[int, str]:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_major_coverage_dedupe_generalized.py",
        "tests/test_major_coverage_dedupe_no_overmerge.py",
        "tests/test_major_coverage_dedupe_llm_plan_validator.py",
        "tests/test_product_detail_coverage_api_deduped.py",
        "tests/test_mobile_coverage_dedupe_generalized.py",
        "tests/test_dashboard_export_coverage_deduped.py",
        "tests/test_major_coverage_duplicate_audit_script.py",
    ]
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, encoding="utf-8", errors="replace", env=env)
    return proc.returncode, (proc.stdout or "")[-4000:] + (proc.stderr or "")[-2000:]


def write_report(result: dict[str, object], pytest_code: int, pytest_output: str) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Major Coverage Dedupe Goal Result",
        "",
        f"- GOAL status: {result['status'] if pytest_code == 0 else 'FAIL'}",
        f"- pytest exit code: {pytest_code}",
        "",
        "## Counts",
    ]
    for name, count in result["counts"].items():
        lines.append(f"- {name}: raw {count['raw']} -> deduped {count['deduped']}")
    lines.extend(["", "## Assertions"])
    for name, passed in result["assertions"].items():
        lines.append(f"- {'PASS' if passed else 'FAIL'}: {name}")
    lines.extend(["", "## Pytest Output", "```", pytest_output.strip(), "```", ""])
    REPORT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    result = run_checks()
    pytest_code, pytest_output = run_pytest()
    write_report(result, pytest_code, pytest_output)
    print({"status": result["status"] if pytest_code == 0 else "FAIL", "report": str(REPORT), "pytest_code": pytest_code})
    if result["status"] != "PASS" or pytest_code != 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
