from typing import Annotated

from contracts_api.application.actor import ActorContext
from contracts_api.application.jobs_service import JobsService
from contracts_api.deps import get_jobs_service
from contracts_api.infrastructure.auth.deps import get_actor
from contracts_api.infrastructure.http.schemas import ComparisonAcceptedResponse
from fastapi import APIRouter, Depends, status

router = APIRouter(
    prefix="/api/v1/contracts/{contract_id}/comparisons",
    tags=["comparisons"],
)


@router.post(
    "",
    response_model=ComparisonAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def request_comparison(
    contract_id: str,
    actor: Annotated[ActorContext, Depends(get_actor)],
    service: Annotated[JobsService, Depends(get_jobs_service)],
) -> ComparisonAcceptedResponse:
    result = await service.request_comparison(actor, contract_id)
    return ComparisonAcceptedResponse(
        job_id=result["jobId"],
        status=result["status"],
        correlation_id=result["correlationId"],
    )
