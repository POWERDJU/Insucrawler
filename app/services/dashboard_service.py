from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from io import BytesIO
import re
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.normalizers.korean_description_normalizer import koreanize_description_text
from app.services.company_service import CHANGED_STATUSES, CompanyService, FOREIGN_BRANCH_ROLES, REINSURER_ROLES
from app.services.coverage_dedupe_service import dedupe_major_coverages
from app.services.pivot_service import PivotService
from app.services.product_exclusion_service import product_policy_exclusion_sql
from app.utils.release_display import display_release_year_month, visible_release_years
from app.db.models import DimCompany, DimProduct, FactArticle, FactContentScreening, FactCrawlJob, FactExclusiveUseRight
from app.services.product_duplicate_guard_service import ProductDuplicateGuardService


PIVOT_PRESETS = [
    {"code": "industry_company", "name": "업종 × 회사별"},
    {"code": "company_product_type", "name": "회사 × 상품군별"},
    {"code": "month_product_type", "name": "출시월 × 상품군별"},
    {"code": "product_type_coverage", "name": "상품군 × 주요보장별"},
    {"code": "product_list", "name": "상품별 목록"},
    {"code": "custom", "name": "사용자 지정 다중피벗"},
]


DIMENSIONS = {
    "insurance_type": "insurance_type",
    "company_name": "company_name",
    "product_type_name": "product_type_name",
    "release_year_month": "release_year_month",
    "product_name": "product_name",
    "risk_area": "risk_area",
    "benefit_type": "benefit_type",
    "company_role": "company_role",
    "status_2024_2026": "status_2024_2026",
}


METRICS = {
    "product_count": {"name": "product_count", "agg": "count_distinct", "field": "product_id"},
    "article_count": {"name": "article_count", "agg": "sum", "field": "article_count"},
    "coverage_count": {"name": "coverage_count", "agg": "count_distinct", "field": "coverage_id"},
    "max_amount_max": {"name": "max_amount_max", "agg": "max", "field": "max_amount_krw"},
    "sales_count_sum": {"name": "sales_count_sum", "agg": "sum", "field": "metric_value", "filter_metric_names": ["판매건수"]},
    "monthly_premium_sum": {"name": "monthly_premium_sum", "agg": "sum", "field": "metric_value", "filter_metric_names": ["월초보험료", "보장월초보험료"]},
}


COMPARISON_EXPORT_EXCLUDED_COLUMNS = {
    "canonical_product_id",
    "product_status",
    "상품명 alias 목록",
    "상품통합 상태",
    "통합근거 요약",
    "partner_company",
    "source_article_urls",
    "원문 상품명",
    "원문 회사명",
    "최초 확인월",
    "고지유형",
    "납입기간",
    "보험기간",
    "확인 필요 정보",
    "미확인 필드",
    "주요보장2 최대보장금액",
}


class DashboardService:
    def options(
        self,
        db: Session,
        include_reinsurers: bool = False,
        include_foreign_branches: bool = False,
        include_changed_companies: bool = True,
        include_short_term_insurers: bool = True,
    ) -> dict[str, Any]:
        years = ["전체"] + visible_release_years()
        companies = CompanyService().list_companies(
            db,
            include_product_news_default_only=True,
            include_reinsurers=include_reinsurers,
            include_foreign_branches=include_foreign_branches,
            include_changed_companies=include_changed_companies,
            include_short_term_insurers=include_short_term_insurers,
        )
        company_options = [
            {
                "company_id": row["company_id"],
                "company_name": row["company_name_normalized"],
                "company_name_normalized": row["company_name_normalized"],
                "insurance_type": row.get("insurance_type"),
                "company_role": row.get("company_role"),
                "status_2024_2026": row.get("status_2024_2026"),
                "include_in_product_news_default": row.get("include_in_product_news_default"),
                "display_label": row.get("display_label"),
                "establishment_year": row.get("establishment_year"),
                "establishment_sort_date": row.get("establishment_sort_date"),
                "display_order_established": row.get("display_order_established"),
                "establishment_source_note": row.get("establishment_source_note"),
            }
            for row in companies
        ]
        product_types = [
            {"code": row["product_type_code"], "name": row["product_type_name_ko"]}
            for row in db.execute(
                text(
                    """
                    SELECT product_type_code, product_type_name_ko
                    FROM dim_product_type
                    WHERE active_yn = 'Y'
                    ORDER BY sort_order
                    """
                )
            ).mappings().all()
        ]
        return {
            "years": years,
            "months": ["전체"] + [f"{month:02d}" for month in range(1, 13)],
            "insurance_types": ["전체", "생명보험", "손해보험", "unknown"],
            "companies": company_options,
            "product_types": product_types,
            "pivot_presets": PIVOT_PRESETS,
        }

    def demo_status(self, db: Session) -> dict[str, Any]:
        product_count = db.execute(text("SELECT COUNT(*) FROM dim_product WHERE LOWER(COALESCE(product_status, 'active')) = 'active'")).scalar_one()
        article_count = db.execute(text("SELECT COUNT(*) FROM fact_article")).scalar_one()
        return {"has_products": product_count > 0, "product_count": product_count, "article_count": article_count}

    def data_status(self, db: Session) -> dict[str, Any]:
        product_count = db.execute(text("SELECT COUNT(*) FROM dim_product WHERE LOWER(COALESCE(product_status, 'active')) = 'active'")).scalar_one()
        article_count = db.execute(text("SELECT COUNT(*) FROM fact_article")).scalar_one()
        exclusive_right_count = db.query(FactExclusiveUseRight).filter(FactExclusiveUseRight.event_status != "merged").count()
        recent_exclusive_right_count_12m = db.query(FactExclusiveUseRight).filter(
            FactExclusiveUseRight.event_status != "merged",
            FactExclusiveUseRight.acquired_year_month >= (date.today() - timedelta(days=366)).strftime("%Y-%m"),
        ).count()
        pending_exclusive_right_extraction_count = db.query(FactContentScreening).filter(
            FactContentScreening.exclusive_right_candidate_yn.is_(True)
        ).count()
        last_exclusive_month = db.query(FactExclusiveUseRight.acquired_year_month).filter(
            FactExclusiveUseRight.event_status != "merged",
            FactExclusiveUseRight.acquired_year_month.isnot(None),
        ).order_by(FactExclusiveUseRight.acquired_year_month.desc()).limit(1).scalar()
        pending_extraction_count = db.query(FactArticle).filter(FactArticle.extraction_status == "pending").count()
        last_crawl = db.query(FactCrawlJob).order_by(FactCrawlJob.started_at.desc().nullslast(), FactCrawlJob.created_at.desc()).first()
        last_success = db.query(FactCrawlJob).filter(FactCrawlJob.status == "completed").order_by(FactCrawlJob.finished_at.desc().nullslast(), FactCrawlJob.created_at.desc()).first()
        last_failed = db.query(FactCrawlJob).filter(FactCrawlJob.status == "failed").order_by(FactCrawlJob.finished_at.desc().nullslast(), FactCrawlJob.created_at.desc()).first()
        return {
            "article_count": article_count,
            "product_count": product_count,
            "last_crawl_started_at": last_crawl.started_at if last_crawl else None,
            "last_crawl_finished_at": last_crawl.finished_at if last_crawl else None,
            "last_successful_job_name": last_success.job_name if last_success else None,
            "last_failed_job_name": last_failed.job_name if last_failed else None,
            "pending_extraction_count": pending_extraction_count,
            "exclusive_right_count": exclusive_right_count,
            "recent_exclusive_right_count_12m": recent_exclusive_right_count_12m,
            "pending_exclusive_right_extraction_count": pending_exclusive_right_extraction_count,
            "last_exclusive_right_acquired_year_month": last_exclusive_month,
        }

    def query(self, db: Session, request: dict[str, Any]) -> dict[str, Any]:
        pivot_spec = self._pivot_spec(request)
        filters = self._pivot_filters(db, request)
        classification_mode = "primary_only"
        pivot_result = PivotService().run_pivot(
            db,
            base=pivot_spec["base"],
            classification_mode=classification_mode,
            rows=pivot_spec["rows"],
            columns=pivot_spec["columns"],
            filters=filters,
            metrics=pivot_spec["metrics"],
            include_review=bool(request.get("include_review", False)),
            min_confidence=float(request.get("min_confidence") or 0),
        )
        products = self._products(db, request)
        summary = self._summary(db, products)
        return {"summary": summary, "pivot_result": pivot_result, "products": products}

    def export_comparison_workbook(self, db: Session, request: dict[str, Any]) -> BytesIO:
        products = [
            product
            for product in self._products(db, request)
            if str(product.get("product_status") or "active").lower() == "active"
        ]
        rows = self._comparison_rows(db, products)
        columns = self._comparison_columns(rows)
        duplicate_warning_rows = self._duplicate_warning_rows(db, products)
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df = pd.DataFrame(rows, columns=columns)
            df.to_excel(writer, index=False, sheet_name="상품 비교표")
            filter_df = pd.DataFrame(self._export_filter_rows(request))
            filter_df.to_excel(writer, index=False, sheet_name="적용 필터")
            if duplicate_warning_rows:
                pd.DataFrame(duplicate_warning_rows).to_excel(writer, index=False, sheet_name="duplicate_warnings")
            worksheet = writer.sheets["상품 비교표"]
            worksheet.freeze_panes = "A2"
            for column_cells in worksheet.columns:
                header = str(column_cells[0].value or "")
                if "요약" in header or "주요보장" in header or "관련기사" in header:
                    width = 42
                elif header in {"상품명", "원문 상품명"}:
                    width = 38
                else:
                    width = min(max(len(header) + 4, 12), 24)
                worksheet.column_dimensions[column_cells[0].column_letter].width = width
        output.seek(0)
        return output

    def _pivot_filters(self, db: Session, request: dict[str, Any]) -> dict[str, list[Any]]:
        filters: dict[str, list[Any]] = {}
        if request.get("insurance_type") and request["insurance_type"] != "전체":
            filters["insurance_type"] = [request["insurance_type"]]
        company_names = self._clean_filter_values(request.get("company_names"))
        product_type_codes = self._clean_filter_values(request.get("product_type_codes"))
        if company_names:
            filters["company_name"] = company_names
        if product_type_codes:
            filters["product_type_code"] = product_type_codes
        company_include_roles: list[str] = []
        if request.get("include_reinsurers"):
            company_include_roles.extend(sorted(REINSURER_ROLES))
        if request.get("include_foreign_branches"):
            company_include_roles.extend(sorted(FOREIGN_BRANCH_ROLES))
        if company_include_roles:
            filters["_company_include_roles"] = company_include_roles
        else:
            filters["include_in_product_news_default"] = ["Y"]
        if not request.get("include_changed_companies", True):
            filters["_exclude_statuses"] = sorted(CHANGED_STATUSES)
        if not request.get("include_short_term_insurers", True):
            filters["_exclude_company_roles"] = ["short_term_pet_insurer"]
            filters.setdefault("_exclude_statuses", []).append("new")
        release_months = self._release_year_month_values_for_request(db, request)
        if release_months:
            filters["release_year_month"] = release_months
        extra_filters = request.get("_extra_filters") or {}
        for key, values in extra_filters.items():
            if values:
                filters[key] = values
        return filters

    def _pivot_spec(self, request: dict[str, Any]) -> dict[str, Any]:
        preset = request.get("pivot_preset") or "custom"
        if preset == "industry_company":
            return {"base": "product", "rows": ["insurance_type"], "columns": ["company_name"], "metrics": [METRICS["product_count"]]}
        if preset == "company_product_type":
            return {"base": "product", "rows": ["company_name"], "columns": ["product_type_name"], "metrics": [METRICS["product_count"]]}
        if preset == "month_product_type":
            return {"base": "product", "rows": ["release_year_month"], "columns": ["product_type_name"], "metrics": [METRICS["product_count"]]}
        if preset == "product_type_coverage":
            return {
                "base": "coverage",
                "rows": ["product_type_name"],
                "columns": ["risk_area"],
                "metrics": [METRICS["coverage_count"], METRICS["product_count"], METRICS["max_amount_max"]],
            }
        if preset == "product_list":
            return {"base": "product", "rows": ["company_name", "normalized_product_name"], "columns": [], "metrics": [METRICS["product_count"], METRICS["article_count"]]}
        rows = [DIMENSIONS[item] for item in request.get("custom_rows", []) if item in DIMENSIONS]
        if not rows:
            rows = ["company_name", "product_type_name"]
        columns: list[str] = []
        metrics = [METRICS[item] for item in request.get("custom_metrics", []) if item in METRICS]
        base = "product"
        if any(item in rows for item in ["risk_area", "benefit_type"]) or any(metric["field"] in {"coverage_id", "max_amount_krw"} for metric in metrics):
            base = "coverage"
        if any(item in request.get("custom_metrics", []) for item in ["sales_count_sum", "monthly_premium_sum"]):
            base = "sales"
            metric_names = []
            if "sales_count_sum" in request.get("custom_metrics", []):
                metric_names.append("판매건수")
            if "monthly_premium_sum" in request.get("custom_metrics", []):
                metric_names.extend(["월초보험료", "보장월초보험료"])
            if metric_names:
                request.setdefault("_extra_filters", {})["metric_name"] = metric_names
        if not metrics:
            metrics = [METRICS["product_count"], METRICS["coverage_count"]] if base == "coverage" else [METRICS["product_count"], METRICS["article_count"]]
        return {"base": base, "rows": rows, "columns": columns, "metrics": metrics}

    def _release_year_month_values(self, db: Session, year: str, month: str) -> list[str]:
        if year == "전체" and month == "전체":
            return []
        if year != "전체" and month != "전체":
            return [f"{year}-{month}"]
        if year != "전체":
            return [f"{year}-{m:02d}" for m in range(1, 13)]
        rows = db.execute(
            text(
                """
                SELECT DISTINCT release_year_month
                FROM dim_product
                WHERE release_year_month LIKE :month_pattern
                """
            ),
            {"month_pattern": f"%-{month}"},
        ).all()
        return [row[0] for row in rows if row[0]]

    def _release_year_month_values_for_request(self, db: Session, request: dict[str, Any]) -> list[str]:
        years = sorted({str(year) for year in request.get("release_years") or [] if str(year) != "전체"})
        month = request.get("release_month", "전체")
        if years and month != "전체":
            return [f"{year}-{month}" for year in years]
        if years:
            return [f"{year}-{idx:02d}" for year in years for idx in range(1, 13)]
        return self._release_year_month_values(db, request.get("release_year", "전체"), month)

    def _products(self, db: Session, request: dict[str, Any]) -> list[dict[str, Any]]:
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
              AND LOWER(COALESCE(s.product_status, 'active')) = 'active'
              AND TRIM(COALESCE(s.normalized_product_name, '')) NOT LIKE :special_clause_suffix
              AND TRIM(COALESCE(s.raw_product_name, '')) NOT LIKE :special_clause_suffix
              AND TRIM(COALESCE(s.normalized_product_name, '')) NOT LIKE :rider_suffix
              AND TRIM(COALESCE(s.raw_product_name, '')) NOT LIKE :rider_suffix
        """
        params: dict[str, Any] = {"special_clause_suffix": "%특별약관", "rider_suffix": "%특약"}
        if not request.get("include_excluded_policy_products", False):
            exclusion_sql, exclusion_params = product_policy_exclusion_sql("s", param_prefix="dashboard_excluded")
            sql += exclusion_sql
            params.update(exclusion_params)
        if not request.get("include_review", False):
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
        min_confidence = float(request.get("min_confidence") or 0)
        sql += " AND s.confidence_total >= :min_confidence"
        params["min_confidence"] = min_confidence
        if request.get("insurance_type") and request["insurance_type"] != "전체":
            sql += " AND s.insurance_type = :insurance_type"
            params["insurance_type"] = request["insurance_type"]
        include_sql, include_params = self._company_inclusion_sql(request)
        sql += include_sql
        params.update(include_params)
        company_names = self._clean_filter_values(request.get("company_names"))
        if company_names:
            names = company_names
            placeholders = []
            for idx, value in enumerate(names):
                key = f"company_{idx}"
                placeholders.append(f":{key}")
                params[key] = value
            sql += f" AND s.company_name IN ({','.join(placeholders)})"
        release_values = self._release_year_month_values_for_request(db, request)
        if release_values:
            placeholders = []
            for idx, value in enumerate(release_values):
                key = f"release_{idx}"
                placeholders.append(f":{key}")
                params[key] = value
            sql += f" AND s.release_year_month IN ({','.join(placeholders)})"
        product_type_codes = self._clean_filter_values(request.get("product_type_codes"))
        if product_type_codes:
            placeholders = []
            for idx, value in enumerate(product_type_codes):
                key = f"type_{idx}"
                placeholders.append(f":{key}")
                params[key] = value
            sql += f" AND s.primary_product_type_code IN ({','.join(placeholders)})"
        keyword_sql, keyword_params = self._keyword_search_sql(request.get("keyword"))
        sql += keyword_sql
        params.update(keyword_params)
        sql += " ORDER BY s.release_year_month DESC, s.confidence_total DESC, s.product_id DESC"
        rows = db.execute(text(sql), params).mappings().all()
        products = []
        for row in rows:
            item = dict(row)
            item["needs_review"] = bool(item.get("needs_review"))
            item["release_year_month"] = display_release_year_month(item.get("release_year_month"))
            for field_name in ("product_summary", "feature_summary", "coverage_summary", "partner_context_summary"):
                if field_name in item:
                    item[field_name] = koreanize_description_text(item.get(field_name), field_name) or item.get(field_name)
            if request.get("keyword"):
                item["match_reason"] = "keyword"
            products.append(item)
        return products

    def _keyword_search_sql(self, keyword: str | None) -> tuple[str, dict[str, Any]]:
        raw = (keyword or "").strip()
        if not raw:
            return "", {}
        compact = self._normalize_keyword_for_search(raw)
        params: dict[str, Any] = {
            "keyword_like": f"%{raw.lower()}%",
            "keyword_compact_like": f"%{compact}%",
        }
        field_exprs = [
            "s.normalized_product_name",
            "s.raw_product_name",
            "s.product_search_key",
            "s.product_core_key",
            "s.coverage_summary",
            "s.partner_company_name",
            "s.partner_context_summary",
        ]
        clauses = [
            f"(LOWER(COALESCE({expr}, '')) LIKE :keyword_like OR {self._sql_compact(expr)} LIKE :keyword_compact_like)"
            for expr in field_exprs
        ]
        clauses.extend(
            [
                """
                EXISTS (
                    SELECT 1
                    FROM dim_product_alias a
                    WHERE a.product_id = s.product_id
                      AND (
                        LOWER(COALESCE(a.raw_product_name, '')) LIKE :keyword_like
                        OR LOWER(COALESCE(a.normalized_product_name_candidate, '')) LIKE :keyword_like
                        OR LOWER(COALESCE(a.product_core_key, '')) LIKE :keyword_compact_like
                        OR REPLACE(REPLACE(REPLACE(LOWER(COALESCE(a.raw_product_name, '')), ' ', ''), '-', ''), '/', '') LIKE :keyword_compact_like
                        OR REPLACE(REPLACE(REPLACE(LOWER(COALESCE(a.normalized_product_name_candidate, '')), ' ', ''), '-', ''), '/', '') LIKE :keyword_compact_like
                      )
                )
                """,
                """
                EXISTS (
                    SELECT 1
                    FROM fact_product_observation o
                    WHERE o.product_id = s.product_id
                      AND (
                        LOWER(COALESCE(o.raw_product_name, '')) LIKE :keyword_like
                        OR LOWER(COALESCE(o.normalized_product_name_candidate, '')) LIKE :keyword_like
                        OR LOWER(COALESCE(o.product_core_key, '')) LIKE :keyword_compact_like
                        OR LOWER(COALESCE(o.observation_context_text, '')) LIKE :keyword_like
                        OR LOWER(COALESCE(o.article_title, '')) LIKE :keyword_like
                        OR LOWER(COALESCE(o.article_description, '')) LIKE :keyword_like
                        OR REPLACE(REPLACE(REPLACE(LOWER(COALESCE(o.raw_product_name, '')), ' ', ''), '-', ''), '/', '') LIKE :keyword_compact_like
                        OR REPLACE(REPLACE(REPLACE(LOWER(COALESCE(o.normalized_product_name_candidate, '')), ' ', ''), '-', ''), '/', '') LIKE :keyword_compact_like
                      )
                )
                """,
                """
                EXISTS (
                    SELECT 1
                    FROM fact_product_narrative_insight ni
                    WHERE ni.product_id = s.product_id
                      AND (
                        LOWER(COALESCE(ni.feature_summary, '')) LIKE :keyword_like
                        OR LOWER(COALESCE(ni.product_development_summary, '')) LIKE :keyword_like
                        OR LOWER(COALESCE(ni.marketing_summary, '')) LIKE :keyword_like
                        OR LOWER(COALESCE(ni.coverage_summary, '')) LIKE :keyword_like
                        OR REPLACE(REPLACE(REPLACE(LOWER(COALESCE(ni.feature_summary, '')), ' ', ''), '-', ''), '/', '') LIKE :keyword_compact_like
                        OR REPLACE(REPLACE(REPLACE(LOWER(COALESCE(ni.coverage_summary, '')), ' ', ''), '-', ''), '/', '') LIKE :keyword_compact_like
                      )
                )
                """,
                """
                EXISTS (
                    SELECT 1
                    FROM fact_product_major_coverage cov
                    WHERE cov.product_id = s.product_id
                      AND (
                        LOWER(COALESCE(cov.coverage_name_raw, '')) LIKE :keyword_like
                        OR LOWER(COALESCE(cov.coverage_name_normalized, '')) LIKE :keyword_like
                        OR LOWER(COALESCE(cov.coverage_summary, '')) LIKE :keyword_like
                        OR REPLACE(REPLACE(REPLACE(LOWER(COALESCE(cov.coverage_name_raw, '')), ' ', ''), '-', ''), '/', '') LIKE :keyword_compact_like
                        OR REPLACE(REPLACE(REPLACE(LOWER(COALESCE(cov.coverage_summary, '')), ' ', ''), '-', ''), '/', '') LIKE :keyword_compact_like
                      )
                )
                """,
                """
                EXISTS (
                    SELECT 1
                    FROM fact_product_article pa
                    JOIN fact_article ar ON ar.article_id = pa.article_id
                    WHERE pa.product_id = s.product_id
                      AND COALESCE(ar.multi_company_article_yn, 0) = 0
                      AND COALESCE(pa.extraction_status, 'saved') NOT IN ('excluded_multi_company', 'excluded_article_eligibility')
                      AND (
                        LOWER(COALESCE(ar.title, '')) LIKE :keyword_like
                        OR LOWER(COALESCE(ar.description, '')) LIKE :keyword_like
                        OR REPLACE(REPLACE(REPLACE(LOWER(COALESCE(ar.title, '')), ' ', ''), '-', ''), '/', '') LIKE :keyword_compact_like
                        OR REPLACE(REPLACE(REPLACE(LOWER(COALESCE(ar.description, '')), ' ', ''), '-', ''), '/', '') LIKE :keyword_compact_like
                      )
                )
                """,
            ]
        )
        return " AND (" + " OR ".join(clauses) + ")", params

    @staticmethod
    def _normalize_keyword_for_search(value: str) -> str:
        return re.sub(r"[\s\-/_.()\\[\\]{}'\"`]+", "", value.lower())

    @staticmethod
    def _sql_compact(expr: str) -> str:
        return f"REPLACE(REPLACE(REPLACE(LOWER(COALESCE({expr}, '')), ' ', ''), '-', ''), '/', '')"

    @staticmethod
    def _clean_filter_values(values: Any) -> list[Any]:
        if not values:
            return []
        if not isinstance(values, (list, tuple, set)):
            values = [values]
        return [value for value in values if value not in {None, "", "__NO_SELECTION__"}]

    def _comparison_rows(self, db: Session, products: list[dict[str, Any]]) -> list[dict[str, Any]]:
        product_ids = [item["product_id"] for item in products]
        if not product_ids:
            return []
        placeholders = ",".join(f":id_{idx}" for idx in range(len(product_ids)))
        params = {f"id_{idx}": value for idx, value in enumerate(product_ids)}
        feature_rows = db.execute(
            text(
                f"""
                SELECT sf.*
                FROM fact_product_structured_feature sf
                JOIN (
                    SELECT product_id, MAX(feature_id) AS feature_id
                    FROM fact_product_structured_feature
                    WHERE product_id IN ({placeholders})
                    GROUP BY product_id
                ) latest ON latest.feature_id = sf.feature_id
                """
            ),
            params,
        ).mappings().all()
        insight_rows = db.execute(
            text(
                f"""
                SELECT ni.*
                FROM fact_product_narrative_insight ni
                JOIN (
                    SELECT ni2.product_id, MAX(ni2.insight_id) AS insight_id
                    FROM fact_product_narrative_insight ni2
                    LEFT JOIN fact_article ar ON ar.article_id = ni2.article_id
                    WHERE ni2.product_id IN ({placeholders})
                      AND COALESCE(ar.multi_company_article_yn, 0) = 0
                    GROUP BY ni2.product_id
                ) latest ON latest.insight_id = ni.insight_id
                """
            ),
            params,
        ).mappings().all()
        coverage_rows = db.execute(
            text(
                f"""
                SELECT cov.*
                FROM fact_product_major_coverage cov
                LEFT JOIN fact_article ar ON ar.article_id = cov.article_id
                WHERE product_id IN ({placeholders})
                  AND COALESCE(ar.multi_company_article_yn, 0) = 0
                ORDER BY product_id, display_order, coverage_id
                """
            ),
            params,
        ).mappings().all()
        sales_rows = db.execute(
            text(
                f"""
                SELECT sm.*
                FROM fact_sales_metric_structured sm
                LEFT JOIN fact_article ar ON ar.article_id = sm.article_id
                WHERE product_id IN ({placeholders})
                  AND COALESCE(ar.multi_company_article_yn, 0) = 0
                ORDER BY product_id, sales_metric_id
                """
            ),
            params,
        ).mappings().all()
        article_rows = db.execute(
            text(
                f"""
                SELECT pa.product_id,
                       a.title,
                       a.pub_date,
                       COALESCE(a.original_url, a.url) AS article_url,
                       pa.confidence_total,
                       pa.needs_review
                FROM fact_product_article pa
                JOIN fact_article a ON a.article_id = pa.article_id
                WHERE pa.product_id IN ({placeholders})
                  AND COALESCE(a.multi_company_article_yn, 0) = 0
                  AND COALESCE(pa.extraction_status, 'saved') NOT IN ('excluded_multi_company', 'excluded_article_eligibility')
                ORDER BY pa.product_id, a.pub_date DESC
                """
            ),
            params,
        ).mappings().all()
        alias_rows = db.execute(
            text(
                f"""
                SELECT al.product_id, al.raw_product_name, al.normalized_product_name_candidate, al.source_type, al.first_seen_at AS sort_at, al.product_alias_id AS sort_id
                FROM dim_product_alias al
                LEFT JOIN fact_article ar ON ar.article_id = al.article_id
                WHERE al.product_id IN ({placeholders})
                  AND COALESCE(ar.multi_company_article_yn, 0) = 0
                UNION ALL
                SELECT ob.product_id, ob.raw_product_name, ob.normalized_product_name_candidate, ob.candidate_type AS source_type, ob.created_at AS sort_at, ob.observation_id AS sort_id
                FROM fact_product_observation ob
                LEFT JOIN fact_article ar ON ar.article_id = ob.article_id
                WHERE ob.product_id IN ({placeholders})
                  AND COALESCE(ar.multi_company_article_yn, 0) = 0
                  AND COALESCE(ob.candidate_type, 'unknown') NOT IN ('excluded_multi_company', 'excluded_article_eligibility')
                ORDER BY product_id, sort_at, sort_id
                """
            ),
            params,
        ).mappings().all()
        merge_rows = db.execute(
            text(
                f"""
                SELECT canonical_product_id AS product_id, reason, decision_source, confidence
                FROM fact_product_merge_decision
                WHERE canonical_product_id IN ({placeholders})
                ORDER BY merge_decision_id DESC
                """
            ),
            params,
        ).mappings().all()
        partner_rows = db.execute(
            text(
                f"""
                SELECT pp.product_id, pc.partner_name_normalized, pp.partner_role
                FROM fact_product_partner pp
                JOIN dim_partner_company pc ON pc.partner_id = pp.partner_id
                WHERE pp.product_id IN ({placeholders})
                ORDER BY pp.product_id, pc.partner_name_normalized
                """
            ),
            params,
        ).mappings().all()
        feature_by_product = {row["product_id"]: dict(row) for row in feature_rows}
        insight_by_product = {row["product_id"]: dict(row) for row in insight_rows}
        coverages_by_product = {
            product_id: dedupe_major_coverages(items)[0]
            for product_id, items in self._group_by_product(coverage_rows).items()
        }
        sales_by_product = self._group_by_product(sales_rows)
        articles_by_product = self._group_by_product(article_rows)
        aliases_by_product = self._group_by_product(alias_rows)
        merges_by_product = self._group_by_product(merge_rows)
        partners_by_product = self._group_by_product(partner_rows)
        duplicate_guard = ProductDuplicateGuardService()
        rows: list[dict[str, Any]] = []
        for product in products:
            product_model = db.get(DimProduct, product["product_id"])
            feature = feature_by_product.get(product["product_id"], {})
            insight = insight_by_product.get(product["product_id"], {})
            raw_alias_names = list(
                dict.fromkeys(
                    self._excel_value(alias.get("raw_product_name"))
                    for alias in aliases_by_product.get(product["product_id"], [])
                    if self._excel_value(alias.get("raw_product_name"))
                )
            )
            alias_names = (
                duplicate_guard.compatible_alias_names(product_model, raw_alias_names, self._company_aliases(db, product_model.company_id))
                if product_model
                else raw_alias_names
            )
            merge_reasons = [
                self._compact_labeled_text(
                    [
                        ("source", item.get("decision_source")),
                        ("confidence", item.get("confidence")),
                        ("reason", item.get("reason")),
                    ],
                    separator=" / ",
                )
                for item in merges_by_product.get(product["product_id"], [])
            ]
            partner_names = list(
                dict.fromkeys(
                    self._excel_value(item.get("partner_name_normalized"))
                    for item in partners_by_product.get(product["product_id"], [])
                    if self._excel_value(item.get("partner_name_normalized"))
                )
            )
            source_urls = list(
                dict.fromkeys(
                    self._excel_value(article.get("article_url"))
                    for article in articles_by_product.get(product["product_id"], [])
                    if self._excel_value(article.get("article_url"))
                )
            )
            row = {
                "상품 ID": product.get("product_id"),
                "canonical_product_id": product.get("canonical_product_id") or product.get("product_id"),
                "product_status": product.get("product_status") or "active",
                "상품명 alias 목록": "\n".join(alias_names),
                "상품통합 상태": "통합상품" if merge_reasons else (product.get("product_status") or "active"),
                "통합근거 요약": "\n".join(merge_reasons),
                "partner_company": product.get("partner_company_name") or ", ".join(partner_names),
                "source_article_urls": "\n".join(source_urls),
                "상품명": product.get("normalized_product_name"),
                "원문 상품명": product.get("raw_product_name"),
                "보험회사": product.get("company_name"),
                "원문 회사명": product.get("company_name_raw"),
                "출시년월": display_release_year_month(product.get("release_year_month")),
                "최초 확인월": product.get("first_seen_month"),
                "대표 보종군": product.get("primary_product_type"),
                "가입연령": self._age_text(feature.get("join_age_min"), feature.get("join_age_max")),
                "고지유형": feature.get("notification_type"),
                "판매채널": feature.get("sales_channel"),
                "간편심사 여부": self._excel_value(feature.get("simple_underwriting_yn")),
                "비대면 여부": self._excel_value(feature.get("non_face_to_face_yn")),
                "갱신/비갱신": feature.get("renewal_type"),
                "납입기간": feature.get("payment_period"),
                "보험기간": feature.get("coverage_period"),
            }
            for label, key in [
                ("상품특징 요약", "feature_summary"),
                ("상품개발 관점 요약", "product_development_summary"),
                ("마케팅 요약", "marketing_summary"),
                ("대상고객 요약", "target_customer_summary"),
                ("언더라이팅 요약", "underwriting_summary"),
                ("채널 요약", "channel_summary"),
                ("주요보장 요약", "coverage_summary"),
                ("판매 요약", "sales_summary"),
                ("차별화 요약", "differentiation_summary"),
                ("리스크/유의사항", "risk_note_summary"),
                ("확인 필요 정보", "missing_info_summary"),
                ("미확인 필드", "missing_fields_json"),
            ]:
                row[label] = insight.get(key)

            for index, coverage in enumerate(coverages_by_product.get(product["product_id"], []), start=1):
                prefix = f"주요보장{index}"
                row[f"{prefix} 보장명"] = coverage.get("coverage_name_normalized") or coverage.get("coverage_name_raw")
                row[f"{prefix} 보장영역"] = coverage.get("risk_area")
                row[f"{prefix} 급부유형"] = coverage.get("benefit_type")
                row[f"{prefix} 최대보장금액"] = self._excel_value(coverage.get("max_amount_krw"))
                row[f"{prefix} 금액기준"] = coverage.get("amount_basis")
                row[f"{prefix} 지급조건"] = coverage.get("condition_text")
                row[f"{prefix} 보장요약"] = coverage.get("coverage_summary")

            for index, metric in enumerate(sales_by_product.get(product["product_id"], []), start=1):
                prefix = f"판매실적{index}"
                row[f"{prefix} 항목"] = metric.get("metric_name")
                row[f"{prefix} 값"] = self._excel_value(metric.get("metric_value"))
                row[f"{prefix} 단위"] = metric.get("metric_unit")
                row[f"{prefix} 기간"] = metric.get("metric_period")
                row[f"{prefix} 기준"] = metric.get("metric_basis")

            for index, article in enumerate(articles_by_product.get(product["product_id"], []), start=1):
                prefix = f"관련기사{index}"
                row[f"{prefix} 제목"] = article.get("title")
                row[f"{prefix} 발행일"] = self._excel_value(article.get("pub_date"))
            rows.append(self._filter_comparison_export_row(row))
        return rows

    def _duplicate_warning_rows(self, db: Session, products: list[dict[str, Any]]) -> list[dict[str, Any]]:
        product_ids = {int(item["product_id"]) for item in products if item.get("product_id") is not None}
        if not product_ids:
            return []
        guard = ProductDuplicateGuardService()
        rows: list[dict[str, Any]] = []
        for group in guard.find_duplicate_family_groups(db):
            if not set(group.get("product_ids") or []).intersection(product_ids):
                continue
            rows.append(
                {
                    "warning": "possible duplicate canonical products remain",
                    "company_name": group.get("company_name"),
                    "risk_score": group.get("risk_score"),
                    "product_ids": ", ".join(str(item) for item in group.get("product_ids") or []),
                    "product_names": " | ".join(group.get("product_names") or []),
                    "suggested_action": group.get("suggested_action"),
                }
            )
        return rows

    @staticmethod
    def _company_aliases(db: Session, company_id: int | None) -> list[str]:
        if company_id is None:
            return []
        company = db.get(DimCompany, company_id)
        if not company:
            return []
        aliases = [company.company_name_normalized or "", company.company_name_raw or ""]
        aliases.extend(item.strip() for item in (company.alias or "").split("|") if item.strip())
        return [item for item in dict.fromkeys(alias for alias in aliases if alias)]

    def _export_filter_rows(self, request: dict[str, Any]) -> list[dict[str, str]]:
        return [
            {"필터": "keyword", "값": self._excel_value(request.get("keyword"))},
            {"필터": "release_year", "값": self._excel_value(request.get("release_year"))},
            {"필터": "release_years", "값": self._excel_value(request.get("release_years"))},
            {"필터": "release_month", "값": self._excel_value(request.get("release_month"))},
            {"필터": "insurance_type", "값": self._excel_value(request.get("insurance_type"))},
            {"필터": "company_names", "값": self._excel_value(request.get("company_names"))},
            {"필터": "product_type_codes", "값": self._excel_value(request.get("product_type_codes"))},
        ]

    @staticmethod
    def _group_by_product(rows: list[Any]) -> dict[int, list[dict[str, Any]]]:
        grouped: dict[int, list[dict[str, Any]]] = {}
        for row in rows:
            item = dict(row)
            grouped.setdefault(item["product_id"], []).append(item)
        return grouped

    @staticmethod
    def _comparison_columns(rows: list[dict[str, Any]]) -> list[str]:
        preferred = [
            "상품 ID",
            "상품명",
            "보험회사",
            "출시년월",
            "대표 보종군",
            "가입연령",
            "판매채널",
            "간편심사 여부",
            "비대면 여부",
            "갱신/비갱신",
            "상품특징 요약",
            "상품개발 관점 요약",
            "마케팅 요약",
            "대상고객 요약",
            "언더라이팅 요약",
            "채널 요약",
            "주요보장 요약",
            "판매 요약",
            "차별화 요약",
            "리스크/유의사항",
        ]
        discovered: list[str] = []
        for row in rows:
            for key in row:
                if key not in COMPARISON_EXPORT_EXCLUDED_COLUMNS and key not in preferred and key not in discovered:
                    discovered.append(key)
        return preferred + discovered

    @staticmethod
    def _filter_comparison_export_row(row: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in row.items() if key not in COMPARISON_EXPORT_EXCLUDED_COLUMNS}

    @staticmethod
    def _compact_labeled_text(items: list[tuple[str, Any]], separator: str = "\n") -> str:
        parts = [f"{label}: {DashboardService._excel_value(value)}" for label, value in items if DashboardService._excel_value(value)]
        return separator.join(parts)

    @staticmethod
    def _excel_value(value: Any) -> str:
        if value is None or value == "":
            return ""
        if isinstance(value, bool):
            return "예" if value else "아니오"
        if isinstance(value, Decimal):
            return f"{value:,.2f}".rstrip("0").rstrip(".")
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, (list, tuple, set)):
            return ", ".join(DashboardService._excel_value(item) for item in value if DashboardService._excel_value(item))
        return str(value)

    @staticmethod
    def _review_label(value: Any) -> str:
        if value is None or value == "":
            return ""
        return "필요" if bool(value) else "정상"

    @staticmethod
    def _age_text(min_age: Any, max_age: Any) -> str:
        if min_age is None and max_age is None:
            return ""
        if min_age is not None and max_age is not None:
            return f"{min_age}세~{max_age}세"
        if min_age is not None:
            return f"{min_age}세 이상"
        return f"{max_age}세 이하"

    def _company_inclusion_sql(self, request: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        params: dict[str, Any] = {}
        parts: list[str] = []
        include_roles: list[str] = []
        if request.get("include_reinsurers"):
            include_roles.extend(sorted(REINSURER_ROLES))
        if request.get("include_foreign_branches"):
            include_roles.extend(sorted(FOREIGN_BRANCH_ROLES))
        if include_roles:
            placeholders = []
            for idx, role in enumerate(include_roles):
                key = f"include_role_{idx}"
                placeholders.append(f":{key}")
                params[key] = role
            parts.append(f"(s.include_in_product_news_default = 'Y' OR s.company_role IN ({','.join(placeholders)}))")
        else:
            parts.append("s.include_in_product_news_default = 'Y'")
        if not request.get("include_changed_companies", True):
            placeholders = []
            for idx, status in enumerate(sorted(CHANGED_STATUSES)):
                key = f"exclude_status_{idx}"
                placeholders.append(f":{key}")
                params[key] = status
            parts.append(f"COALESCE(s.status_2024_2026, 'unknown') NOT IN ({','.join(placeholders)})")
        if not request.get("include_short_term_insurers", True):
            parts.append("COALESCE(s.company_role, '') != 'short_term_pet_insurer'")
            parts.append("COALESCE(s.status_2024_2026, '') != 'new'")
        return (" AND " + " AND ".join(parts), params)

    def _summary(self, db: Session, products: list[dict[str, Any]]) -> dict[str, Any]:
        product_ids = [item["product_id"] for item in products]
        if not product_ids:
            return {"product_count": 0, "company_count": 0, "article_count": 0, "coverage_count": 0}
        placeholders = ",".join(f":id_{idx}" for idx in range(len(product_ids)))
        params = {f"id_{idx}": value for idx, value in enumerate(product_ids)}
        article_count = db.execute(
            text(f"SELECT COUNT(DISTINCT article_id) FROM fact_product_article WHERE product_id IN ({placeholders})"),
            params,
        ).scalar_one()
        coverage_count = db.execute(
            text(f"SELECT COUNT(*) FROM fact_product_major_coverage WHERE product_id IN ({placeholders})"),
            params,
        ).scalar_one()
        return {
            "product_count": len(product_ids),
            "company_count": len({item.get("company_name") for item in products if item.get("company_name")}),
            "article_count": article_count,
            "coverage_count": coverage_count,
        }
