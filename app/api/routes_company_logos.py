from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.services.company_logo_service import CompanyLogoService

router = APIRouter()


@router.get("/api/company-logos")
def company_logo(
    company_name: str = Query(...),
    insurance_type: str | None = None,
) -> dict:
    service = CompanyLogoService()
    logo_url = service.get_logo_url(company_name, insurance_type)
    return {
        "company_name": company_name,
        "insurance_type": insurance_type,
        "logo_url": logo_url,
        "found": bool(logo_url),
    }


@router.get("/api/company-logos/file/{bucket}/{filename}")
def company_logo_file(bucket: str, filename: str) -> FileResponse:
    path = CompanyLogoService().get_logo_file(bucket, filename)
    if path is None:
        raise HTTPException(status_code=404, detail="Company logo not found")
    return FileResponse(path)
