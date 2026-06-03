from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import DimProduct, FactProductMajorCoverage, FactSalesMetricStructured


class ReviewService:
    def queue(self, db: Session, limit: int = 100) -> list[dict]:
        items: list[dict] = []
        for product in db.query(DimProduct).filter(DimProduct.needs_review == True).limit(limit).all():  # noqa: E712
            items.append({"entity_type": "product", "entity_id": product.product_id, "label": product.normalized_product_name, "reason": "needs_review", "confidence": product.confidence_total})
        remaining = max(0, limit - len(items))
        for coverage in db.query(FactProductMajorCoverage).filter(FactProductMajorCoverage.needs_human_review == True).limit(remaining).all():  # noqa: E712
            items.append({"entity_type": "coverage", "entity_id": coverage.coverage_id, "label": coverage.coverage_name_normalized or "", "reason": "needs_human_review", "confidence": coverage.confidence})
        remaining = max(0, limit - len(items))
        for metric in db.query(FactSalesMetricStructured).filter(FactSalesMetricStructured.needs_human_review == True).limit(remaining).all():  # noqa: E712
            items.append({"entity_type": "sales_metric", "entity_id": metric.sales_metric_id, "label": metric.metric_name, "reason": "needs_human_review", "confidence": metric.confidence})
        return items

    def resolve(self, db: Session, entity_type: str, entity_id: int, updates: dict) -> dict:
        model_map = {
            "product": DimProduct,
            "coverage": FactProductMajorCoverage,
            "sales_metric": FactSalesMetricStructured,
        }
        model = model_map.get(entity_type)
        if not model:
            raise ValueError(f"Unsupported entity_type: {entity_type}")
        item = db.get(model, entity_id)
        if not item:
            raise ValueError(f"Entity not found: {entity_type} {entity_id}")
        for key, value in updates.items():
            if hasattr(item, key):
                setattr(item, key, value)
        if hasattr(item, "needs_review"):
            setattr(item, "needs_review", False)
        if hasattr(item, "needs_human_review"):
            setattr(item, "needs_human_review", False)
        db.commit()
        return {"status": "resolved", "entity_type": entity_type, "entity_id": entity_id}
