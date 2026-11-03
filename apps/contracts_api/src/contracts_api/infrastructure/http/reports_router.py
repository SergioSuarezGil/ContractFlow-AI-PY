from typing import Annotated

from contracts_api.application.actor import ActorContext
from contracts_api.application.reports_service import ReportsService
from contracts_api.deps import get_reports_service
from contracts_api.infrastructure.auth.deps import get_actor
from contracts_api.infrastructure.http.schemas import ReportResponse
from fastapi import APIRouter, Depends
from fastapi.responses import Response

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(
    report_id: str,
    actor: Annotated[ActorContext, Depends(get_actor)],
    service: Annotated[ReportsService, Depends(get_reports_service)],
) -> ReportResponse:
    report = await service.get_for_actor(actor, report_id)
    return ReportResponse(
        id=report.id,
        job_id=report.job_id,
        contract_id=report.contract_id,
        file_name=report.file_name,
        created_at=report.created_at,
    )


@router.get("/{report_id}/download")
async def download_report(
    report_id: str,
    actor: Annotated[ActorContext, Depends(get_actor)],
    service: Annotated[ReportsService, Depends(get_reports_service)],
) -> Response:
    report, body = await service.download_for_actor(actor, report_id)
    return Response(
        content=body,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{report.file_name}"'},
    )
