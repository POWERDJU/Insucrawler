from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


GENERIC_WORDS = {
    "보험",
    "보장",
    "담보",
    "특약",
    "상품",
    "급여",
    "보험금",
    "비용",
    "지급",
    "지원",
    "관련",
    "주요",
    "중심",
    "제공",
    "coverage",
    "benefit",
    "insurance",
}

BENEFIT_ALIASES = {
    "cash": "cash_payment",
    "cashbenefit": "cash_payment",
    "cashpayment": "cash_payment",
    "supportfund": "cash_payment",
    "supportpayment": "cash_payment",
    "indemnity": "indemnity",
    "lumpsum": "cash_payment",
    "진단": "diagnosis",
    "진단비": "diagnosis",
    "진단금": "diagnosis",
    "수술": "surgery",
    "수술비": "surgery",
    "입원": "hospitalization",
    "입원비": "hospitalization",
    "입원일당": "hospitalization_daily",
    "치료": "treatment",
    "치료비": "treatment",
    "사망": "death",
    "사망보험금": "death",
    "법률": "legal_expense",
    "법률비용": "legal_expense",
    "비용보상": "expense_reimbursement",
    "손해보상": "expense_reimbursement",
    "배상책임": "liability",
    "납입면제": "premium_waiver",
    "납입유예": "premium_deferral",
}


@dataclass
class CoverageGroup:
    canonical_key: str
    canonical_coverage: dict[str, Any]
    duplicate_coverage_ids: list[int]
    source_count: int
    merge_reason: str
    component_tokens: list[str]


def normalize_coverage_text(text: Any) -> str:
    if text is None:
        return ""
    return re.sub(r"[^0-9a-zA-Z가-힣]+", "", str(text).casefold())


def normalize_coverage_name(name: Any) -> str:
    text = normalize_coverage_text(name)
    for suffix in ("특약", "담보", "보장", "보험금", "급여금"):
        if len(text) > len(suffix) + 2 and text.endswith(suffix):
            text = text[: -len(suffix)]
    return text


def normalize_coverage_area(area: Any) -> str:
    compact = normalize_coverage_text(area)
    if not compact or compact in {"unknown", "기타"}:
        return ""
    return _semantic_family_for_text(compact) or compact


def normalize_benefit_type(benefit_type: Any) -> str:
    compact = normalize_coverage_text(benefit_type)
    if not compact or compact == "unknown":
        return ""
    for needle, replacement in BENEFIT_ALIASES.items():
        if normalize_coverage_text(needle) in compact:
            return replacement
    return compact


def normalize_payment_condition(condition: Any) -> str:
    compact = normalize_coverage_text(condition)
    compact = re.sub(r"최대\d+(?:억|만|천)?원?", "", compact)
    compact = re.sub(r"\d+(?:일|회|년|개월|종|형|급)", "", compact)
    return compact


def normalize_amount(amount: Any) -> str:
    if amount in (None, "", 0, "0", "unknown"):
        return ""
    try:
        return str(int(float(amount)))
    except (TypeError, ValueError):
        return normalize_coverage_text(amount)


def build_coverage_component_tokens(coverage: dict[str, Any]) -> set[str]:
    text = _coverage_text(coverage)
    compact = normalize_coverage_text(text)
    tokens: set[str] = set()
    for token in re.findall(r"[0-9a-zA-Z가-힣]+", text.casefold()):
        normalized = normalize_coverage_text(token)
        if len(normalized) >= 2 and normalized not in GENERIC_WORDS:
            tokens.add(normalized)
    for marker, token in [
        ("유사암", "minor_cancer"),
        ("소액암", "minor_cancer"),
        ("고액암", "high_value_cancer"),
        ("일반암", "general_cancer"),
        ("중환자", "icu"),
        ("집중치료", "icu"),
        ("요양병원", "care_hospital"),
        ("질병사망", "disease_death"),
        ("상해사망", "injury_death"),
        ("질병수술", "disease_surgery"),
        ("상해수술", "injury_surgery"),
        ("1종", "surgery_class_1"),
        ("2종", "surgery_class_2"),
        ("3종", "surgery_class_3"),
        ("벌금", "driver_fine"),
        ("변호사", "driver_attorney"),
        ("교통사고처리지원", "driver_accident_support"),
        ("납입면제", "premium_waiver"),
        ("납입유예", "premium_deferral"),
        ("화재", "fire"),
        ("배상책임", "liability"),
    ]:
        if marker in compact:
            tokens.add(token)
    return tokens


def build_coverage_identity_key(coverage: dict[str, Any]) -> str:
    family = coverage_component_family(coverage)
    amount = normalize_amount(coverage.get("max_amount_krw"))
    condition = normalize_payment_condition(coverage.get("condition_text") or coverage.get("limit_text"))
    benefit = normalize_benefit_type(coverage.get("benefit_type"))
    area = normalize_coverage_area(coverage.get("risk_area"))
    if family:
        detail = _coverage_distinction_token(family, coverage)
        if family in {
            "pregnancy_support",
            "birth_support",
            "legal_expense_domestic_violence",
            "legal_expense",
            "support_cash_payment",
        }:
            condition = ""
        parts = [f"family:{family}", detail, amount, condition]
        return "|".join(part for part in parts if part)
    name = normalize_coverage_name(
        coverage.get("coverage_name_normalized")
        or coverage.get("coverage_name_raw")
        or coverage.get("coverage_summary")
    )
    return "|".join(part for part in [name, area, benefit, amount, condition] if part)


def group_duplicate_coverages(coverages: list[dict[str, Any]]) -> list[CoverageGroup]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for coverage in coverages or []:
        key = build_coverage_identity_key(coverage)
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].append(coverage)
    result: list[CoverageGroup] = []
    for key in order:
        members = grouped[key]
        canonical = select_best_coverage_record(members)
        tokens = sorted(set().union(*(build_coverage_component_tokens(item) for item in members)))
        result.append(
            CoverageGroup(
                canonical_key=key,
                canonical_coverage=canonical,
                duplicate_coverage_ids=[
                    int(item.get("coverage_id"))
                    for item in members
                    if item.get("coverage_id") and item.get("coverage_id") != canonical.get("coverage_id")
                ],
                source_count=len(members),
                merge_reason="same normalized coverage identity" if len(members) > 1 else "unique coverage",
                component_tokens=tokens,
            )
        )
    return result


def select_best_coverage_record(*args: Any) -> dict[str, Any]:
    if len(args) == 1 and isinstance(args[0], list):
        group = args[0]
        return sorted(group, key=_coverage_selection_score, reverse=True)[0] if group else {}
    if len(args) == 2:
        left, right = args
        return right if _coverage_selection_score(right) > _coverage_selection_score(left) else left
    raise TypeError("select_best_coverage_record expects a group or two coverage records")


def dedupe_major_coverages(coverages: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    groups = group_duplicate_coverages(coverages or [])
    deduped = [group.canonical_coverage for group in groups]
    return deduped, summarize_coverage_dedupe(groups, raw_count=len(coverages or []))


def summarize_coverage_dedupe(groups: list[CoverageGroup], raw_count: int | None = None) -> dict[str, Any]:
    raw = raw_count if raw_count is not None else sum(group.source_count for group in groups)
    deduped = len(groups)
    duplicate_groups = [group for group in groups if group.source_count > 1]
    return {
        "raw_count": raw,
        "deduped_count": deduped,
        "duplicate_count": max(raw - deduped, 0),
        "deduped_group_count": len(duplicate_groups),
        "groups": [
            {
                "canonical_key": group.canonical_key,
                "canonical_coverage_id": group.canonical_coverage.get("coverage_id"),
                "canonical_coverage_name": group.canonical_coverage.get("coverage_name_normalized")
                or group.canonical_coverage.get("coverage_name_raw"),
                "duplicate_coverage_ids": group.duplicate_coverage_ids,
                "source_count": group.source_count,
                "merge_reason": group.merge_reason,
                "component_tokens": group.component_tokens,
            }
            for group in duplicate_groups
        ],
    }


def coverage_component_family(coverage: dict[str, Any]) -> str | None:
    name_compact = normalize_coverage_text(
        " ".join(
            str(coverage.get(key) or "")
            for key in ("coverage_name_normalized", "coverage_name_raw")
        )
    )
    if "출산" in name_compact or "childbirth" in name_compact or re.search(r"\bbirth\b", name_compact):
        return "birth_support"
    if "임신" in name_compact or "pregnancy" in name_compact or "maternity" in name_compact:
        return "pregnancy_support"
    text = _coverage_text(coverage)
    compact = normalize_coverage_text(text)
    semantic = _semantic_family_for_text(compact)
    if semantic:
        return semantic
    return None


def _semantic_family_for_text(compact: str) -> str | None:
    if not compact:
        return None
    if "임신" in compact or "pregnancy" in compact or "maternity" in compact:
        return "pregnancy_support"
    if "출산" in compact or "childbirth" in compact or re.search(r"\bbirth\b", compact):
        return "birth_support"
    if ("가정폭력" in compact or "가족폭력" in compact or "domesticviolence" in compact) and (
        "법률" in compact or "변호사" in compact or "legal" in compact
    ):
        return "legal_expense_domestic_violence"
    if "운전자" in compact or "교통사고처리" in compact or "벌금" in compact or "driver" in compact:
        if "벌금" in compact:
            return "driver_fine"
        if "변호사" in compact or "선임" in compact:
            return "driver_attorney_fee"
        if "교통사고처리" in compact:
            return "driver_accident_support"
    if "암" in compact and ("진단" in compact or "diagnosis" in compact):
        return "cancer_diagnosis"
    if "수술" in compact or "surgery" in compact:
        return "surgery_benefit"
    if "입원" in compact or "hospitalization" in compact or "inpatient" in compact:
        return "hospitalization_daily"
    if "사망" in compact or "death" in compact:
        return "death_benefit"
    if "치매" in compact or "dementia" in compact or "간병" in compact or "care" in compact:
        if "진단" in compact:
            return "dementia_diagnosis"
        return "dementia_care"
    if "치료" in compact or "chemotherapy" in compact or "treatment" in compact or "항암" in compact or "방사선" in compact:
        return "treatment_cost"
    if "납입면제" in compact or "premiumwaiver" in compact:
        return "premium_waiver"
    if "납입유예" in compact or "premiumdeferral" in compact:
        return "premium_deferral"
    if "화재" in compact or "배상책임" in compact or "property" in compact or "liability" in compact:
        if "배상책임" in compact or "liability" in compact:
            return "property_liability"
        return "property_expense"
    if "법률" in compact or "변호사" in compact or "소송" in compact or "legalexpense" in compact:
        return "legal_expense"
    if "지원금" in compact or "축하금" in compact:
        return "support_cash_payment"
    return None


def _coverage_distinction_token(family: str, coverage: dict[str, Any]) -> str:
    text = _coverage_text(coverage)
    compact = normalize_coverage_text(text)
    tokens = build_coverage_component_tokens(coverage)
    if family == "cancer_diagnosis":
        for token in ("minor_cancer", "high_value_cancer", "general_cancer"):
            if token in tokens:
                return token
        return "cancer_general"
    if family == "surgery_benefit":
        parts = [token for token in ("disease_surgery", "injury_surgery", "surgery_class_1", "surgery_class_2", "surgery_class_3") if token in tokens]
        return ",".join(parts) or "surgery_general"
    if family == "hospitalization_daily":
        for token in ("icu", "care_hospital"):
            if token in tokens:
                return token
        if "상해" in compact:
            return "injury_hospitalization"
        if "질병" in compact:
            return "disease_hospitalization"
        return "hospitalization_general"
    if family == "death_benefit":
        for token in ("disease_death", "injury_death"):
            if token in tokens:
                return token
        return "death_general"
    if family == "treatment_cost":
        if "항암" in compact or "chemotherapy" in compact:
            return "anticancer_treatment"
        if "방사선" in compact:
            return "radiation_treatment"
        if "표적" in compact:
            return "targeted_treatment"
        return "treatment_general"
    return ""


def _coverage_selection_score(coverage: dict[str, Any]) -> tuple[Any, ...]:
    name = coverage.get("coverage_name_normalized") or coverage.get("coverage_name_raw") or ""
    summary = coverage.get("coverage_summary") or ""
    detail_level = coverage.get("detail_level") or ""
    return (
        1 if detail_level == "exact_coverage" else 0,
        1 if coverage.get("coverage_summary") else 0,
        len(str(summary)),
        1 if coverage.get("max_amount_krw") else 0,
        1 if coverage.get("condition_text") else 0,
        1 if coverage.get("evidence_text") else 0,
        len(str(name)),
        float(coverage.get("confidence") or 0.0),
        -int(coverage.get("display_order") or 0),
        -int(coverage.get("coverage_id") or 0),
    )


def _coverage_text(coverage: dict[str, Any]) -> str:
    return " ".join(
        str(coverage.get(key) or "")
        for key in (
            "coverage_name_normalized",
            "coverage_name_raw",
            "risk_area",
            "benefit_type",
            "coverage_group",
            "condition_text",
            "limit_text",
            "coverage_summary",
            "evidence_text",
        )
    )
