from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.database import SessionLocal
from app.normalizers.korean_description_normalizer import is_english_like, koreanize_description_text


@dataclass(frozen=True)
class TextColumn:
    table: str
    id_column: str
    column: str
    field_name: str


TARGET_COLUMNS = (
    TextColumn("dim_product", "product_id", "product_category_summary", "product_category_summary"),
    TextColumn("dim_product", "product_id", "partner_context_summary", "partner_context_summary"),
    TextColumn("fact_product_narrative_insight", "insight_id", "feature_summary", "feature_summary"),
    TextColumn("fact_product_narrative_insight", "insight_id", "product_development_summary", "product_development_summary"),
    TextColumn("fact_product_narrative_insight", "insight_id", "marketing_summary", "marketing_summary"),
    TextColumn("fact_product_narrative_insight", "insight_id", "target_customer_summary", "target_customer_summary"),
    TextColumn("fact_product_narrative_insight", "insight_id", "underwriting_summary", "underwriting_summary"),
    TextColumn("fact_product_narrative_insight", "insight_id", "channel_summary", "channel_summary"),
    TextColumn("fact_product_narrative_insight", "insight_id", "coverage_summary", "coverage_summary"),
    TextColumn("fact_product_narrative_insight", "insight_id", "sales_summary", "sales_summary"),
    TextColumn("fact_product_narrative_insight", "insight_id", "differentiation_summary", "differentiation_summary"),
    TextColumn("fact_product_narrative_insight", "insight_id", "risk_note_summary", "risk_note_summary"),
    TextColumn("fact_product_narrative_insight", "insight_id", "missing_info_summary", "missing_info_summary"),
    TextColumn("fact_product_major_coverage", "coverage_id", "amount_basis", "amount_basis"),
    TextColumn("fact_product_major_coverage", "coverage_id", "condition_text", "condition_text"),
    TextColumn("fact_product_major_coverage", "coverage_id", "limit_text", "limit_text"),
    TextColumn("fact_product_major_coverage", "coverage_id", "coverage_summary", "coverage_summary"),
    TextColumn("fact_exclusive_use_right", "exclusive_right_id", "feature_summary", "feature_summary"),
    TextColumn("fact_exclusive_use_right", "exclusive_right_id", "evidence_summary", "evidence_summary"),
    TextColumn("fact_exclusive_use_right_observation", "observation_id", "feature_summary", "feature_summary"),
)


def run(*, apply: bool = False, limit: int | None = None, source_db: str | None = None) -> dict[str, Any]:
    summary: dict[str, Any] = {"apply": apply, "columns": [], "updated_total": 0, "english_before_total": 0}
    source_conn: sqlite3.Connection | None = None
    if source_db:
        source_conn = sqlite3.connect(source_db)
        source_conn.row_factory = sqlite3.Row
    with SessionLocal() as db:
        for target in TARGET_COLUMNS:
            if source_conn:
                source_rows = source_conn.execute(
                    f"""
                    SELECT {target.id_column} AS id, {target.column} AS value
                    FROM {target.table}
                    WHERE {target.column} IS NOT NULL AND TRIM({target.column}) <> ''
                    ORDER BY {target.id_column}
                    """
                ).fetchall()
                current_rows = {
                    row["id"]: row["value"]
                    for row in db.execute(
                        text(
                            f"""
                            SELECT {target.id_column} AS id, {target.column} AS value
                            FROM {target.table}
                            """
                        )
                    ).mappings().all()
                }
                rows = [{"id": row["id"], "value": row["value"], "current_value": current_rows.get(row["id"])} for row in source_rows]
            else:
                rows = db.execute(
                    text(
                        f"""
                        SELECT {target.id_column} AS id, {target.column} AS value
                        FROM {target.table}
                        WHERE {target.column} IS NOT NULL AND TRIM({target.column}) <> ''
                        ORDER BY {target.id_column}
                        """
                    )
                ).mappings().all()
            updates: list[dict[str, Any]] = []
            english_before = 0
            for row in rows:
                current = str(row["value"] or "")
                if not is_english_like(current) and koreanize_description_text(current, target.field_name) == current:
                    continue
                english_before += 1
                next_value = koreanize_description_text(current, target.field_name)
                compare_value = str(row.get("current_value") if isinstance(row, dict) else row.get("current_value") or current)
                if next_value and next_value != compare_value:
                    updates.append({"id": row["id"], "value": next_value})
                    if limit is not None and len(updates) >= limit:
                        break
            if apply and updates:
                db.execute(
                    text(
                        f"""
                        UPDATE {target.table}
                        SET {target.column} = :value
                        WHERE {target.id_column} = :id
                        """
                    ),
                    updates,
                )
            summary["columns"].append(
                {
                    "table": target.table,
                    "column": target.column,
                    "english_before": english_before,
                    "updated": len(updates),
                    "examples": updates[:3],
                }
            )
            summary["updated_total"] += len(updates)
            summary["english_before_total"] += english_before
        if apply:
            db.commit()
    if apply:
        with SessionLocal() as db:
            db.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
    if source_conn:
        source_conn.close()
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Koreanize user-facing description fields without external APIs.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--source-db")
    args = parser.parse_args()
    print(json.dumps(run(apply=args.apply, limit=args.limit, source_db=args.source_db), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
