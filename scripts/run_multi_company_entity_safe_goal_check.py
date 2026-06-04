from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_multi_company_cleanup_entity_safe.py", "-q"],
        text=True,
        capture_output=True,
    )
    report_path = Path("docs/multi-company-entity-safe-goal-result.md")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    status = "PASS" if result.returncode == 0 else "FAIL"
    report_path.write_text(
        "\n".join(
            [
                "# Multi-Company Entity-Safe Goal Result",
                "",
                f"GOAL status: {status}",
                "",
                "Validated policy:",
                "- Multi-company articles are excluded at article/source level.",
                "- Mixed-source products remain visible when non-multi evidence exists.",
                "- Only-multi-source products are marked but not physically deleted.",
                "- Mixed-source exclusive-right events remain visible when non-multi evidence exists.",
                "- Only-multi-source exclusive-right events are marked but not physically deleted.",
                "- Raw articles are preserved.",
                "- Batch import guard skips multi-company article output.",
                "",
                "pytest output:",
                "```",
                result.stdout.strip(),
                result.stderr.strip(),
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"GOAL status: {status}")
    print(f"report={report_path}")
    if result.returncode:
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
