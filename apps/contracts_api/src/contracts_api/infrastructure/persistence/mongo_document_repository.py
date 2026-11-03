from __future__ import annotations

from typing import Any

from contracts_api.domain.document import ContractDocument
from contracts_api.infrastructure.persistence.mongo_codec import as_datetime
from motor.motor_asyncio import AsyncIOMotorDatabase


class MongoContractDocumentRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._collection = db["documents"]
        self._indexes_ready = False

    async def _ensure_indexes(self) -> None:
        if self._indexes_ready:
            return
        await self._collection.create_index("id", unique=True)
        await self._collection.create_index([("contractId", 1), ("createdAt", -1)])
        self._indexes_ready = True

    async def save(self, document: ContractDocument) -> None:
        await self._ensure_indexes()
        await self._collection.update_one(
            {"id": document.id},
            {"$set": _to_doc(document)},
            upsert=True,
        )

    async def find_by_id(self, document_id: str) -> ContractDocument | None:
        await self._ensure_indexes()
        doc = await self._collection.find_one({"id": document_id})
        return _to_domain(doc) if doc else None

    async def list_by_contract(self, contract_id: str) -> list[ContractDocument]:
        await self._ensure_indexes()
        cursor = self._collection.find({"contractId": contract_id}).sort("createdAt", -1)
        docs = await cursor.to_list(length=500)
        return [_to_domain(doc) for doc in docs]


def _to_doc(document: ContractDocument) -> dict[str, Any]:
    return {
        "id": document.id,
        "contractId": document.contract_id,
        "householdId": document.household_id,
        "ownerId": document.owner_id,
        "role": document.role,
        "fileName": document.file_name,
        "contentType": document.content_type,
        "sizeBytes": document.size_bytes,
        "storageKey": document.storage_key,
        "createdAt": document.created_at,
    }


def _to_domain(doc: dict[str, Any]) -> ContractDocument:
    return ContractDocument(
        id=doc["id"],
        contract_id=doc["contractId"],
        household_id=doc["householdId"],
        owner_id=doc["ownerId"],
        role=doc["role"],
        file_name=doc["fileName"],
        content_type=doc["contentType"],
        size_bytes=int(doc["sizeBytes"]),
        storage_key=doc["storageKey"],
        created_at=as_datetime(doc["createdAt"]),
    )
