from __future__ import annotations

import json
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import repository
from app.db.models import (
    DimCompany,
    DimPartnerCompany,
    DimProduct,
    DimProductAlias,
    FactArticle,
    FactProductMajorCoverage,
    FactProductMergeDecision,
    FactProductNarrativeInsight,
    FactProductObservation,
    FactProductPartner,
    FactProductStructuredFeature,
    FactSalesMetricStructured,
)
from app.utils.release_display import display_release_year_month
from app.services.coverage_dedupe_service import dedupe_major_coverages


class ProductService:
    def get_detail(self, db: Session, product_id: int, *, debug: bool = False) -> dict | None:
        product = db.get(DimProduct, product_id)
        if not product:
            return None
        company = db.get(DimCompany, product.company_id) if product.company_id else None
        type_rows = db.execute(
            text(
                """
                SELECT NULL AS assignment_id, p.primary_product_type_code AS product_type_code,
                       pt.product_type_name_ko, 'primary' AS assignment_role,
                       'dim_product.primary_product_type_code' AS classification_basis,
                       NULL AS evidence_text, p.confidence_total AS confidence,
                       p.needs_review AS needs_human_review
                FROM dim_product p
                LEFT JOIN dim_product_type pt ON pt.product_type_code = p.primary_product_type_code
                WHERE p.product_id = :product_id
                """
            ),
            {"product_id": product_id},
        ).mappings().all()
        features = (
            db.query(FactProductStructuredFeature)
            .filter(FactProductStructuredFeature.product_id == product_id)
            .order_by(FactProductStructuredFeature.feature_id.desc())
            .all()
        )
        narratives = (
            db.query(FactProductNarrativeInsight)
            .filter(FactProductNarrativeInsight.product_id == product_id)
            .order_by(FactProductNarrativeInsight.insight_id.desc())
            .all()
        )
        coverages = (
            db.query(FactProductMajorCoverage)
            .filter(FactProductMajorCoverage.product_id == product_id)
            .order_by(FactProductMajorCoverage.display_order, FactProductMajorCoverage.coverage_id)
            .all()
        )
        sales = (
            db.query(FactSalesMetricStructured)
            .filter(FactSalesMetricStructured.product_id == product_id)
            .order_by(FactSalesMetricStructured.sales_metric_id)
            .all()
        )
        articles = db.execute(
            text(
                """
                SELECT a.article_id, a.title, a.url, a.original_url, a.pub_date, pa.confidence_total, pa.needs_review
                FROM fact_product_article pa
                JOIN fact_article a ON a.article_id = pa.article_id
                WHERE pa.product_id = :product_id
                ORDER BY a.pub_date DESC
                """
            ),
            {"product_id": product_id},
        ).mappings().all()
        aliases = (
            db.query(DimProductAlias)
            .filter(DimProductAlias.product_id == product_id)
            .order_by(DimProductAlias.first_seen_at.asc(), DimProductAlias.product_alias_id.asc())
            .all()
        )
        correction_rows = db.execute(
            text(
                """
                SELECT a.field_audit_id, a.field_path, a.extractor_value, a.verifier_verdict,
                       a.suggested_value, a.evidence_text, a.severity, a.final_value, a.final_basis, a.created_at
                FROM fact_extraction_field_audit a
                JOIN fact_extraction_comparison c ON c.comparison_id = a.comparison_id
                WHERE c.product_id = :product_id
                  AND a.verifier_verdict = 'incorrect'
                  AND a.final_value IS NOT NULL
                  AND (
                    a.field_path LIKE 'products%.identity.raw_product_name'
                    OR a.field_path LIKE 'products%.identity.normalized_product_name_candidate'
                    OR a.field_path LIKE 'products%.product_type_classification.primary_product_type%'
                  )
                ORDER BY a.field_audit_id DESC
                """
            ),
            {"product_id": product_id},
        ).mappings().all()
        partner_rows = db.execute(
            text(
                """
                SELECT pp.product_partner_id, pc.partner_name_normalized, pc.partner_type,
                       pp.partner_role, pp.evidence_text, pp.confidence, pp.article_id
                FROM fact_product_partner pp
                JOIN dim_partner_company pc ON pc.partner_id = pp.partner_id
                WHERE pp.product_id = :product_id
                ORDER BY pp.product_partner_id
                """
            ),
            {"product_id": product_id},
        ).mappings().all()
        merge_rows = db.execute(
            text(
                """
                SELECT merge_decision_id, canonical_product_id, duplicate_product_id,
                       decision_type, decision_source, confidence, reason,
                       evidence_article_ids_json, alias_names_json, applied_at,
                       applied_by, needs_review, created_at
                FROM fact_product_merge_decision
                WHERE canonical_product_id = :product_id OR duplicate_product_id = :product_id
                ORDER BY merge_decision_id DESC
                """
            ),
            {"product_id": product_id},
        ).mappings().all()
        observations = (
            db.query(FactProductObservation)
            .filter(FactProductObservation.product_id == product_id)
            .order_by(FactProductObservation.created_at.asc(), FactProductObservation.observation_id.asc())
            .all()
        )
        raw_coverages = [self._model_dict(row) for row in coverages]
        deduped_coverages, coverage_dedupe_summary = dedupe_major_coverages(raw_coverages)
        detail = {
            "product_id": product.product_id,
            "raw_product_name": product.raw_product_name,
            "normalized_product_name": product.normalized_product_name,
            "product_status": product.product_status,
            "merged_into_product_id": product.merged_into_product_id,
            "canonical_product_id": product.canonical_product_id or product.product_id,
            "partner_company_name": product.partner_company_name,
            "partner_context_summary": product.partner_context_summary,
            "company_name_raw": product.company_name_raw,
            "company_name": company.company_name_normalized if company else None,
            "insurance_type": product.insurance_type,
            "release_year_month": display_release_year_month(product.release_year_month),
            "release_year_month_basis": product.release_year_month_basis,
            "release_year_month_source_article_id": product.release_year_month_source_article_id,
            "release_year_month_source_type": product.release_year_month_source_type,
            "release_year_month_inferred_at": product.release_year_month_inferred_at,
            "first_seen_month": product.first_seen_month,
            "primary_product_type_code": product.primary_product_type_code,
            "confidence_total": product.confidence_total,
            "needs_review": product.needs_review,
            "product_type_assignments": [dict(row) for row in type_rows],
            "structured_features": [self._model_dict(row) for row in features],
            "narrative_insights": [self._model_dict(row) for row in narratives],
            "major_coverages": deduped_coverages,
            "coverage_dedupe_summary": coverage_dedupe_summary,
            "sales_metrics": [self._model_dict(row) for row in sales],
            "articles": [dict(row) for row in articles],
            "product_aliases": [self._model_dict(row) for row in aliases],
            "product_observations": [self._model_dict(row) for row in observations],
            "product_partners": [dict(row) for row in partner_rows],
            "merge_decisions": [self._merge_decision_dict(row) for row in merge_rows],
            "correction_audits": [self._correction_dict(row) for row in correction_rows],
        }
        if debug:
            detail["raw_coverages"] = raw_coverages
        return detail

    @staticmethod
    def _model_dict(row) -> dict:
        return {column.name: getattr(row, column.name) for column in row.__table__.columns}

    @staticmethod
    def _correction_dict(row) -> dict:
        item = dict(row)
        for key in ["extractor_value", "suggested_value", "final_value"]:
            item[key] = ProductService._json_value(item.get(key))
        return item

    @staticmethod
    def _merge_decision_dict(row) -> dict:
        item = dict(row)
        for key in ["evidence_article_ids_json", "alias_names_json"]:
            item[key] = ProductService._json_value(item.get(key))
        return item

    @staticmethod
    def _json_value(value):
        if value is None:
            return None
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return value

    def add_manual_type_assignment(self, db: Session, product_id: int, payload: dict) -> None:
        product = db.get(DimProduct, product_id)
        if product:
            product.primary_product_type_code = payload["product_type_code"]
            product.needs_review = False
        db.commit()

    def add_manual_coverage(self, db: Session, product_id: int, payload: dict) -> int:
        item = repository.add_major_coverage(db, product_id, payload)
        db.commit()
        return item.coverage_id
