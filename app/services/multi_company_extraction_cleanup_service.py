from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models import DimProduct, FactExclusiveUseRight


class MultiCompanyExtractionCleanupService:
    """Source-level cleanup for records derived from multi-company articles."""

    def product_cleanup_plan(self, db: Session) -> list[dict[str, Any]]:
        rows = db.execute(
            text(
                """
                SELECT p.product_id,
                       p.normalized_product_name AS product_name,
                       pa.article_id,
                       a.title AS article_title,
                       'fact_product_article' AS source_record_type,
                       pa.product_article_id AS source_record_id,
                       COALESCE(pa.extraction_status, 'saved') AS current_status,
                       CASE
                         WHEN EXISTS (
                           SELECT 1
                           FROM fact_product_article clean_pa
                           JOIN fact_article clean_a ON clean_a.article_id = clean_pa.article_id
                           WHERE clean_pa.product_id = p.product_id
                             AND COALESCE(clean_a.multi_company_article_yn, 0) = 0
                             AND COALESCE(clean_pa.extraction_status, 'saved') NOT IN ('excluded_multi_company', 'excluded_article_eligibility')
                         )
                         THEN 1 ELSE 0
                       END AS product_has_non_multi_company_sources
                FROM fact_product_article pa
                JOIN fact_article a ON a.article_id = pa.article_id
                JOIN dim_product p ON p.product_id = pa.product_id
                WHERE COALESCE(a.multi_company_article_yn, 0) = 1
                ORDER BY p.product_id, pa.article_id
                """
            )
        ).mappings().all()
        plan = []
        for row in rows:
            has_clean = bool(row["product_has_non_multi_company_sources"])
            plan.append(
                {
                    **dict(row),
                    "proposed_status": "excluded_multi_company",
                    "action": "exclude_source_record" if has_clean else "exclude_source_and_mark_product",
                    "reason": "multi-company source article; canonical kept only if non-multi evidence exists",
                }
            )
        return plan

    def apply_product_cleanup(self, db: Session) -> dict[str, int]:
        plan = self.product_cleanup_plan(db)
        multi_article_ids = [row["article_id"] for row in plan]
        if multi_article_ids:
            placeholders, params = self._in_params("article_id", sorted(set(multi_article_ids)))
            db.execute(
                text(
                    f"""
                    UPDATE fact_product_article
                    SET extraction_status = 'excluded_multi_company'
                    WHERE article_id IN ({placeholders})
                    """
                ),
                params,
            )
            db.execute(
                text(
                    f"""
                    UPDATE fact_product_observation
                    SET candidate_type = 'excluded_multi_company'
                    WHERE article_id IN ({placeholders})
                    """
                ),
                params,
            )
        product_ids = sorted({int(row["product_id"]) for row in plan})
        marked_products = 0
        for product_id in product_ids:
            if self._product_has_non_multi_source(db, product_id):
                continue
            product = db.get(DimProduct, product_id)
            if product:
                product.product_status = "rejected_multi_company_only"
                product.consolidation_status = "excluded_multi_company_only"
                product.needs_review = True
                marked_products += 1
        db.commit()
        return {"source_records_excluded": len(plan), "products_marked": marked_products}

    def exclusive_cleanup_plan(self, db: Session) -> list[dict[str, Any]]:
        rows = db.execute(
            text(
                """
                SELECT er.exclusive_right_id,
                       er.subject_name,
                       era.article_id,
                       a.title AS article_title,
                       'fact_exclusive_use_right_article' AS source_record_type,
                       era.exclusive_right_article_id AS source_record_id,
                       er.event_status AS current_status,
                       CASE
                         WHEN EXISTS (
                           SELECT 1
                           FROM fact_exclusive_use_right_article clean_era
                           JOIN fact_article clean_a ON clean_a.article_id = clean_era.article_id
                           WHERE clean_era.exclusive_right_id = er.exclusive_right_id
                             AND COALESCE(clean_a.multi_company_article_yn, 0) = 0
                         )
                         THEN 1 ELSE 0
                       END AS event_has_non_multi_company_sources
                FROM fact_exclusive_use_right_article era
                JOIN fact_article a ON a.article_id = era.article_id
                JOIN fact_exclusive_use_right er ON er.exclusive_right_id = era.exclusive_right_id
                WHERE COALESCE(a.multi_company_article_yn, 0) = 1
                ORDER BY er.exclusive_right_id, era.article_id
                """
            )
        ).mappings().all()
        plan = []
        for row in rows:
            has_clean = bool(row["event_has_non_multi_company_sources"])
            plan.append(
                {
                    **dict(row),
                    "proposed_status": "excluded_multi_company",
                    "action": "exclude_source_record" if has_clean else "exclude_source_and_mark_event",
                    "reason": "multi-company source article; event kept only if non-multi evidence exists",
                }
            )
        return plan

    def apply_exclusive_cleanup(self, db: Session) -> dict[str, int]:
        plan = self.exclusive_cleanup_plan(db)
        multi_article_ids = [row["article_id"] for row in plan]
        if multi_article_ids:
            placeholders, params = self._in_params("article_id", sorted(set(multi_article_ids)))
            db.execute(
                text(
                    f"""
                    UPDATE fact_exclusive_use_right_observation
                    SET status_candidate = 'excluded_multi_company', needs_review = 1
                    WHERE article_id IN ({placeholders})
                    """
                ),
                params,
            )
        event_ids = sorted({int(row["exclusive_right_id"]) for row in plan})
        marked_events = 0
        for event_id in event_ids:
            if self._exclusive_has_non_multi_source(db, event_id):
                self._refresh_exclusive_article_count(db, event_id)
                continue
            event = db.get(FactExclusiveUseRight, event_id)
            if event:
                event.event_status = "rejected_multi_company_only"
                event.needs_review = True
                marked_events += 1
        db.commit()
        return {"source_records_excluded": len(plan), "events_marked": marked_events}

    def write_plan_csv(self, rows: list[dict[str, Any]], path: str | Path) -> None:
        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = sorted({key for row in rows for key in row.keys()})
        with output.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    @staticmethod
    def _product_has_non_multi_source(db: Session, product_id: int) -> bool:
        return bool(
            db.execute(
                text(
                    """
                    SELECT 1
                    FROM fact_product_article pa
                    JOIN fact_article a ON a.article_id = pa.article_id
                    WHERE pa.product_id = :product_id
                      AND COALESCE(a.multi_company_article_yn, 0) = 0
                      AND COALESCE(pa.extraction_status, 'saved') NOT IN ('excluded_multi_company', 'excluded_article_eligibility')
                    LIMIT 1
                    """
                ),
                {"product_id": product_id},
            ).first()
        )

    @staticmethod
    def _exclusive_has_non_multi_source(db: Session, exclusive_right_id: int) -> bool:
        return bool(
            db.execute(
                text(
                    """
                    SELECT 1
                    FROM fact_exclusive_use_right_article era
                    JOIN fact_article a ON a.article_id = era.article_id
                    WHERE era.exclusive_right_id = :exclusive_right_id
                      AND COALESCE(a.multi_company_article_yn, 0) = 0
                    LIMIT 1
                    """
                ),
                {"exclusive_right_id": exclusive_right_id},
            ).first()
        )

    @staticmethod
    def _refresh_exclusive_article_count(db: Session, exclusive_right_id: int) -> None:
        count = int(
            db.execute(
                text(
                    """
                    SELECT COUNT(DISTINCT era.article_id)
                    FROM fact_exclusive_use_right_article era
                    JOIN fact_article a ON a.article_id = era.article_id
                    WHERE era.exclusive_right_id = :exclusive_right_id
                      AND COALESCE(a.multi_company_article_yn, 0) = 0
                    """
                ),
                {"exclusive_right_id": exclusive_right_id},
            ).scalar()
            or 0
        )
        event = db.get(FactExclusiveUseRight, exclusive_right_id)
        if event:
            event.article_count = count

    @staticmethod
    def _in_params(prefix: str, values: list[int]) -> tuple[str, dict[str, int]]:
        params = {f"{prefix}_{idx}": value for idx, value in enumerate(values)}
        placeholders = ",".join(f":{key}" for key in params)
        return placeholders, params
