from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy.orm import Session
from starlette.templating import Jinja2Templates

from app.db.database import get_db
from app.schemas.dashboard import DashboardQueryRequest
from app.services.dashboard_service import DashboardService
from app.services.exclusive_right_service import ExclusiveRightService
from app.services.monthly_new_product_service import MonthlyNewProductService

templates = Jinja2Templates(directory="app/templates")
router = APIRouter()


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "dashboard.html")


@router.get("/api/dashboard/options")
def dashboard_options(
    include_reinsurers: bool = False,
    include_foreign_branches: bool = False,
    include_changed_companies: bool = True,
    include_short_term_insurers: bool = True,
    db: Session = Depends(get_db),
) -> dict:
    return DashboardService().options(
        db,
        include_reinsurers=include_reinsurers,
        include_foreign_branches=include_foreign_branches,
        include_changed_companies=include_changed_companies,
        include_short_term_insurers=include_short_term_insurers,
    )


@router.get("/api/dashboard/demo-status")
def demo_status(db: Session = Depends(get_db)) -> dict:
    return DashboardService().demo_status(db)


@router.get("/api/dashboard/data-status")
def data_status(db: Session = Depends(get_db)) -> dict:
    return DashboardService().data_status(db)


@router.get("/api/dashboard/monthly-new-products")
def monthly_new_products(
    year_month: str | None = None,
    limit: int = 10,
    fallback_latest: bool = True,
    insurance_type: str | None = None,
    include_review: bool = False,
    include_excluded_policy_products: bool = False,
    random_sample: bool = True,
    db: Session = Depends(get_db),
) -> dict:
    return MonthlyNewProductService().get_monthly_new_products(
        db,
        year_month=year_month,
        limit=limit,
        fallback_latest=fallback_latest,
        insurance_type=insurance_type,
        include_review=include_review,
        include_excluded_policy_products=include_excluded_policy_products,
        random_sample=random_sample,
    )


@router.get("/api/dashboard/recent-exclusive-rights")
def recent_exclusive_rights(
    insurance_type: str | None = None,
    months_back: int = 12,
    limit: int = 10,
    include_review: bool = False,
    fallback_latest: bool = True,
    random_sample: bool = True,
    db: Session = Depends(get_db),
) -> dict:
    return ExclusiveRightService().recent_dashboard(
        db,
        insurance_type=insurance_type,
        months_back=months_back,
        limit=limit,
        include_review=include_review,
        fallback_latest=fallback_latest,
        random_sample=random_sample,
    )


@router.post("/api/dashboard/query")
def dashboard_query(request: DashboardQueryRequest, db: Session = Depends(get_db)) -> dict:
    return DashboardService().query(db, request.model_dump())


@router.post("/api/dashboard/export")
def dashboard_export(request: DashboardQueryRequest, db: Session = Depends(get_db)) -> StreamingResponse:
    workbook = DashboardService().export_comparison_workbook(db, request.model_dump())
    headers = {"Content-Disposition": 'attachment; filename="insurance_product_comparison.xlsx"'}
    return StreamingResponse(
        workbook,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )
