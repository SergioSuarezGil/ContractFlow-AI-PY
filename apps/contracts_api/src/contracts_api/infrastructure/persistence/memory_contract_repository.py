from contracts_api.domain.errors import NotFoundError, ValidationError
from contracts_api.domain.service_contract import ServiceContract


class InMemoryServiceContractRepository:
    def __init__(self) -> None:
        self._items: dict[str, ServiceContract] = {}

    async def save(self, contract: ServiceContract) -> None:
        self._items[contract.id] = contract.snapshot()

    async def find_by_id(self, contract_id: str) -> ServiceContract | None:
        found = self._items.get(contract_id)
        return found.snapshot() if found else None

    async def list_by_household(
        self, household_id: str, owner_id: str
    ) -> list[ServiceContract]:
        matches = [
            item.snapshot()
            for item in self._items.values()
            if item.household_id == household_id and item.owner_id == owner_id
        ]
        matches.sort(key=lambda c: c.updated_at, reverse=True)
        return matches

    async def attach_document_id(
        self, contract_id: str, document_id: str, role: str
    ) -> None:
        contract = self._items.get(contract_id)
        if contract is None:
            raise NotFoundError(f"Contract not found: {contract_id}")
        if role not in {"current", "proposal"}:
            raise ValidationError(f"Invalid document role: {role}")
        contract.attach_document(document_id, role)  # type: ignore[arg-type]
        self._items[contract_id] = contract.snapshot()

    def clear(self) -> None:
        self._items.clear()
