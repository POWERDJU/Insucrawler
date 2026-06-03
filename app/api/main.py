from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import routes_admin, routes_articles, routes_companies, routes_company_logos, routes_dashboard, routes_exclusive_rights, routes_extractions, routes_ingestion, routes_llm_runs, routes_pivots, routes_products, routes_review

app = FastAPI(title="Insurance News Intelligence MVP", version="0.1.0")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(routes_company_logos.router, tags=["company-logos"])
app.include_router(routes_dashboard.router, tags=["dashboard"])
app.include_router(routes_admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(routes_companies.router, prefix="/api/companies", tags=["companies"])
app.include_router(routes_articles.router, prefix="/api/articles", tags=["articles"])
app.include_router(routes_exclusive_rights.router, prefix="/api/exclusive-rights", tags=["exclusive-rights"])
app.include_router(routes_extractions.router, prefix="/api/extractions", tags=["extractions"])
app.include_router(routes_ingestion.router, prefix="/api/ingestion", tags=["ingestion"])
app.include_router(routes_products.router, prefix="/api/products", tags=["products"])
app.include_router(routes_pivots.router, prefix="/api/pivots", tags=["pivots"])
app.include_router(routes_review.router, prefix="/api/review", tags=["review"])
app.include_router(routes_llm_runs.router, prefix="/api/llm-runs", tags=["llm-runs"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
