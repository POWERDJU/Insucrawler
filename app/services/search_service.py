from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.normalizers.company_normalizer import CompanyNormalizer
from app.services.company_service import CHANGED_STATUSES, FOREIGN_BRANCH_ROLES, REINSURER_ROLES
from app.services.product_exclusion_service import product_policy_exclusion_sql
from app.utils.release_display import display_release_year_month
from app.utils.text import normalize_search_key


class SearchService:
    def search_products(
        self,
        db: Session,
        q: str | None = None,
        company_name: str | None = None,
        insurance_type: str | None = None,
        product_type_code: str | None = None,
        release_year_month_from: str | None = None,
        release_year_month_to: str | None = None,
        include_secondary_types: bool = False,
        min_confidence: float | None = None,
        include_review: bool = False,
        company_role: str | None = None,
        status_2024_2026: str | None = None,
        include_in_product_news_default: str | None = None,
        include_reinsurers: bool = False,
        include_foreign_branches: bool = False,
        include_inactive_or_changed_companies: bool = True,
        include_excluded_policy_products: bool = False,
    ) -> list[dict]:
        sql = """
            SELECT s.*,
                   (SELECT COUNT(*) FROM fact_product_major_coverage c WHERE c.product_id = s.product_id) AS major_coverage_count,
                   (
                     SELECT COUNT(DISTINCT pa.article_id)
                     FROM fact_product_article pa
                     JOIN fact_article ar_count ON ar_count.article_id = pa.article_id
                     WHERE pa.product_id = s.product_id
                       AND COALESCE(ar_count.multi_company_article_yn, 0) = 0
                       AND COALESCE(pa.extraction_status, 'saved') NOT IN ('excluded_multi_company', 'excluded_article_eligibility')
                   ) AS article_count
            FROM vw_product_search s
            WHERE 1=1
              AND TRIM(COALESCE(s.normalized_product_name, '')) NOT LIKE :special_clause_suffix
              AND TRIM(COALESCE(s.raw_product_name, '')) NOT LIKE :special_clause_suffix
              AND TRIM(COALESCE(s.normalized_product_name, '')) NOT LIKE :rider_suffix
              AND TRIM(COALESCE(s.raw_product_name, '')) NOT LIKE :rider_suffix
        """
        params: dict[str, object] = {"special_clause_suffix": "%특별약관", "rider_suffix": "%특약"}
        if not include_excluded_policy_products:
            exclusion_sql, exclusion_params = product_policy_exclusion_sql("s", param_prefix="search_excluded")
            sql += exclusion_sql
            params.update(exclusion_params)
        if q:
            normalized_company = CompanyNormalizer().normalize(q)
            sql += " AND (s.product_search_key LIKE :q OR s.normalized_product_name LIKE :raw_q OR s.raw_product_name LIKE :raw_q"
            params["q"] = f"%{normalize_search_key(q)}%"
            params["raw_q"] = f"%{q}%"
            if normalized_company and normalized_company.match_type != "unknown":
                sql += " OR s.company_name = :normalized_query_company"
                params["normalized_query_company"] = normalized_company.company_name_normalized
            sql += ")"
        if company_name:
            sql += " AND s.company_name LIKE :company_name"
            params["company_name"] = f"%{company_name}%"
        if insurance_type:
            sql += " AND s.insurance_type = :insurance_type"
            params["insurance_type"] = insurance_type
        if release_year_month_from:
            sql += " AND s.release_year_month >= :release_from"
            params["release_from"] = release_year_month_from
        if release_year_month_to:
            sql += " AND s.release_year_month <= :release_to"
            params["release_to"] = release_year_month_to
        if min_confidence is not None:
            sql += " AND s.confidence_total >= :min_confidence"
            params["min_confidence"] = min_confidence
        if not include_review:
            sql += " AND s.needs_review = 0"
        sql += """
            AND (
                EXISTS (
                    SELECT 1
                    FROM fact_product_article clean_pa
                    JOIN fact_article clean_a ON clean_a.article_id = clean_pa.article_id
                    WHERE clean_pa.product_id = s.product_id
                      AND COALESCE(clean_a.multi_company_article_yn, 0) = 0
                      AND COALESCE(clean_pa.extraction_status, 'saved') NOT IN ('excluded_multi_company', 'excluded_article_eligibility')
                )
                OR NOT EXISTS (
                    SELECT 1 FROM fact_product_article any_pa WHERE any_pa.product_id = s.product_id
                )
            )
        """
        if include_in_product_news_default:
            sql += " AND s.include_in_product_news_default = :include_in_product_news_default"
            params["include_in_product_news_default"] = include_in_product_news_default
        else:
            include_roles = []
            if include_reinsurers:
                include_roles.extend(sorted(REINSURER_ROLES))
            if include_foreign_branches:
                include_roles.extend(sorted(FOREIGN_BRANCH_ROLES))
            if include_roles:
                placeholders = []
                for idx, role in enumerate(include_roles):
                    key = f"include_role_{idx}"
                    placeholders.append(f":{key}")
                    params[key] = role
                sql += f" AND (s.include_in_product_news_default = 'Y' OR s.company_role IN ({','.join(placeholders)}))"
            else:
                sql += " AND s.include_in_product_news_default = 'Y'"
        if company_role:
            sql += " AND s.company_role = :company_role"
            params["company_role"] = company_role
        if status_2024_2026:
            sql += " AND s.status_2024_2026 = :status_2024_2026"
            params["status_2024_2026"] = status_2024_2026
        if not include_inactive_or_changed_companies:
            placeholders = []
            for idx, status in enumerate(sorted(CHANGED_STATUSES)):
                key = f"changed_{idx}"
                placeholders.append(f":{key}")
                params[key] = status
            sql += f" AND COALESCE(s.status_2024_2026, 'unknown') NOT IN ({','.join(placeholders)})"
        if product_type_code:
            sql += " AND s.primary_product_type_code = :product_type_code"
            params["product_type_code"] = product_type_code
        sql += " ORDER BY s.confidence_total DESC, s.product_id DESC"
        rows = db.execute(text(sql), params).mappings().all()
        results: list[dict] = []
        for row in rows:
            item = dict(row)
            item["needs_review"] = bool(item["needs_review"])
            item["release_year_month"] = display_release_year_month(item.get("release_year_month"))
            results.append(item)
        return results
