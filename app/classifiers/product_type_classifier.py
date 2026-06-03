from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


PRODUCT_TYPE_NAMES = {
    "DEATH_WHOLELIFE": "사망(종신/정기)",
    "HEALTH_COMPREHENSIVE": "건강(종합)",
    "SPECIFIC_DISEASE": "특정질병/중대질병",
    "CANCER": "암보험",
    "MEDICAL_INDEMNITY": "실손의료",
    "ACCIDENT_DRIVER": "상해 및 운전자",
    "AUTO": "자동차",
    "SIMPLIFIED_IMPAIRED": "간편(유병자)",
    "DEMENTIA_CARE": "치매간병",
    "CHILD_ADULT_CHILD": "어린이/어른이",
    "DENTAL": "치아",
    "PET": "펫/반려동물",
    "TRAVEL_LEISURE": "여행/레저",
    "PROPERTY_EXPENSE": "재물 및 비용",
    "GUARANTEE_CREDIT": "보증/신용",
    "ANNUITY_SAVINGS": "연금/저축",
    "VARIABLE_UL": "변액/유니버셜",
    "CORPORATE_GROUP_SPECIALTY": "기업/단체/특종",
    "OTHER": "기타",
    "UNKNOWN": "분류불명",
}


@dataclass(frozen=True)
class ProductTypeAssignmentResult:
    code: str
    name_ko: str
    role: str
    basis: str
    evidence_text: str
    confidence: float


@dataclass(frozen=True)
class ProductTypeClassificationResult:
    primary: ProductTypeAssignmentResult
    secondary: list[ProductTypeAssignmentResult]
    needs_review: bool


class ProductTypeClassifier:
    def __init__(self, rules_path: str | Path = "config/product_type_rules.yaml") -> None:
        self.rules_path = Path(rules_path)
        self.rules = self._load_rules()

    def _load_rules(self) -> dict:
        if not self.rules_path.exists():
            return {}
        with self.rules_path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def classify(self, product_name: str | None, text: str | None = None) -> ProductTypeClassificationResult:
        source = f"{product_name or ''}\n{text or ''}"
        scores: list[tuple[int, str, str, str, float]] = []
        for code, rule in self.rules.items():
            strong = [kw for kw in rule.get("strong", []) if kw and kw in source]
            medium = [kw for kw in rule.get("medium", []) if kw and kw in source]
            if not strong and not medium:
                continue
            priority = int(rule.get("priority", 999))
            evidence = strong[0] if strong else medium[0]
            confidence = 0.92 if strong else 0.74
            role = rule.get("default_role", "tag")
            scores.append((priority, code, role, evidence, confidence))

        if not scores:
            return ProductTypeClassificationResult(
                primary=ProductTypeAssignmentResult(
                    "UNKNOWN",
                    self._name_for("UNKNOWN"),
                    "primary",
                    "rule_no_match",
                    "",
                    0.2,
                ),
                secondary=[],
                needs_review=True,
            )

        scores.sort(key=lambda item: item[0])
        primary_priority, primary_code, primary_role, evidence, confidence = self._choose_primary(scores)
        primary = ProductTypeAssignmentResult(
            primary_code,
            self._name_for(primary_code),
            "primary",
            "rule_keyword",
            evidence,
            confidence,
        )

        secondary: list[ProductTypeAssignmentResult] = []
        for priority, code, role, ev, conf in scores:
            if code == primary_code:
                continue
            secondary_role = "secondary" if role in {"primary", "secondary"} else role
            secondary.append(
                ProductTypeAssignmentResult(
                    code,
                    self._name_for(code),
                    secondary_role,
                    "rule_keyword",
                    ev,
                    min(conf, 0.88),
                )
            )

        for modifier_code in ("SIMPLIFIED_IMPAIRED", "VARIABLE_UL"):
            if primary_code == modifier_code:
                continue
            for priority, code, role, ev, conf in scores:
                if code == modifier_code and all(item.code != code for item in secondary):
                    secondary.append(
                        ProductTypeAssignmentResult(
                            code,
                            self._name_for(code),
                            "secondary",
                            "rule_keyword",
                            ev,
                            min(conf, 0.88),
                        )
                    )

        return ProductTypeClassificationResult(primary, secondary, needs_review=primary.confidence < 0.65)

    def _choose_primary(self, scores: list[tuple[int, str, str, str, float]]) -> tuple[int, str, str, str, float]:
        primary_scores = [item for item in scores if item[2] != "secondary"]
        if primary_scores:
            return primary_scores[0]
        return scores[0]

    def _name_for(self, code: str) -> str:
        rule = self.rules.get(code) or {}
        return rule.get("name_ko") or PRODUCT_TYPE_NAMES.get(code, code)
