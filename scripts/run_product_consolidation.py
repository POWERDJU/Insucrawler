from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import SessionLocal, engine
from app.db.migrations import init_db
from app.services.product_consolidation_service import ProductConsolidationService


def main() -> None:
    parser = argparse.ArgumentParser(description="Run product entity resolution consolidation.")
    parser.add_argument("--mode", choices=["dry-run", "rule-only-apply", "apply-with-llm"], default="dry-run")
    parser.add_argument("--target", choices=["new_since_last_job", "all_provisional", "all", "selected"], default="all_provisional")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--all-pages", action="store_true", help="Process all active/provisional candidates instead of only the newest limit.")
    parser.add_argument("--include-family-signature", action="store_true", help="Include product family signature diagnostics in dry-run CSV.")
    parser.add_argument("--export-csv", default="data/exports/product_consolidation_blocks.csv")
    parser.add_argument("--use-llm-for-gray-blocks", action="store_true")
    args = parser.parse_args()

    mode = {
        "dry-run": "dry_run",
        "rule-only-apply": "rule_only_apply",
        "apply-with-llm": "apply_with_llm_gray_blocks",
    }[args.mode]
    init_db(engine)
    limit = 0 if args.all_pages else args.limit
    with SessionLocal() as db:
        result = ProductConsolidationService().run(
            db,
            mode=mode,
            target=args.target,
            limit=limit,
            trigger_type="script",
            use_llm_for_gray_blocks=args.use_llm_for_gray_blocks,
        )
    if args.all_pages or mode == "dry_run":
        _export_blocks_csv(result, Path(args.export_csv), include_family_signature=args.include_family_signature)
    print(json.dumps(result, ensure_ascii=False, indent=2))


def _export_blocks_csv(result: dict, path: Path, *, include_family_signature: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for block in result.get("blocks") or []:
        reason_payload = {}
        try:
            reason_payload = json.loads(block.get("block_reason") or "{}")
        except json.JSONDecodeError:
            reason_payload = {"reason": block.get("block_reason")}
        candidate_names = reason_payload.get("candidate_names") or []
        partner_candidates = reason_payload.get("partner_candidates") or []
        context_scores = reason_payload.get("context_scores") or []
        family_signatures = reason_payload.get("family_signatures") or []
        family_tokens = reason_payload.get("family_tokens") or []
        rows.append(
            {
                "block_id": block.get("block_id"),
                "block_key": block.get("block_key"),
                "candidate_product_ids": ", ".join(str(item) for item in block.get("candidate_product_ids") or []),
                "candidate_names": " | ".join(str(item) for item in candidate_names),
                "company_names": str(block.get("company_id") or ""),
                "partner_candidates": " | ".join(str(item) for item in partner_candidates),
                "product_type_codes": ", ".join(str(item) for item in block.get("product_type_codes") or []),
                "release_months": block.get("release_month_window") or "",
                "context_similarity_summary": json.dumps(context_scores[:5], ensure_ascii=False),
                "suggested_canonical_name": candidate_names[0] if candidate_names else "",
                "suggested_action": block.get("status") or "",
                "reason": reason_payload.get("reason") or block.get("block_reason") or "",
                "family_signature": " | ".join(str(item) for item in family_signatures),
                "family_tokens": " | ".join(str(item) for item in family_tokens),
                "same_company_family_reason": _family_reason(reason_payload),
                "canonical_candidate": candidate_names[0] if candidate_names else "",
                "duplicate_product_ids": ", ".join(str(item) for item in (block.get("candidate_product_ids") or [])[1:]),
                "merge_confidence": _max_context_score(context_scores),
            }
        )
    fields = [
        "block_id",
        "block_key",
        "candidate_product_ids",
        "candidate_names",
        "company_names",
        "partner_candidates",
        "product_type_codes",
        "release_months",
        "context_similarity_summary",
        "suggested_canonical_name",
        "suggested_action",
        "reason",
    ]
    diagnostic_fields = [
        "family_signature",
        "family_tokens",
        "same_company_family_reason",
        "canonical_candidate",
        "duplicate_product_ids",
        "merge_confidence",
    ]
    if include_family_signature or any(any(row.get(field) for field in diagnostic_fields) for row in rows):
        fields.extend(
            field
            for field in diagnostic_fields
            if field not in fields
        )
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Exported {len(rows)} consolidation blocks to {path}")


def _family_reason(reason_payload: dict) -> str:
    signatures = reason_payload.get("family_signatures") or []
    tokens = reason_payload.get("family_tokens") or []
    if signatures:
        return f"family_signature={';'.join(str(item) for item in signatures)}"
    if tokens:
        return f"family_tokens={';'.join(str(item) for item in tokens[:10])}"
    return ""


def _max_context_score(context_scores: list[dict]) -> str:
    values = []
    for item in context_scores or []:
        try:
            values.append(float(item.get("context_similarity") or 0))
        except (TypeError, ValueError):
            continue
    return f"{max(values):.4f}" if values else ""


if __name__ == "__main__":
    main()
