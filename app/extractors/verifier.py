from __future__ import annotations

from app.extractors.extraction_schema import VerificationResult


def summarize_verification(result: VerificationResult) -> dict[str, int | float | bool | str]:
    conflict_count = sum(1 for check in result.field_checks if check.verdict in {"unsupported", "incorrect", "ambiguous"})
    critical_conflict_count = sum(1 for check in result.field_checks if check.severity == "critical")
    return {
        "agreement_score": max(0.0, 1.0 - (conflict_count / max(len(result.field_checks), 1))),
        "conflict_count": conflict_count,
        "critical_conflict_count": critical_conflict_count,
        "final_status": result.verification_status,
        "needs_human_review": result.needs_human_review or critical_conflict_count > 0,
    }
