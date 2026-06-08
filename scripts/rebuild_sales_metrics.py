from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import SessionLocal
from app.db.models import DimProduct, FactSalesMetricStructured
from app.services.sales_metric_validation_service import SalesMetricValidationService


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output", default="data/exports/sales_metric_validation_audit.csv")
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    with SessionLocal() as db:
        service = SalesMetricValidationService()
        metrics = db.query(FactSalesMetricStructured).all()
        for metric in metrics:
            product = db.get(DimProduct, metric.product_id)
            decision = service.validate(
                {
                    "metric_name": metric.metric_name,
                    "metric_value": metric.metric_value,
                    "metric_unit": metric.metric_unit,
                    "metric_period": metric.metric_period,
                    "metric_basis": metric.metric_basis,
                    "evidence_text": metric.evidence_text,
                },
                product_name=product.normalized_product_name if product else None,
                context_text=metric.evidence_text,
            )
            if decision.accepted:
                continue
            rows.append(
                {
                    "sales_metric_id": metric.sales_metric_id,
                    "product_id": metric.product_id,
                    "product_name": product.normalized_product_name if product else None,
                    "metric_name": metric.metric_name,
                    "metric_value": metric.metric_value,
                    "reason": decision.reason,
                }
            )
            if args.apply:
                metric.needs_human_review = True
        if args.apply:
            db.commit()
    with output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["sales_metric_id", "product_id", "product_name", "metric_name", "metric_value", "reason"],
        )
        writer.writeheader()
        writer.writerows(rows)
    print({"apply": args.apply, "count": len(rows), "output": str(output)})


if __name__ == "__main__":
    main()
