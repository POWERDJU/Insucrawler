from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import SessionLocal, engine
from app.db.migrations import init_db
from app.db.models import DimProduct
from app.normalizers.company_normalizer import CompanyNormalizer
from app.utils.dates import utcnow


def main() -> None:
    init_db(engine)
    export_dir = Path("data/exports")
    export_dir.mkdir(parents=True, exist_ok=True)
    path = export_dir / f"unknown_company_audit_{utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    normalizer = CompanyNormalizer()
    with SessionLocal() as db, path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["product_id", "normalized_product_name", "company_name_raw", "match_type", "needs_review"])
        rows = db.query(DimProduct).filter(DimProduct.company_id.is_(None)).order_by(DimProduct.product_id).all()
        for product in rows:
            match = normalizer.normalize(product.company_name_raw)
            writer.writerow([
                product.product_id,
                product.normalized_product_name,
                product.company_name_raw,
                match.match_type if match else "empty",
                True,
            ])
    print({"unknown_company_products": len(rows), "path": str(path)})


if __name__ == "__main__":
    main()
