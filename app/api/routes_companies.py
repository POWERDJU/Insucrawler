from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.company import CompanyNormalizeRequest
from app.services.company_service import CompanyService

router = APIRouter()


@router.get("")
def list_companies(
    insurance_type: str | None = None,
    company_role: str | None = None,
    status_2024_2026: str | None = None,
    include_product_news_default_only: bool = True,
    include_reinsurers: bool = False,
    include_foreign_branches: bool = False,
    include_changed_companies: bool = True,
    include_short_term_insurers: bool = True,
    include_establishment_info: bool = True,
    db: Session = Depends(get_db),
) -> list[dict]:
    return CompanyService().list_companies(
        db,
        insurance_type=insurance_type,
        company_role=company_role,
        status_2024_2026=status_2024_2026,
        include_product_news_default_only=include_product_news_default_only,
        include_reinsurers=include_reinsurers,
        include_foreign_branches=include_foreign_branches,
        include_changed_companies=include_changed_companies,
        include_short_term_insurers=include_short_term_insurers,
        include_establishment_info=include_establishment_info,
    )


@router.post("/normalize")
def normalize_company(request: CompanyNormalizeRequest) -> dict:
    return CompanyService().normalize_text(request.text)
