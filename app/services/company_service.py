from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.normalizers.company_normalizer import CompanyNormalizer


REINSURER_ROLES = {"reinsurer"}
FOREIGN_BRANCH_ROLES = {"foreign_branch", "reinsurer_or_foreign_branch"}
CHANGED_STATUSES = {"merged", "bridge", "transferred_to_bridge", "exiting", "renamed"}
SHORT_TERM_ROLES = {"short_term_pet_insurer"}


def company_display_label(row: dict[str, Any]) -> str:
    name = row.get("company_name_normalized") or row.get("company_name") or ""
    predecessor = row.get("predecessor_company")
    successor = row.get("successor_company")
    status = row.get("status_2024_2026")
    role = row.get("company_role")
    if name == "예별손해보험":
        return f"{name} (MG손보 계약관리)"
    if predecessor:
        return f"{name} (구 {predecessor})"
    if successor and status == "merged":
        return f"{name} ({successor} 합병)"
    if role == "short_term_pet_insurer" or status == "new":
        return f"{name} (신규)"
    return name


def company_display_sort_key(company: dict[str, Any]) -> tuple[Any, ...]:
    insurance_type_order = {
        "생명보험": 10,
        "손해보험": 20,
        "unknown": 99,
        None: 99,
    }
    return (
        insurance_type_order.get(company.get("insurance_type"), 99),
        company.get("display_order_established") if company.get("display_order_established") is not None else 999999,
        company.get("establishment_year") if company.get("establishment_year") is not None else 9999,
        company.get("establishment_month") if company.get("establishment_month") is not None else 99,
        company.get("establishment_day") if company.get("establishment_day") is not None else 99,
        company.get("sort_tie_breaker") if company.get("sort_tie_breaker") is not None else 999999,
        company.get("company_name_normalized") or "",
    )


def sort_companies_for_display(companies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(companies, key=company_display_sort_key)


class CompanyService:
    def list_companies(
        self,
        db: Session,
        insurance_type: str | None = None,
        company_role: str | None = None,
        status_2024_2026: str | None = None,
        include_product_news_default_only: bool = True,
        include_reinsurers: bool = False,
        include_foreign_branches: bool = False,
        include_changed_companies: bool = True,
        include_short_term_insurers: bool = True,
        include_establishment_info: bool = True,
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT company_id, company_name_normalized, company_name_raw, alias,
                   insurance_type, insurance_type_default, company_role, status_2024_2026,
                   include_in_product_news_default, active_yn, valid_from, valid_to,
                   predecessor_company, successor_company,
                   establishment_year, establishment_month, establishment_day,
                   establishment_sort_date, establishment_basis, oldest_predecessor_year,
                   current_brand_year, display_order_established, sort_tie_breaker,
                   establishment_source_note, notes
            FROM dim_company
            WHERE active_yn = 'Y'
        """
        params: dict[str, Any] = {}
        if insurance_type:
            sql += " AND insurance_type = :insurance_type"
            params["insurance_type"] = insurance_type
        if company_role:
            sql += " AND company_role = :company_role"
            params["company_role"] = company_role
        if status_2024_2026:
            sql += " AND status_2024_2026 = :status_2024_2026"
            params["status_2024_2026"] = status_2024_2026
        if include_product_news_default_only:
            extra_roles: list[str] = []
            if include_reinsurers:
                extra_roles.extend(sorted(REINSURER_ROLES))
            if include_foreign_branches:
                extra_roles.extend(sorted(FOREIGN_BRANCH_ROLES))
            if extra_roles:
                placeholders = []
                for idx, role in enumerate(extra_roles):
                    key = f"extra_role_{idx}"
                    placeholders.append(f":{key}")
                    params[key] = role
                sql += f" AND (include_in_product_news_default = 'Y' OR company_role IN ({','.join(placeholders)}))"
            else:
                sql += " AND include_in_product_news_default = 'Y'"
        if not include_changed_companies:
            placeholders = []
            for idx, status in enumerate(sorted(CHANGED_STATUSES)):
                key = f"changed_{idx}"
                placeholders.append(f":{key}")
                params[key] = status
            sql += f" AND COALESCE(status_2024_2026, 'unknown') NOT IN ({','.join(placeholders)})"
        if not include_short_term_insurers:
            sql += " AND COALESCE(company_role, '') != 'short_term_pet_insurer' AND COALESCE(status_2024_2026, '') != 'new'"
        rows = [dict(row) for row in db.execute(text(sql), params).mappings().all()]
        for row in rows:
            row["display_label"] = company_display_label(row)
        rows = sort_companies_for_display(rows)
        if not include_establishment_info:
            for row in rows:
                for key in [
                    "establishment_year",
                    "establishment_month",
                    "establishment_day",
                    "establishment_sort_date",
                    "establishment_basis",
                    "oldest_predecessor_year",
                    "current_brand_year",
                    "display_order_established",
                    "sort_tie_breaker",
                    "establishment_source_note",
                ]:
                    row.pop(key, None)
        return rows

    def normalize_text(self, text_value: str) -> dict[str, Any]:
        matches = CompanyNormalizer().detect_all(text_value)
        return {
            "matches": [
                {
                    "company_name_raw": item.company_name_raw,
                    "company_name_normalized": item.company_name_normalized,
                    "insurance_type": item.insurance_type,
                    "company_role": item.company_role,
                    "status_2024_2026": item.status_2024_2026,
                    "match_type": item.match_type,
                    "confidence": item.confidence,
                }
                for item in matches
            ]
        }
