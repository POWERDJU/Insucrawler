from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.normalizers.korean_description_normalizer import koreanize_description_text
from app.utils.release_display import display_release_year_month

from app.services.company_service import FOREIGN_BRANCH_ROLES, REINSURER_ROLES
from app.services.company_logo_service import CompanyLogoService
from app.services.product_exclusion_service import product_policy_exclusion_sql


LAUNCH_KEYWORDS = ("출시", "신상품", "신규 출시", "선보", "내놨")


class MonthlyNewProductService:
    def get_monthly_new_products(
        self,
        db: Session,
        year_month: str | None = None,
        limit: int = 10,
        fallback_latest: bool = True,
        insurance_type: str | None = None,
        include_review: bool = False,
        include_excluded_policy_products: bool = False,
    ) -> dict[str, Any]:
        explicit_month = self._normalize_year_month(year_month)
        target_month = explicit_month or self._current_year_month()
        target_months = [target_month] if explicit_month else self._current_and_previous_months(target_month)
        normalized_insurance_type = None if insurance_type in {None, "", "전체"} else insurance_type
        bounded_limit = max(1, min(int(limit or 10), 50))
        products = self._query_products(
            db,
            target_months,
            bounded_limit,
            normalized_insurance_type,
            include_review,
            include_excluded_policy_products,
        )
        fallback_used = False
        display_month = target_month
        display_months = target_months
        if not products and fallback_latest:
            latest_month = self._latest_release_month(db, normalized_insurance_type, include_review, include_excluded_policy_products)
            if latest_month:
                display_month = latest_month
                display_months = [latest_month]
                fallback_used = latest_month != target_month
                products = self._query_products(
                    db,
                    [latest_month],
                    bounded_limit,
                    normalized_insurance_type,
                    include_review,
                    include_excluded_policy_products,
                )
        items = [self._item(db, product) for product in products]
        return {
            "year_month": display_month,
            "display_year_month": self._display_year_month(display_month),
            "months": display_months,
            "display_period": ", ".join(display_months),
            "fallback_used": fallback_used,
            "items": items,
        }

    def _query_products(
        self,
        db: Session,
        year_month: str | list[str],
        limit: int,
        insurance_type: str | None,
        include_review: bool,
        include_excluded_policy_products: bool,
    ) -> list[dict[str, Any]]:
        sql = """
            SELECT p.product_id,
                   p.normalized_product_name,
                   p.raw_product_name,
                   p.insurance_type,
                   p.release_year_month,
                   p.release_year_month_basis,
                   p.release_year_month_source_article_id,
                   p.primary_product_type_code,
                   p.confidence_total,
                   p.needs_review,
                   c.company_name_normalized AS company_name,
                   c.include_in_product_news_default,
                   c.company_role,
                   pt.product_type_name_ko AS primary_product_type,
                   (
                     SELECT MAX(a.pub_date)
                     FROM fact_product_article pa
                     JOIN fact_article a ON a.article_id = pa.article_id
                     WHERE pa.product_id = p.product_id
                       AND COALESCE(a.multi_company_article_yn, 0) = 0
                       AND COALESCE(pa.extraction_status, 'saved') NOT IN ('excluded_multi_company', 'excluded_article_eligibility')
                   ) AS latest_article_pub_date
            FROM dim_product p
            LEFT JOIN dim_company c ON c.company_id = p.company_id
            LEFT JOIN dim_product_type pt ON pt.product_type_code = p.primary_product_type_code
            WHERE p.release_year_month IN ({month_placeholders})
              AND TRIM(COALESCE(p.normalized_product_name, '')) NOT LIKE :special_clause_suffix
              AND TRIM(COALESCE(p.raw_product_name, '')) NOT LIKE :special_clause_suffix
              AND TRIM(COALESCE(p.normalized_product_name, '')) NOT LIKE :rider_suffix
              AND TRIM(COALESCE(p.raw_product_name, '')) NOT LIKE :rider_suffix
              AND COALESCE(c.include_in_product_news_default, 'Y') = 'Y'
              AND EXISTS (
                  SELECT 1
                  FROM fact_product_article clean_pa
                  JOIN fact_article clean_a ON clean_a.article_id = clean_pa.article_id
                  WHERE clean_pa.product_id = p.product_id
                    AND COALESCE(clean_a.multi_company_article_yn, 0) = 0
                    AND COALESCE(clean_pa.extraction_status, 'saved') NOT IN ('excluded_multi_company', 'excluded_article_eligibility')
              )
        """
        month_values = year_month if isinstance(year_month, list) else [year_month]
        month_placeholders = []
        params: dict[str, Any] = {
            "limit": limit,
            "special_clause_suffix": "%특별약관",
            "rider_suffix": "%특약",
        }
        for idx, month_value in enumerate(month_values):
            key = f"month_{idx}"
            month_placeholders.append(f":{key}")
            params[key] = month_value
        sql = sql.format(month_placeholders=",".join(month_placeholders))
        if not include_excluded_policy_products:
            exclusion_sql, exclusion_params = product_policy_exclusion_sql("p", param_prefix="monthly_excluded")
            sql += exclusion_sql
            params.update(exclusion_params)
        if not include_review:
            sql += " AND p.needs_review = 0"
        if insurance_type:
            sql += " AND p.insurance_type = :insurance_type"
            params["insurance_type"] = insurance_type
        excluded_roles = sorted(REINSURER_ROLES | FOREIGN_BRANCH_ROLES)
        for idx, role in enumerate(excluded_roles):
            key = f"excluded_role_{idx}"
            params[key] = role
        placeholders = ",".join(f":excluded_role_{idx}" for idx in range(len(excluded_roles)))
        sql += f" AND COALESCE(c.company_role, '') NOT IN ({placeholders})"
        sql += """
            ORDER BY p.release_year_month DESC,
                     latest_article_pub_date DESC,
                     p.confidence_total DESC,
                     p.product_id DESC
            LIMIT :limit
        """
        return [dict(row) for row in db.execute(text(sql), params).mappings().all()]

    def _latest_release_month(
        self,
        db: Session,
        insurance_type: str | None,
        include_review: bool,
        include_excluded_policy_products: bool,
    ) -> str | None:
        sql = """
            SELECT MAX(p.release_year_month)
            FROM dim_product p
            LEFT JOIN dim_company c ON c.company_id = p.company_id
            WHERE p.release_year_month IS NOT NULL
              AND COALESCE(c.include_in_product_news_default, 'Y') = 'Y'
              AND EXISTS (
                  SELECT 1
                  FROM fact_product_article clean_pa
                  JOIN fact_article clean_a ON clean_a.article_id = clean_pa.article_id
                  WHERE clean_pa.product_id = p.product_id
                    AND COALESCE(clean_a.multi_company_article_yn, 0) = 0
                    AND COALESCE(clean_pa.extraction_status, 'saved') NOT IN ('excluded_multi_company', 'excluded_article_eligibility')
              )
              AND TRIM(COALESCE(p.normalized_product_name, '')) NOT LIKE :special_clause_suffix
              AND TRIM(COALESCE(p.raw_product_name, '')) NOT LIKE :special_clause_suffix
              AND TRIM(COALESCE(p.normalized_product_name, '')) NOT LIKE :rider_suffix
              AND TRIM(COALESCE(p.raw_product_name, '')) NOT LIKE :rider_suffix
        """
        params: dict[str, Any] = {"special_clause_suffix": "%특별약관", "rider_suffix": "%특약"}
        if not include_excluded_policy_products:
            exclusion_sql, exclusion_params = product_policy_exclusion_sql("p", param_prefix="monthly_latest_excluded")
            sql += exclusion_sql
            params.update(exclusion_params)
        if not include_review:
            sql += " AND p.needs_review = 0"
        if insurance_type:
            sql += " AND p.insurance_type = :insurance_type"
            params["insurance_type"] = insurance_type
        excluded_roles = sorted(REINSURER_ROLES | FOREIGN_BRANCH_ROLES)
        for idx, role in enumerate(excluded_roles):
            key = f"excluded_role_{idx}"
            params[key] = role
        placeholders = ",".join(f":excluded_role_{idx}" for idx in range(len(excluded_roles)))
        sql += f" AND COALESCE(c.company_role, '') NOT IN ({placeholders})"
        return db.execute(text(sql), params).scalar_one_or_none()

    def _item(self, db: Session, product: dict[str, Any]) -> dict[str, Any]:
        article = self._representative_article(db, product)
        narrative = self._latest_narrative(db, product["product_id"])
        summary = self._summary(narrative, article)
        return {
            "product_id": product["product_id"],
            "product_name": product.get("normalized_product_name"),
            "raw_product_name": product.get("raw_product_name"),
            "company_name": product.get("company_name"),
            "insurance_type": product.get("insurance_type"),
            "company_logo_url": CompanyLogoService().get_logo_url(product.get("company_name"), product.get("insurance_type")),
            "release_year_month": display_release_year_month(product.get("release_year_month")),
            "release_year_month_basis": product.get("release_year_month_basis"),
            "primary_product_type": product.get("primary_product_type"),
            "summary": summary,
            "article_title": article.get("title") if article else None,
            "article_pub_date": article.get("pub_date") if article else None,
            "article_url": article.get("article_url") if article else None,
            "source_label": "원문 기사" if article and article.get("article_url") else None,
            "confidence_total": product.get("confidence_total"),
            "needs_review": bool(product.get("needs_review")),
        }

    def _representative_article(self, db: Session, product: dict[str, Any]) -> dict[str, Any] | None:
        article_rows = [
            dict(row)
            for row in db.execute(
                text(
                    """
                    SELECT a.article_id,
                           a.title,
                           a.description,
                           a.pub_date,
                           COALESCE(a.original_url, a.url) AS article_url
                    FROM fact_product_article pa
                    JOIN fact_article a ON a.article_id = pa.article_id
                    WHERE pa.product_id = :product_id
                      AND COALESCE(a.multi_company_article_yn, 0) = 0
                      AND COALESCE(pa.extraction_status, 'saved') NOT IN ('excluded_multi_company', 'excluded_article_eligibility')
                    ORDER BY a.pub_date ASC, a.article_id ASC
                    """
                ),
                {"product_id": product["product_id"]},
            ).mappings().all()
        ]
        if not article_rows:
            return None
        source_id = product.get("release_year_month_source_article_id")
        if source_id:
            for article in article_rows:
                if article["article_id"] == source_id:
                    return article
        launch_articles = [article for article in article_rows if self._has_launch_keyword(article)]
        if launch_articles:
            return launch_articles[0]
        return article_rows[0] or article_rows[-1]

    @staticmethod
    def _has_launch_keyword(article: dict[str, Any]) -> bool:
        text_value = " ".join(str(article.get(key) or "") for key in ["title", "description"])
        return any(keyword in text_value for keyword in LAUNCH_KEYWORDS)

    @staticmethod
    def _latest_narrative(db: Session, product_id: int) -> dict[str, Any]:
        row = db.execute(
            text(
                """
                SELECT product_development_summary,
                       feature_summary,
                       coverage_summary,
                       marketing_summary
                FROM fact_product_narrative_insight
                WHERE product_id = :product_id
                ORDER BY insight_id DESC
                LIMIT 1
                """
            ),
            {"product_id": product_id},
        ).mappings().first()
        return dict(row) if row else {}

    def _summary(self, narrative: dict[str, Any], article: dict[str, Any] | None) -> str:
        candidates = [
            narrative.get("product_development_summary"),
            narrative.get("feature_summary"),
            narrative.get("coverage_summary"),
            narrative.get("marketing_summary"),
            article.get("description") if article else None,
            article.get("title") if article else None,
        ]
        for value in candidates:
            text_value = self._clean_text(value)
            if text_value:
                korean_text = koreanize_description_text(text_value, "feature_summary") or text_value
                return self._truncate_summary(korean_text)
        return ""

    @staticmethod
    def _clean_text(value: Any) -> str:
        text_value = re.sub(r"<[^>]+>", " ", str(value or ""))
        text_value = re.sub(r"\s+", " ", text_value).strip()
        return text_value

    @staticmethod
    def _truncate_summary(value: str, limit: int = 210) -> str:
        if len(value) <= limit:
            return value
        boundary = max(value.rfind(".", 0, limit), value.rfind("다.", 0, limit), value.rfind("요.", 0, limit))
        if boundary >= 80:
            return value[: boundary + 1].strip()
        return value[:limit].rstrip() + "..."

    @staticmethod
    def _normalize_year_month(value: str | None) -> str | None:
        if not value:
            return None
        if not re.fullmatch(r"\d{4}-\d{2}", value):
            return None
        return value

    @staticmethod
    def _current_year_month() -> str:
        return datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m")

    @staticmethod
    def _current_and_previous_months(year_month: str) -> list[str]:
        year, month = [int(part) for part in year_month.split("-", 1)]
        previous = f"{year - 1}-12" if month == 1 else f"{year:04d}-{month - 1:02d}"
        return [year_month, previous]

    @staticmethod
    def _display_year_month(value: str | None) -> str:
        if not value or "-" not in value:
            return value or ""
        year, month = value.split("-", 1)
        return f"{year}년 {int(month)}월"
