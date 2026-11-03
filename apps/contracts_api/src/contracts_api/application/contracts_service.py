from __future__ import annotations

from uuid import uuid4

from contracts_api.application.actor import ActorContext
from contracts_api.application.ports import ServiceContractRepository
from contracts_api.domain.errors import NotFoundError
from contracts_api.domain.service_contract import ServiceContract


class ContractsService:
    def __init__(self, repository: ServiceContractRepository) -> None:
        self._repository = repository

    async def create(
        self,
        actor: ActorContext,
        *,
        service_type: str,
        provider_name: str,
        title: str,
        notes: str = "",
    ) -> ServiceContract:
        contract = ServiceContract.create(
            id=str(uuid4()),
            household_id=actor.household_id,
            owner_id=actor.owner_id,
            service_type=service_type,
            provider_name=provider_name,
            title=title,
            notes=notes,
        )
        await self._repository.save(contract)
        return contract.snapshot()

    async def list(self, actor: ActorContext) -> list[ServiceContract]:
        items = await self._repository.list_by_household(
            actor.household_id, actor.owner_id
        )
        return [item.snapshot() for item in items]

    async def get(self, actor: ActorContext, contract_id: str) -> ServiceContract:
        contract = await self._require_owned(actor, contract_id)
        return contract.snapshot()

    async def update(
        self,
        actor: ActorContext,
        contract_id: str,
        *,
        title: str | None = None,
        provider_name: str | None = None,
        notes: str | None = None,
        service_type: str | None = None,
        status: str | None = None,
    ) -> ServiceContract:
        contract = await self._require_owned(actor, contract_id)
        contract.update_details(
            title=title,
            provider_name=provider_name,
            notes=notes,
            service_type=service_type,
            status=status,
        )
        await self._repository.save(contract)
        return contract.snapshot()

    async def archive(self, actor: ActorContext, contract_id: str) -> ServiceContract:
        contract = await self._require_owned(actor, contract_id)
        contract.archive()
        await self._repository.save(contract)
        return contract.snapshot()

    async def _require_owned(
        self, actor: ActorContext, contract_id: str
    ) -> ServiceContract:
        contract = await self._repository.find_by_id(contract_id)
        if contract is None or not contract.belongs_to(
            actor.owner_id, actor.household_id
        ):
            raise NotFoundError(f"Contract not found: {contract_id}")
        return contract
