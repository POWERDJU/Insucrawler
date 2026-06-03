from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CoverageClassification:
    risk_area: str
    benefit_type: str
    coverage_group: str
    confidence: float
    basis: str


class CoverageClassifier:
    def __init__(self, dictionary_path: str | Path = "config/coverage_dictionary.csv") -> None:
        self.dictionary_path = Path(dictionary_path)
        self.rules: list[dict[str, str]] = []
        self.load()

    def load(self) -> None:
        if not self.dictionary_path.exists():
            return
        with self.dictionary_path.open("r", encoding="utf-8-sig", newline="") as f:
            self.rules = list(csv.DictReader(f))

    def classify(self, coverage_name: str | None, text: str | None = None) -> CoverageClassification:
        source = f"{coverage_name or ''}\n{text or ''}"
        for row in self.rules:
            keyword = row.get("keyword", "")
            if keyword and keyword in source:
                return CoverageClassification(
                    row.get("risk_area") or "unknown",
                    row.get("benefit_type") or "unknown",
                    row.get("coverage_group") or "기타",
                    0.9,
                    f"dictionary_keyword:{keyword}",
                )
        if "암" in source:
            return CoverageClassification("암", "unknown", "암보장", 0.7, "rule_keyword:암")
        if "운전자" in source or "교통사고" in source:
            return CoverageClassification("운전자", "unknown", "운전자보장", 0.7, "rule_keyword:운전자")
        return CoverageClassification("unknown", "unknown", "기타", 0.3, "no_match")
