from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.database import SessionLocal, engine
from app.db.migrations import init_db
from app.db.models import FactExclusiveUseRight
from app.services.exclusive_right_consolidation_service import ExclusiveRightBlockingService, ExclusiveRightConsolidationService
from app.services.exclusive_right_local_context import (
    has_bad_subject_tail,
    is_generic_or_weak_subject,
    is_weak_subject,
    normalize_search_key,
    resolve_subject_reference,
    validate_exclusive_subject_before_save,
)


EXPORT_PATH = Path("data/exports/exclusive_right_rebuild_plan.csv")


def write_plan(db, path: Path = EXPORT_PATH) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    blocks = ExclusiveRightBlockingService().build_blocks(db)
    weak_rows = (
        db.query(FactExclusiveUseRight)
        .filter(FactExclusiveUseRight.event_status.in_(["active", "provisional", "review"]))
        .all()
    )
    standalone_weak = [row for row in weak_rows if is_weak_subject(row.subject_name)]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "group_id",
                "canonical_subject_name",
                "canonical_company_name",
                "canonical_acquired_year_month",
                "canonical_exclusivity_months",
                "duplicate_exclusive_right_ids",
                "subject_names",
                "article_titles",
                "article_urls",
                "merge_reason",
                "attribution_warnings",
                "suggested_action",
                "old_subject_name",
                "proposed_subject_name",
                "subject_quality_issue",
                "resolution_source",
                "resolution_reason",
            ]
        )
        for index, block in enumerate(blocks, start=1):
            candidates = sorted(block.candidates, key=lambda row: (is_weak_subject(row.subject_name), -len(row.subject_core_key or ""), row.exclusive_right_id))
            canonical = candidates[0]
            duplicates = [str(row.exclusive_right_id) for row in candidates[1:]]
            writer.writerow(
                [
                    f"block-{index}",
                    canonical.subject_name,
                    canonical.company_name_normalized,
                    canonical.acquired_year_month,
                    canonical.exclusivity_months,
                    "|".join(duplicates),
                    "|".join(row.subject_name for row in candidates),
                    "|".join(row.primary_article_title or "" for row in candidates),
                    "|".join(row.primary_article_url or "" for row in candidates),
                    block.reason,
                    "weak_subject_in_block" if any(is_weak_subject(row.subject_name) for row in candidates) else "",
                    "merge_or_review",
                    "",
                    "",
                    "",
                    "",
                    "",
                ]
            )
        false_attribution_rows = []
        quality_rows = []
        for row in weak_rows:
            validation = _validate_row(row)
            if is_generic_or_weak_subject(row.subject_name) or has_bad_subject_tail(row.subject_name) or validation.needs_review:
                quality_rows.append((row, validation))
            if is_weak_subject(row.subject_name):
                continue
            if validation.needs_review and validation.reason.startswith("weak_reference_type_conflict"):
                false_attribution_rows.append((row, validation.reason))
        for row in standalone_weak:
            validation = _validate_row(row)
            writer.writerow(
                [
                    f"weak-{row.exclusive_right_id}",
                    "",
                    row.company_name_normalized,
                    row.acquired_year_month,
                    row.exclusivity_months,
                    str(row.exclusive_right_id),
                    row.subject_name,
                    row.primary_article_title or "",
                    row.primary_article_url or "",
                    "weak subject cannot be canonical",
                    "subject_name is pronoun/weak phrase",
                    "reject_or_review",
                    row.subject_name,
                    validation.subject_name or "",
                    "weak_subject",
                    "subject_quality_validation",
                    validation.reason,
                ]
            )
        for row, reason in false_attribution_rows:
            writer.writerow(
                [
                    f"false-attribution-{row.exclusive_right_id}",
                    "",
                    row.company_name_normalized,
                    row.acquired_year_month,
                    row.exclusivity_months,
                    str(row.exclusive_right_id),
                    row.subject_name,
                    row.primary_article_title or "",
                    row.primary_article_url or "",
                    "subject conflicts with weak local reference type",
                    reason,
                    "review",
                    row.subject_name,
                    "",
                    "false_attribution",
                    "subject_quality_validation",
                    reason,
                ]
            )
        seen_quality = {row.exclusive_right_id for row in standalone_weak} | {row.exclusive_right_id for row, _ in false_attribution_rows}
        for row, validation in quality_rows:
            if row.exclusive_right_id in seen_quality:
                continue
            writer.writerow(
                [
                    f"quality-{row.exclusive_right_id}",
                    validation.subject_name or "",
                    row.company_name_normalized,
                    row.acquired_year_month,
                    row.exclusivity_months,
                    str(row.exclusive_right_id),
                    row.subject_name,
                    row.primary_article_title or "",
                    row.primary_article_url or "",
                    "subject quality validation",
                    validation.reason,
                    "replace_or_review" if validation.subject_name else "reject_or_review",
                    row.subject_name,
                    validation.subject_name or "",
                    "bad_or_generic_subject",
                    "subject_quality_validation",
                    validation.reason,
                ]
            )
    return {
        "path": str(path),
        "block_count": len(blocks),
        "standalone_weak_count": len(standalone_weak),
        "false_attribution_count": len(false_attribution_rows),
    }


def apply_rebuild(db) -> dict:
    weak_rows = (
        db.query(FactExclusiveUseRight)
        .filter(FactExclusiveUseRight.event_status.in_(["active", "provisional", "review"]))
        .all()
    )
    rejected = 0
    replaced = 0
    reviewed_false_attribution = 0
    for row in weak_rows:
        validation = _validate_row(row)
        if validation.subject_name and normalize_search_key(validation.subject_name) != normalize_search_key(row.subject_name):
            old_subject = row.subject_name
            row.subject_name = validation.subject_name
            row.subject_core_key = normalize_search_key(validation.subject_name)
            aliases = set(_json_load(row.alias_names_json))
            aliases.add(old_subject)
            aliases.add(validation.subject_name)
            row.alias_names_json = _json_list(sorted(alias for alias in aliases if alias))
            row.needs_review = bool(validation.needs_review)
            if row.company_id and not row.needs_review:
                row.event_status = "active"
            replaced += 1
            continue
        if is_generic_or_weak_subject(row.subject_name) or has_bad_subject_tail(row.subject_name):
            row.event_status = "rejected"
            row.needs_review = True
            rejected += 1
            continue
        if validation.needs_review and validation.reason.startswith("weak_reference_type_conflict"):
            row.event_status = "review"
            row.needs_review = True
            reviewed_false_attribution += 1
    result = ExclusiveRightConsolidationService().run(db, mode="rule_only_apply")
    db.commit()
    result["rejected_weak_subject_count"] = rejected
    result["replaced_bad_subject_count"] = replaced
    result["reviewed_false_attribution_count"] = reviewed_false_attribution
    return result


def _validate_row(row: FactExclusiveUseRight):
    window_text = " ".join(
        part
        for part in [
            row.evidence_text or "",
            row.evidence_summary or "",
            row.feature_summary or "",
            row.primary_article_title or "",
            " ".join(_json_load(row.alias_names_json)),
        ]
        if part
    )
    validation = validate_exclusive_subject_before_save(
        row.subject_name,
        evidence_text=row.evidence_text,
        window_text=window_text,
        article_title=row.primary_article_title,
    )
    if validation.subject_name:
        return validation
    resolved = resolve_subject_reference(
        row.subject_name,
        window_text,
        row.evidence_text,
        article_title=row.primary_article_title,
    )
    if resolved:
        return type(validation)(resolved, "resolved", False, "rebuild_reference_resolved", row.subject_name)
    return validation


def _json_load(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        import json

        payload = json.loads(value)
        return [str(item) for item in payload if item]
    except Exception:
        return []


def _json_list(values: list[str]) -> str:
    import json

    return json.dumps(values, ensure_ascii=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild exclusive-use-right canonical events without LLM calls.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Write rebuild plan CSV only.")
    mode.add_argument("--apply", action="store_true", help="Apply deterministic merge/reject decisions.")
    args = parser.parse_args()

    init_db(engine)
    with SessionLocal() as db:
        plan = write_plan(db)
        if args.dry_run:
            print(f"dry-run plan written: {plan}")
            return
        result = apply_rebuild(db)
        print(f"applied rebuild: {result}; plan={plan}")


if __name__ == "__main__":
    main()
