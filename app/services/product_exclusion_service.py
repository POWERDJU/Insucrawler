from __future__ import annotations

import re
from typing import Any


EXCLUDED_PRODUCT_NAME_PATTERNS = ("실손의료",)


def normalize_exclusion_text(value: str | None) -> str:
    return re.sub(r"[\s\-/_.()\\[\\]{}'\"`]+", "", str(value or "").lower())


def product_policy_exclusion_sql(
    product_alias: str = "s",
    *,
    param_prefix: str = "policy_excluded",
) -> tuple[str, dict[str, Any]]:
    params: dict[str, Any] = {}
    clauses: list[str] = []
    fields = [
        f"{product_alias}.normalized_product_name",
        f"{product_alias}.raw_product_name",
        f"{product_alias}.product_search_key",
        f"{product_alias}.product_core_key",
    ]
    for idx, pattern in enumerate(EXCLUDED_PRODUCT_NAME_PATTERNS):
        key = f"{param_prefix}_{idx}"
        params[key] = f"%{normalize_exclusion_text(pattern)}%"
        field_clauses = [f"{_sql_compact(field)} LIKE :{key}" for field in fields]
        field_clauses.extend(
            [
                f"""
                EXISTS (
                    SELECT 1
                    FROM dim_product_alias excluded_alias
                    WHERE excluded_alias.product_id = {product_alias}.product_id
                      AND (
                        {_sql_compact("excluded_alias.raw_product_name")} LIKE :{key}
                        OR {_sql_compact("excluded_alias.normalized_product_name_candidate")} LIKE :{key}
                        OR {_sql_compact("excluded_alias.product_core_key")} LIKE :{key}
                      )
                )
                """,
                f"""
                EXISTS (
                    SELECT 1
                    FROM fact_product_observation excluded_observation
                    WHERE excluded_observation.product_id = {product_alias}.product_id
                      AND (
                        {_sql_compact("excluded_observation.raw_product_name")} LIKE :{key}
                        OR {_sql_compact("excluded_observation.normalized_product_name_candidate")} LIKE :{key}
                        OR {_sql_compact("excluded_observation.product_core_key")} LIKE :{key}
                      )
                )
                """,
            ]
        )
        clauses.append("(" + " OR ".join(field_clauses) + ")")
    if not clauses:
        return "", {}
    return " AND NOT (" + " OR ".join(clauses) + ")", params


def _sql_compact(expr: str) -> str:
    return (
        "REPLACE(REPLACE(REPLACE(REPLACE(REPLACE("
        f"LOWER(COALESCE({expr}, '')), ' ', ''), '-', ''), '/', ''), '.', ''), '_', '')"
    )
