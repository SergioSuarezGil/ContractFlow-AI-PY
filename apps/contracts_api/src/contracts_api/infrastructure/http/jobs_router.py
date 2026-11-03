from typing import Annotated

from contracts_api.application.actor import ActorContext
from contracts_api.application.jobs_service import JobsService
from contracts_api.application.reports_service import ReportsService
from contracts_api.application.worker_comparison import WorkerComparisonService
from contracts_api.deps import (
    get_job_repository,
    get_jobs_service,
    get_reports_service,
    lookup_worker_comparison,
)
from contracts_api.infrastructure.auth.deps import get_actor
from contracts_api.infrastructure.http.schemas import JobResponse
from fastapi import APIRouter, Depends
from fastapi.responses import Response

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    actor: Annotated[ActorContext, Depends(get_actor)],
    service: Annotated[JobsService, Depends(get_jobs_service)],
) -> JobResponse:
    job = await service.get(actor, job_id)
    return JobResponse(
        id=job.id,
        type=job.job_type,
        status=job.status,
        contract_id=job.contract_id,
        household_id=job.household_id,
        owner_id=job.owner_id,
        correlation_id=job.correlation_id,
        comparison_id=job.comparison_id,
        report_id=job.report_id,
        error_message=job.error_message,
        version=job.version,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def get_worker_comparison_service() -> WorkerComparisonService:
    return WorkerComparisonService(get_job_repository(), lookup_worker_comparison)


@router.get("/{job_id}/worker-comparison")
async def get_worker_comparison(
    job_id: str,
    actor: Annotated[ActorContext, Depends(get_actor)],
    service: Annotated[WorkerComparisonService, Depends(get_worker_comparison_service)],
) -> dict:
    return await service.get(actor, job_id)


@router.get("/{job_id}/report")
async def get_job_report(
    job_id: str,
    actor: Annotated[ActorContext, Depends(get_actor)],
    service: Annotated[ReportsService, Depends(get_reports_service)],
) -> Response:
    report, body = await service.get_pdf_for_job(actor, job_id)
    return Response(
        content=body,
        media_type=report.content_type or "application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{report.file_name}"',
        },
    )
