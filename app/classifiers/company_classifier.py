from __future__ import annotations

from app.normalizers.company_normalizer import CompanyMatch, CompanyNormalizer


class CompanyClassifier:
    def __init__(self) -> None:
        self.normalizer = CompanyNormalizer()

    def classify(self, raw_name: str | None) -> CompanyMatch | None:
        return self.normalizer.normalize(raw_name)
