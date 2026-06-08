from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.product import ManualCoverageRequest, ManualTypeAssignmentRequest
from app.services.product_service import ProductService
from app.services.search_service import SearchService

router = APIRouter()


@router.get("/search")
def search_products(
    q: str | None = None,
    company_name: str | None = None,
    insurance_type: str | None = None,
    product_type_code: str | None = None,
    release_year_month_from: str | None = None,
    release_year_month_to: str | None = None,
    min_confidence: float | None = None,
    include_review: bool = False,
    company_role: str | None = None,
    status_2024_2026: str | None = None,
    include_in_product_news_default: str | None = None,
    include_reinsurers: bool = False,
    include_foreign_branches: bool = False,
    include_inactive_or_changed_companies: bool = True,
    include_excluded_policy_products: bool = False,
    db: Session = Depends(get_db),
) -> list[dict]:
    return SearchService().search_products(
        db,
        q=q,
        company_name=company_name,
        insurance_type=insurance_type,
        product_type_code=product_type_code,
        release_year_month_from=release_year_month_from,
        release_year_month_to=release_year_month_to,
        include_secondary_types=False,
        min_confidence=min_confidence,
        include_review=include_review,
        company_role=company_role,
        status_2024_2026=status_2024_2026,
        include_in_product_news_default=include_in_product_news_default,
        include_reinsurers=include_reinsurers,
        include_foreign_branches=include_foreign_branches,
        include_inactive_or_changed_companies=include_inactive_or_changed_companies,
        include_excluded_policy_products=include_excluded_policy_products,
    )


@router.get("/{product_id}")
def get_product(product_id: int, debug: bool = False, db: Session = Depends(get_db)) -> dict:
    detail = ProductService().get_detail(db, product_id, debug=debug)
    if not detail:
        raise HTTPException(status_code=404, detail="Product not found")
    return detail


@router.post("/{product_id}/manual-type-assignment")
def manual_type_assignment(product_id: int, request: ManualTypeAssignmentRequest, db: Session = Depends(get_db)) -> dict:
    ProductService().add_manual_type_assignment(db, product_id, request.model_dump())
    return {"status": "saved", "product_id": product_id}


@router.post("/{product_id}/manual-coverage")
def manual_coverage(product_id: int, request: ManualCoverageRequest, db: Session = Depends(get_db)) -> dict:
    coverage_id = ProductService().add_manual_coverage(db, product_id, request.model_dump())
    return {"status": "saved", "product_id": product_id, "coverage_id": coverage_id}
