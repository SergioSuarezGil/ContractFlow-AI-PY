from contracts_api.domain.document import ContractDocument


class InMemoryContractDocumentRepository:
    def __init__(self) -> None:
        self._items: dict[str, ContractDocument] = {}

    async def save(self, document: ContractDocument) -> None:
        self._items[document.id] = document.snapshot()

    async def find_by_id(self, document_id: str) -> ContractDocument | None:
        found = self._items.get(document_id)
        return found.snapshot() if found else None

    async def list_by_contract(self, contract_id: str) -> list[ContractDocument]:
        return [
            item.snapshot()
            for item in self._items.values()
            if item.contract_id == contract_id
        ]

    def clear(self) -> None:
        self._items.clear()
