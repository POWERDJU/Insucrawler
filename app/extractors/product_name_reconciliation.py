from __future__ import annotations

import re
from typing import Any

from app.classifiers.product_type_classifier import ProductTypeClassifier
from app.extractors.extraction_schema import ExtractionResult, ProductTypeValue, VerificationResult
from app.extractors.product_launch_candidate import (
    best_launch_candidate,
    is_negative_product_name,
    normalize_launch_product_name,
)


PRODUCT_NAME_FIELDS = {
    "identity.raw_product_name",
    "identity.normalized_product_name_candidate",
}


def reconcile_extraction(
    extraction: ExtractionResult,
    source_text: str | None,
    verification: VerificationResult | None = None,
) -> tuple[ExtractionResult, list[dict[str, Any]]]:
    corrections: list[dict[str, Any]] = []
    verifier_suggestions = _verifier_product_name_suggestions(verification)
    launch_candidate = best_launch_candidate(source_text)
    classifier = ProductTypeClassifier()

    for index, product in enumerate(extraction.products):
        identity = product.identity
        original_name = identity.raw_product_name or identity.normalized_product_name_candidate
        final_name = original_name
        reason = None
        basis = None
        evidence = None

        suggested = verifier_suggestions.get(index)
        if suggested:
            normalized_suggestion = normalize_launch_product_name(str(suggested.get("suggested_value") or ""))
            if normalized_suggestion:
                final_name = normalized_suggestion
                reason = suggested.get("reason") or "verifier suggested corrected product name"
                basis = suggested.get("suggested_basis") or "verifier_suggested_value"
                evidence = suggested.get("evidence_text")

        if launch_candidate and (is_negative_product_name(final_name) or final_name != launch_candidate.normalized_name):
            if is_negative_product_name(final_name) or is_negative_product_name(original_name):
                final_name = launch_candidate.normalized_name
                reason = "앱/서비스/할인명 대신 본문 신규 출시 문장에 직접 연결된 보험상품명을 사용"
                basis = "launch_sentence_candidate"
                evidence = launch_candidate.evidence_text

        if final_name and is_negative_product_name(final_name):
            corrections.append(
                _audit(
                    index,
                    field="identity.raw_product_name",
                    extracted_value=original_name,
                    suggested_value=None,
                    evidence_text=evidence,
                    reason="상품명 후보가 앱/서비스/할인/채널명으로 판단되어 저장 대상에서 제외",
                    basis="negative_product_name_pattern",
                    final_value=None,
                    severity="high",
                )
            )
            identity.raw_product_name = None
            identity.normalized_product_name_candidate = None
            product.needs_human_review = True
            product.missing_fields.append("valid_product_name")
            continue

        if final_name and final_name != original_name:
            corrections.append(
                _audit(
                    index,
                    field="identity.raw_product_name",
                    extracted_value=original_name,
                    suggested_value=final_name,
                    evidence_text=evidence,
                    reason=reason or "상품명 보정",
                    basis=basis or "product_name_reconciliation",
                    final_value=final_name,
                    severity="high",
                )
            )
            identity.raw_product_name = final_name
            identity.normalized_product_name_candidate = final_name
            if evidence:
                product.evidence.product_name_evidence = evidence
            if product.confidence.identity < 0.9:
                product.confidence.identity = 0.9

        name_for_classification = identity.raw_product_name or identity.normalized_product_name_candidate
        rule = classifier.classify(name_for_classification)
        primary = product.product_type_classification.primary_product_type
        if rule.primary.code != "UNKNOWN" and primary.code != rule.primary.code:
            corrections.append(
                _audit(
                    index,
                    field="product_type_classification.primary_product_type.code",
                    extracted_value=primary.code,
                    suggested_value=rule.primary.code,
                    evidence_text=rule.primary.evidence_text,
                    reason=f"{name_for_classification}은(는) {rule.primary.name_ko} 상품군 규칙에 더 명확히 부합",
                    basis="rule_keyword",
                    final_value=rule.primary.code,
                    severity="medium",
                )
            )
            product.product_type_classification.primary_product_type = ProductTypeValue(
                code=rule.primary.code,
                name_ko=rule.primary.name_ko,
                basis=rule.primary.basis,
                evidence_text=rule.primary.evidence_text,
                confidence=rule.primary.confidence,
            )
            if product.confidence.product_type < rule.primary.confidence:
                product.confidence.product_type = rule.primary.confidence

        _merge_rule_secondaries(product, rule)

    return extraction, corrections


def _merge_rule_secondaries(product, rule) -> None:
    primary_code = product.product_type_classification.primary_product_type.code
    existing_codes = {item.code for item in product.product_type_classification.secondary_product_types}
    for secondary in rule.secondary:
        if secondary.code == primary_code or secondary.code in existing_codes:
            continue
        product.product_type_classification.secondary_product_types.append(
            ProductTypeValue(
                code=secondary.code,
                name_ko=secondary.name_ko,
                basis=secondary.basis,
                evidence_text=secondary.evidence_text,
                confidence=secondary.confidence,
            )
        )
        existing_codes.add(secondary.code)


def _verifier_product_name_suggestions(verification: VerificationResult | None) -> dict[int, dict[str, Any]]:
    if verification is None:
        return {}
    suggestions: dict[int, dict[str, Any]] = {}
    for check in verification.field_checks:
        if check.verdict != "incorrect" or check.severity not in {"high", "critical"}:
            continue
        product_index = _product_index(check.field_path)
        if product_index is None:
            continue
        normalized_path = re.sub(r"^products\[\d+\]\.", "", check.field_path)
        if normalized_path not in PRODUCT_NAME_FIELDS:
            continue
        if check.suggested_value is None:
            continue
        suggestions[product_index] = check.model_dump()
    return suggestions


def _product_index(field_path: str) -> int | None:
    match = re.match(r"products\[(\d+)\]", field_path or "")
    if not match:
        return None
    return int(match.group(1))


def _audit(
    index: int,
    *,
    field: str,
    extracted_value: Any,
    suggested_value: Any,
    evidence_text: str | None,
    reason: str,
    basis: str,
    final_value: Any,
    severity: str,
) -> dict[str, Any]:
    return {
        "field_path": f"products[{index}].{field}",
        "extracted_value": extracted_value,
        "verdict": "incorrect",
        "reason": reason,
        "suggested_value": suggested_value,
        "suggested_basis": basis,
        "evidence_text": evidence_text,
        "severity": severity,
        "final_value": final_value,
    }
