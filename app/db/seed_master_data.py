from __future__ import annotations

import csv
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.models import DimCompany, DimProduct, FactProductCandidateCluster, FactProductObservation, DimProductType


def _nullable_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value or value.lower() == "null":
        return None
    return value


def _nullable_int(value: str | None) -> int | None:
    value = _nullable_text(value)
    return int(value) if value is not None else None


def seed_product_types(db: Session, csv_path: str | Path = "config/product_type_master.csv") -> int:
    path = Path(csv_path)
    count = 0
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            existing = db.get(DimProductType, row["product_type_code"])
            if existing:
                existing.product_type_name_ko = row["product_type_name_ko"]
                existing.description = _nullable_text(row.get("description"))
                existing.sort_order = int(row["sort_order"])
                existing.pivot_enabled = row["pivot_enabled"]
                existing.active_yn = row["active_yn"]
            else:
                db.add(
                    DimProductType(
                        product_type_code=row["product_type_code"],
                        product_type_name_ko=row["product_type_name_ko"],
                        description=_nullable_text(row.get("description")),
                        sort_order=int(row["sort_order"]),
                        pivot_enabled=row["pivot_enabled"],
                        active_yn=row["active_yn"],
                    )
                )
            count += 1
    db.commit()
    return count


def seed_companies(db: Session, csv_path: str | Path = "config/company_dictionary.csv") -> int:
    path = Path(csv_path)
    count = 0
    _remove_deleted_company_entries(db)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            normalized = row["company_name_normalized"]
            insurance_type = row.get("insurance_type") or row.get("insurance_type_default")
            existing = (
                db.query(DimCompany)
                .filter(DimCompany.company_name_normalized == normalized)
                .first()
            )
            if existing:
                existing.company_name_raw = row.get("company_name_raw") or existing.company_name_raw or normalized
                existing.alias = _nullable_text(row.get("alias"))
                existing.insurance_type = insurance_type
                existing.insurance_type_default = row.get("insurance_type_default") or insurance_type
                existing.company_role = _nullable_text(row.get("company_role"))
                existing.status_2024_2026 = _nullable_text(row.get("status_2024_2026")) or "active"
                existing.include_in_product_news_default = row.get("include_in_product_news_default") or "Y"
                existing.active_yn = row.get("active_yn", "Y")
                existing.valid_from = _nullable_text(row.get("valid_from"))
                existing.valid_to = _nullable_text(row.get("valid_to"))
                existing.predecessor_company = _nullable_text(row.get("predecessor_company"))
                existing.successor_company = _nullable_text(row.get("successor_company"))
                existing.establishment_year = _nullable_int(row.get("establishment_year"))
                existing.establishment_month = _nullable_int(row.get("establishment_month"))
                existing.establishment_day = _nullable_int(row.get("establishment_day"))
                existing.establishment_sort_date = _nullable_text(row.get("establishment_sort_date"))
                existing.establishment_basis = _nullable_text(row.get("establishment_basis"))
                existing.oldest_predecessor_year = _nullable_int(row.get("oldest_predecessor_year"))
                existing.current_brand_year = _nullable_int(row.get("current_brand_year"))
                existing.display_order_established = _nullable_int(row.get("display_order_established"))
                existing.sort_tie_breaker = _nullable_int(row.get("sort_tie_breaker"))
                existing.establishment_source_note = _nullable_text(row.get("establishment_source_note"))
                existing.notes = _nullable_text(row.get("notes"))
            else:
                db.add(
                    DimCompany(
                        company_name_normalized=normalized,
                        company_name_raw=row.get("company_name_raw") or normalized,
                        alias=_nullable_text(row.get("alias")),
                        insurance_type=insurance_type,
                        insurance_type_default=row.get("insurance_type_default") or insurance_type,
                        company_role=_nullable_text(row.get("company_role")),
                        status_2024_2026=_nullable_text(row.get("status_2024_2026")) or "active",
                        include_in_product_news_default=row.get("include_in_product_news_default") or "Y",
                        active_yn=row.get("active_yn", "Y"),
                        valid_from=_nullable_text(row.get("valid_from")),
                        valid_to=_nullable_text(row.get("valid_to")),
                        predecessor_company=_nullable_text(row.get("predecessor_company")),
                        successor_company=_nullable_text(row.get("successor_company")),
                        establishment_year=_nullable_int(row.get("establishment_year")),
                        establishment_month=_nullable_int(row.get("establishment_month")),
                        establishment_day=_nullable_int(row.get("establishment_day")),
                        establishment_sort_date=_nullable_text(row.get("establishment_sort_date")),
                        establishment_basis=_nullable_text(row.get("establishment_basis")),
                        oldest_predecessor_year=_nullable_int(row.get("oldest_predecessor_year")),
                        current_brand_year=_nullable_int(row.get("current_brand_year")),
                        display_order_established=_nullable_int(row.get("display_order_established")),
                        sort_tie_breaker=_nullable_int(row.get("sort_tie_breaker")),
                        establishment_source_note=_nullable_text(row.get("establishment_source_note")),
                        notes=_nullable_text(row.get("notes")),
                    )
                )
            count += 1
    db.commit()
    return count


def _remove_deleted_company_entries(db: Session) -> None:
    removed_names = {"스타"}
    rows = (
        db.query(DimCompany)
        .filter(
            (DimCompany.company_name_normalized.in_(removed_names))
            | (DimCompany.alias.like("%Starr%"))
            | (DimCompany.alias.like("%스타보험%"))
        )
        .all()
    )
    for company in rows:
        for product in db.query(DimProduct).filter(DimProduct.company_id == company.company_id).all():
            product.company_id = None
            product.company_name_raw = None
            product.insurance_type = product.insurance_type or "unknown"
            product.needs_review = True
            product.consolidation_status = "review"
        for observation in db.query(FactProductObservation).filter(FactProductObservation.company_id == company.company_id).all():
            observation.company_id = None
            if observation.company_name_raw in removed_names:
                observation.company_name_raw = None
            observation.candidate_type = observation.candidate_type or "review_company_attribution"
        for cluster in db.query(FactProductCandidateCluster).filter(FactProductCandidateCluster.company_id == company.company_id).all():
            cluster.company_id = None
            if cluster.candidate_company_name in removed_names:
                cluster.candidate_company_name = None
        db.delete(company)


def seed_all(db: Session) -> dict[str, int]:
    return {
        "product_types": seed_product_types(db),
        "companies": seed_companies(db),
    }


def company_display_order_summary(db: Session, insurance_type: str) -> list[tuple[int, str, int | None]]:
    rows = (
        db.query(DimCompany)
        .filter(DimCompany.active_yn == "Y", DimCompany.insurance_type == insurance_type)
        .order_by(
            DimCompany.display_order_established.is_(None),
            DimCompany.display_order_established,
            DimCompany.establishment_year.is_(None),
            DimCompany.establishment_year,
            DimCompany.establishment_month.is_(None),
            DimCompany.establishment_month,
            DimCompany.establishment_day.is_(None),
            DimCompany.establishment_day,
            DimCompany.sort_tie_breaker.is_(None),
            DimCompany.sort_tie_breaker,
            DimCompany.company_name_normalized,
        )
        .all()
    )
    return [(idx, row.company_name_normalized, row.establishment_year) for idx, row in enumerate(rows, start=1)]
