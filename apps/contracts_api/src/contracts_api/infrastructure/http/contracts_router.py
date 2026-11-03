from typing import Annotated

from contracts_api.application.actor import ActorContext
from contracts_api.application.contracts_service import ContractsService
from contracts_api.deps import get_contracts_service
from contracts_api.domain.service_contract import ServiceContract
from contracts_api.infrastructure.auth.deps import get_actor
from contracts_api.infrastructure.http.schemas import (
    ContractResponse,
    CreateContractRequest,
    UpdateContractRequest,
)
from fastapi import APIRouter, Depends, status

router = APIRouter(prefix="/api/v1/contracts", tags=["contracts"])


def _to_response(contract: ServiceContract) -> ContractResponse:
    return ContractResponse(
        id=contract.id,
        household_id=contract.household_id,
        owner_id=contract.owner_id,
        service_type=contract.service_type,
        provider_name=contract.provider_name,
        title=contract.title,
        notes=contract.notes,
        status=contract.status,
        current_document_ids=list(contract.current_document_ids),
        proposal_document_ids=list(contract.proposal_document_ids),
        created_at=contract.created_at,
        updated_at=contract.updated_at,
        version=contract.version,
    )


@router.post("", response_model=ContractResponse, status_code=status.HTTP_201_CREATED)
async def create_contract(
    body: CreateContractRequest,
    actor: Annotated[ActorContext, Depends(get_actor)],
    service: Annotated[ContractsService, Depends(get_contracts_service)],
) -> ContractResponse:
    contract = await service.create(
        actor,
        service_type=body.service_type,
        provider_name=body.provider_name,
        title=body.title,
        notes=body.notes or "",
    )
    return _to_response(contract)


@router.get("", response_model=list[ContractResponse])
async def list_contracts(
    actor: Annotated[ActorContext, Depends(get_actor)],
    service: Annotated[ContractsService, Depends(get_contracts_service)],
) -> list[ContractResponse]:
    items = await service.list(actor)
    return [_to_response(item) for item in items]


@router.get("/{contract_id}", response_model=ContractResponse)
async def get_contract(
    contract_id: str,
    actor: Annotated[ActorContext, Depends(get_actor)],
    service: Annotated[ContractsService, Depends(get_contracts_service)],
) -> ContractResponse:
    contract = await service.get(actor, contract_id)
    return _to_response(contract)


@router.patch("/{contract_id}", response_model=ContractResponse)
async def update_contract(
    contract_id: str,
    body: UpdateContractRequest,
    actor: Annotated[ActorContext, Depends(get_actor)],
    service: Annotated[ContractsService, Depends(get_contracts_service)],
) -> ContractResponse:
    contract = await service.update(
        actor,
        contract_id,
        title=body.title,
        provider_name=body.provider_name,
        notes=body.notes,
        service_type=body.service_type,
        status=body.status,
    )
    return _to_response(contract)


@router.delete("/{contract_id}", response_model=ContractResponse)
async def archive_contract(
    contract_id: str,
    actor: Annotated[ActorContext, Depends(get_actor)],
    service: Annotated[ContractsService, Depends(get_contracts_service)],
) -> ContractResponse:
    contract = await service.archive(actor, contract_id)
    return _to_response(contract)
