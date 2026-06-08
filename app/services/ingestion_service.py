from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.classifiers.product_type_classifier import ProductTypeClassifier
from app.db import repository
from app.db.models import DimProduct


class IngestionService:
    def upsert_structured_product(self, db: Session, payload: dict[str, Any], create_manual_record: bool = True) -> DimProduct:
        if create_manual_record:
            repository.create_manual_ingestion(db, "structured_json", title=(payload.get("product") or {}).get("raw_product_name"), input_json=payload, submitted_by=payload.get("submitted_by"))
        product_data = dict(payload.get("product") or {})
        assignments = list(payload.get("product_type_assignments") or [])
        if not product_data.get("primary_product_type_code"):
            classified = ProductTypeClassifier().classify(product_data.get("raw_product_name") or product_data.get("normalized_product_name"))
            product_data["primary_product_type_code"] = classified.primary.code
            if not assignments:
                assignments.append(
                    {
                        "product_type_code": classified.primary.code,
                        "assignment_role": "primary",
                        "classification_basis": classified.primary.basis,
                        "evidence_text": classified.primary.evidence_text,
                        "confidence": classified.primary.confidence,
                        "needs_human_review": classified.needs_review,
                    }
                )
        product = repository.upsert_product(db, product_data, allow_unknown_company=False)
        if product is None:
            raise ValueError("Unknown insurer company; product was not saved")
        repository.record_product_observation(
            db,
            product=product,
            raw_product_name=product_data.get("raw_product_name") or product.raw_product_name,
            normalized_product_name_candidate=product_data.get("normalized_product_name") or product.normalized_product_name,
            product_core_key=product.product_core_key,
            company_name_raw=product_data.get("company_name") or product_data.get("company_name_raw"),
            partner_company_name=product_data.get("partner_company_name"),
            product_type_code=product.primary_product_type_code,
            release_year_month=product.release_year_month,
            observation_context_text=product_data.get("context_text"),
            candidate_type=product_data.get("candidate_type") or "official_name",
            confidence=float(product_data.get("confidence_total") or product.confidence_total or 0.0),
        )
        for assignment in assignments:
            repository.add_type_assignment(db, product.product_id, assignment)
        if payload.get("features"):
            repository.add_structured_feature(db, product.product_id, payload["features"])
        if payload.get("narrative_insights"):
            repository.add_narrative_insight(db, product.product_id, payload["narrative_insights"])
        for coverage in payload.get("major_coverages") or []:
            repository.add_major_coverage(db, product.product_id, coverage)
        for metric in payload.get("sales_metrics") or []:
            repository.add_sales_metric(db, product.product_id, metric)
        db.commit()
        return product
