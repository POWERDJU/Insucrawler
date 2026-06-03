from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import FactLLMBatchJob
from app.collectors.naver_news_client import NaverNewsClient
from app.schemas.admin import (
    AdminAuthRequest,
    CrawlIncrementalRequest,
    CrawlJobRunRequest,
    CrawlManualRangeRequest,
    ExclusiveRightConsolidateRequest,
    ExclusiveRightExtractPendingRequest,
    LLMConsolidationReviewRequest,
    LLMBatchCreateRequest,
    NaverNewsSearchPreviewRequest,
    ProductConsolidationManualMergeRequest,
    ProductConsolidationRejectMergeRequest,
    ProductConsolidationRunRequest,
)
from app.services.admin_auth_service import AdminAuthService
from app.services.batch_llm_service import BatchLLMService
from app.services.crawl_job_service import CrawlJobService
from app.services.llm_cost_service import LLMCostService
from app.services.llm_execution_guard_service import LLMExecutionGuardService
from app.services.llm_savings_service import LLMSavingsService
from app.services.product_consolidation_service import ProductConsolidationService
from app.services.product_duplicate_guard_service import ProductDuplicateGuardService
from app.services.product_full_list_consolidation_service import ProductFullListConsolidationService
from app.services.exclusive_right_consolidation_service import ExclusiveRightConsolidationService
from app.services.exclusive_right_llm_consolidation_service import ExclusiveRightLLMConsolidationService
from app.services.exclusive_right_service import ExclusiveRightService

router = APIRouter()


def require_admin_token(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Admin token required")
    token = authorization.removeprefix("Bearer ").strip()
    if not AdminAuthService().validate_token(token):
        raise HTTPException(status_code=401, detail="Invalid or expired admin token")
    return token


@router.post("/auth")
def admin_auth(request: AdminAuthRequest) -> dict:
    token = AdminAuthService().create_token(request.password)
    if not token.get("ok"):
        raise HTTPException(status_code=401, detail="Invalid admin password")
    return token


@router.post("/crawl-jobs/test-2026-01")
def create_test_crawl_job(
    request_body: CrawlJobRunRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin_token),
) -> dict:
    service = CrawlJobService()
    job = service.create_test_2026_01(
        db,
        include_llm_extraction=request_body.include_llm_extraction,
        extraction_mode=request_body.extraction_mode,
        include_exclusive_right_pipeline=request_body.include_exclusive_right_pipeline,
        exclusive_right_pipeline_mode=request_body.exclusive_right_pipeline_mode,
        exclusive_right_auto_submit_batch=request_body.exclusive_right_auto_submit_batch,
        exclusive_right_auto_import_when_completed=request_body.exclusive_right_auto_import_when_completed,
        exclusive_right_auto_consolidate=request_body.exclusive_right_auto_consolidate,
        exclusive_right_limit=request_body.exclusive_right_limit,
        include_reinsurers=request_body.include_reinsurers,
        include_foreign_branches=request_body.include_foreign_branches,
        requested_by="admin",
        requested_from=request.client.host if request.client else None,
    )
    background_tasks.add_task(service.run_job_by_id, job.crawl_job_id)
    return {
        "crawl_job_id": job.crawl_job_id,
        "status": job.status,
        "exclusive_right_pipeline_requested": job.include_exclusive_right_pipeline,
        "exclusive_right_pipeline_mode": job.exclusive_right_pipeline_mode,
    }


@router.post("/crawl-jobs/backfill-2024-2026-05")
def create_backfill_crawl_job(
    request_body: CrawlJobRunRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin_token),
) -> dict:
    service = CrawlJobService()
    job = service.create_backfill_2024_2026_05(
        db,
        include_llm_extraction=request_body.include_llm_extraction,
        extraction_mode=request_body.extraction_mode,
        include_exclusive_right_pipeline=request_body.include_exclusive_right_pipeline,
        exclusive_right_pipeline_mode=request_body.exclusive_right_pipeline_mode,
        exclusive_right_auto_submit_batch=request_body.exclusive_right_auto_submit_batch,
        exclusive_right_auto_import_when_completed=request_body.exclusive_right_auto_import_when_completed,
        exclusive_right_auto_consolidate=request_body.exclusive_right_auto_consolidate,
        exclusive_right_limit=request_body.exclusive_right_limit,
        include_reinsurers=request_body.include_reinsurers,
        include_foreign_branches=request_body.include_foreign_branches,
        requested_by="admin",
        requested_from=request.client.host if request.client else None,
    )
    background_tasks.add_task(service.run_job_by_id, job.crawl_job_id)
    return {
        "crawl_job_id": job.crawl_job_id,
        "status": job.status,
        "exclusive_right_pipeline_requested": job.include_exclusive_right_pipeline,
        "exclusive_right_pipeline_mode": job.exclusive_right_pipeline_mode,
    }


@router.post("/crawl-jobs/incremental")
def create_incremental_crawl_job(
    request_body: CrawlIncrementalRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin_token),
) -> dict:
    service = CrawlJobService()
    job = service.create_incremental(
        db,
        days_back=request_body.days_back,
        include_llm_extraction=request_body.include_llm_extraction,
        extraction_mode=request_body.extraction_mode,
        include_exclusive_right_pipeline=request_body.include_exclusive_right_pipeline,
        exclusive_right_pipeline_mode=request_body.exclusive_right_pipeline_mode,
        exclusive_right_auto_submit_batch=request_body.exclusive_right_auto_submit_batch,
        exclusive_right_auto_import_when_completed=request_body.exclusive_right_auto_import_when_completed,
        exclusive_right_auto_consolidate=request_body.exclusive_right_auto_consolidate,
        exclusive_right_limit=request_body.exclusive_right_limit,
        include_reinsurers=request_body.include_reinsurers,
        include_foreign_branches=request_body.include_foreign_branches,
        requested_by="admin",
        requested_from=request.client.host if request.client else None,
    )
    background_tasks.add_task(service.run_job_by_id, job.crawl_job_id)
    return {
        "crawl_job_id": job.crawl_job_id,
        "status": job.status,
        "exclusive_right_pipeline_requested": job.include_exclusive_right_pipeline,
        "exclusive_right_pipeline_mode": job.exclusive_right_pipeline_mode,
    }


@router.post("/crawl-jobs/manual-range")
def create_manual_range_crawl_job(
    request_body: CrawlManualRangeRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin_token),
) -> dict:
    service = CrawlJobService()
    job = service.create_manual_range(
        db,
        date_from=request_body.date_from,
        date_to=request_body.date_to,
        include_llm_extraction=request_body.include_llm_extraction,
        extraction_mode=request_body.extraction_mode,
        include_exclusive_right_pipeline=request_body.include_exclusive_right_pipeline,
        exclusive_right_pipeline_mode=request_body.exclusive_right_pipeline_mode,
        exclusive_right_auto_submit_batch=request_body.exclusive_right_auto_submit_batch,
        exclusive_right_auto_import_when_completed=request_body.exclusive_right_auto_import_when_completed,
        exclusive_right_auto_consolidate=request_body.exclusive_right_auto_consolidate,
        exclusive_right_limit=request_body.exclusive_right_limit,
        include_reinsurers=request_body.include_reinsurers,
        include_foreign_branches=request_body.include_foreign_branches,
        requested_by="admin",
        requested_from=request.client.host if request.client else None,
    )
    background_tasks.add_task(service.run_job_by_id, job.crawl_job_id)
    return {
        "crawl_job_id": job.crawl_job_id,
        "status": job.status,
        "exclusive_right_pipeline_requested": job.include_exclusive_right_pipeline,
        "exclusive_right_pipeline_mode": job.exclusive_right_pipeline_mode,
    }


@router.get("/crawl-jobs")
def list_crawl_jobs(
    db: Session = Depends(get_db),
    _: str = Depends(require_admin_token),
) -> list[dict]:
    return CrawlJobService().list_jobs(db)


@router.get("/llm-cost-summary")
def llm_cost_summary(
    date_from: str | None = None,
    date_to: str | None = None,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin_token),
) -> dict:
    return LLMCostService().summary(db, date_from=date_from, date_to=date_to)


@router.get("/llm-cost-savings-summary")
def llm_cost_savings_summary(
    date_from: str | None = None,
    date_to: str | None = None,
    baseline_policy: str = "all_articles_fulltext_extract_and_verify",
    include_breakdown: bool = True,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin_token),
) -> dict:
    return LLMSavingsService().get_savings_summary(
        db,
        date_from=date_from,
        date_to=date_to,
        baseline_policy=baseline_policy,
        include_breakdown=include_breakdown,
    )


@router.get("/llm-execution-guard-summary")
def llm_execution_guard_summary(
    db: Session = Depends(get_db),
    _: str = Depends(require_admin_token),
) -> dict:
    return LLMExecutionGuardService().summary(db)


@router.post("/exclusive-rights/extract-pending")
def extract_pending_exclusive_rights(
    request_body: ExclusiveRightExtractPendingRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin_token),
) -> dict:
    try:
        return ExclusiveRightService().extract_pending(
            db,
            limit=request_body.limit,
            mode=request_body.mode,
            date_from=request_body.date_from,
            date_to=request_body.date_to,
            crawl_job_id=request_body.crawl_job_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/exclusive-rights/extract-queue-status")
def exclusive_right_extract_queue_status(
    crawl_job_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin_token),
) -> dict:
    return ExclusiveRightService().queue_status(db, crawl_job_id=crawl_job_id, date_from=date_from, date_to=date_to)


@router.post("/exclusive-rights/consolidate")
def consolidate_exclusive_rights(
    request_body: ExclusiveRightConsolidateRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin_token),
) -> dict:
    return ExclusiveRightConsolidationService().run(
        db,
        mode=request_body.mode,
        crawl_job_id=request_body.crawl_job_id,
        date_from=request_body.date_from,
        date_to=request_body.date_to,
    )


@router.post("/llm-batch-jobs/create")
def create_llm_batch_job(
    request_body: LLMBatchCreateRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin_token),
) -> dict:
    job = BatchLLMService().create_from_pending_queue(
        db,
        task_type=request_body.task_type,
        provider=request_body.provider,
        model_name=request_body.model_name,
        limit=request_body.limit,
        submit=request_body.submit,
        crawl_job_id=request_body.crawl_job_id,
    )
    db.commit()
    return BatchLLMService().get_job_detail(db, job.llm_batch_job_id)


@router.post("/llm-batch-jobs/{batch_job_id}/submit")
def submit_llm_batch_job(
    batch_job_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin_token),
) -> dict:
    job = db.get(FactLLMBatchJob, batch_job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Batch job not found")
    BatchLLMService().submit_batch(db, job)
    db.commit()
    return BatchLLMService().get_job_detail(db, batch_job_id)


@router.get("/llm-batch-jobs")
def list_llm_batch_jobs(
    task_type: str = "extract",
    db: Session = Depends(get_db),
    _: str = Depends(require_admin_token),
) -> dict:
    service = BatchLLMService()
    return {
        "pending_batch_eligible_count": service.pending_batch_eligible_count(db, task_type=task_type),
        "jobs": service.list_jobs(db),
    }


@router.get("/llm-batch-jobs/{batch_job_id}")
def get_llm_batch_job(
    batch_job_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin_token),
) -> dict:
    try:
        return BatchLLMService().get_job_detail(db, batch_job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/llm-batch-jobs/{batch_job_id}/refresh-status")
def refresh_llm_batch_job_status(
    batch_job_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin_token),
) -> dict:
    job = db.get(FactLLMBatchJob, batch_job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Batch job not found")
    BatchLLMService().refresh_status(db, job)
    db.commit()
    return BatchLLMService().get_job_detail(db, batch_job_id)


@router.post("/llm-batch-jobs/{batch_job_id}/import-results")
def import_llm_batch_job_results(
    batch_job_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin_token),
) -> dict:
    job = db.get(FactLLMBatchJob, batch_job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Batch job not found")
    result = BatchLLMService().import_results(db, job)
    db.commit()
    return {"result": result, "job": BatchLLMService().get_job_detail(db, batch_job_id)}


@router.post("/product-consolidation/run")
def run_product_consolidation(
    request_body: ProductConsolidationRunRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin_token),
) -> dict:
    return ProductConsolidationService().run(
        db,
        mode=request_body.mode,
        target=request_body.target,
        limit=request_body.limit,
        trigger_type="manual",
        use_llm_for_gray_blocks=request_body.use_llm_for_gray_blocks,
    )


@router.post("/product-consolidation/llm-review")
def run_product_llm_consolidation_review(
    request_body: LLMConsolidationReviewRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin_token),
) -> dict:
    try:
        return ProductFullListConsolidationService().run_full_list_consolidation(
            db,
            mode=request_body.mode,
            target="all" if request_body.target == "company" else request_body.target,
            company_name=request_body.company_name,
            limit=request_body.limit,
            max_companies=request_body.max_companies,
            max_blocks=request_body.max_blocks,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/exclusive-rights/llm-consolidation-review")
def run_exclusive_right_llm_consolidation_review(
    request_body: LLMConsolidationReviewRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin_token),
) -> dict:
    try:
        return ExclusiveRightLLMConsolidationService().run(
            db,
            mode=request_body.mode,
            target=request_body.target,
            limit=request_body.limit,
            max_blocks=request_body.max_blocks,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/product-consolidation/jobs")
def list_product_consolidation_jobs(
    db: Session = Depends(get_db),
    _: str = Depends(require_admin_token),
) -> list[dict]:
    return ProductConsolidationService().list_jobs(db)


@router.get("/product-consolidation/jobs/{job_id}")
def get_product_consolidation_job(
    job_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin_token),
) -> dict:
    try:
        return ProductConsolidationService().get_job_detail(db, job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/product-consolidation/merge")
def manual_product_consolidation_merge(
    request_body: ProductConsolidationManualMergeRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin_token),
) -> dict:
    return ProductConsolidationService().manual_merge(
        db,
        canonical_product_id=request_body.canonical_product_id,
        duplicate_product_ids=request_body.duplicate_product_ids,
        reason=request_body.reason,
    )


@router.post("/product-consolidation/reject-merge")
def reject_product_consolidation_merge(
    request_body: ProductConsolidationRejectMergeRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin_token),
) -> dict:
    try:
        return ProductConsolidationService().reject_merge(db, block_id=request_body.block_id, reason=request_body.reason)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/product-consolidation/cost-summary")
def product_consolidation_cost_summary(
    db: Session = Depends(get_db),
    _: str = Depends(require_admin_token),
) -> dict:
    return ProductConsolidationService().cost_summary(db)


@router.get("/product-consolidation/duplicate-check")
def product_consolidation_duplicate_check(
    company_id: int | None = None,
    company_name: str | None = None,
    export_csv: bool = False,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin_token),
) -> dict:
    service = ProductDuplicateGuardService()
    groups = service.find_duplicate_family_groups(db, filters={"company_id": company_id, "company_name": company_name})
    summary = service.summarize_duplicate_risk(groups)
    if export_csv:
        summary["csv_path"] = str(service.export_groups_csv(groups))
    return summary


@router.get("/crawl-jobs/{crawl_job_id}")
def get_crawl_job_detail(
    crawl_job_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin_token),
) -> dict:
    try:
        return CrawlJobService().get_job_detail(db, crawl_job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/crawl-jobs/{crawl_job_id}/cancel")
def cancel_crawl_job(
    crawl_job_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin_token),
) -> dict:
    try:
        job = CrawlJobService().cancel_job(db, crawl_job_id)
        return {"crawl_job_id": job.crawl_job_id, "status": job.status}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/crawl-jobs/{crawl_job_id}/retry-failed")
def retry_failed_crawl_tasks(
    crawl_job_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin_token),
) -> dict:
    service = CrawlJobService()
    try:
        job = service.retry_failed(db, crawl_job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    background_tasks.add_task(service.run_job_by_id, job.crawl_job_id)
    return {"crawl_job_id": job.crawl_job_id, "status": job.status}


@router.post("/search-preview/naver-news")
def preview_naver_news_search(
    request_body: NaverNewsSearchPreviewRequest,
    _: str = Depends(require_admin_token),
) -> dict:
    items = NaverNewsClient().search_page(
        request_body.query,
        "admin_preview",
        display=request_body.display,
        start=request_body.start,
        sort=request_body.sort,
    )
    return {
        "query": request_body.query,
        "display": request_body.display,
        "start": request_body.start,
        "sort": request_body.sort,
        "items": [
            {
                "title": item.title,
                "description": item.description,
                "pub_date": item.pub_date.isoformat() if item.pub_date else None,
                "link": item.link,
                "original_link": item.original_link,
                "publisher": item.publisher,
                "source_api": item.source_api,
            }
            for item in items
        ],
    }
