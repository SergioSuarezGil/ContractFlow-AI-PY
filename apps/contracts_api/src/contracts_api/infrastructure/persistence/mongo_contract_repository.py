from __future__ import annotations

from datetime import datetime
from typing import Any

from contracts_api.domain.service_contract import ServiceContract
from motor.motor_asyncio import AsyncIOMotorDatabase


class MongoServiceContractRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._collection = db["contracts"]

    async def save(self, contract: ServiceContract) -> None:
        snap = contract.snapshot()
        doc = {
            "id": snap.id,
            "householdId": snap.household_id,
            "ownerId": snap.owner_id,
            "serviceType": snap.service_type,
            "providerName": snap.provider_name,
            "title": snap.title,
            "notes": snap.notes,
            "status": snap.status,
            "currentDocumentIds": list(snap.current_document_ids),
            "proposalDocumentIds": list(snap.proposal_document_ids),
            "createdAt": snap.created_at,
            "updatedAt": snap.updated_at,
            "version": snap.version,
        }
        await self._collection.update_one({"id": snap.id}, {"$set": doc}, upsert=True)

    async def find_by_id(self, contract_id: str) -> ServiceContract | None:
        doc = await self._collection.find_one({"id": contract_id})
        return self._to_domain(doc) if doc else None

    async def list_by_household(
        self, household_id: str, owner_id: str
    ) -> list[ServiceContract]:
        cursor = self._collection.find(
            {"householdId": household_id, "ownerId": owner_id}
        ).sort("updatedAt", -1)
        return [self._to_domain(doc) async for doc in cursor]

    async def attach_document_id(
        self, contract_id: str, document_id: str, role: str
    ) -> None:
        contract = await self.find_by_id(contract_id)
        if contract is None:
            from contracts_api.domain.errors import NotFoundError

            raise NotFoundError(f"Contract not found: {contract_id}")
        contract.attach_document(document_id, role)  # type: ignore[arg-type]
        await self.save(contract)

    def _to_domain(self, doc: dict[str, Any]) -> ServiceContract:
        created = doc["createdAt"]
        updated = doc["updatedAt"]
        if isinstance(created, str):
            created = datetime.fromisoformat(created.replace("Z", "+00:00"))
        if isinstance(updated, str):
            updated = datetime.fromisoformat(updated.replace("Z", "+00:00"))
        return ServiceContract(
            id=doc["id"],
            household_id=doc["householdId"],
            owner_id=doc["ownerId"],
            service_type=doc["serviceType"],
            provider_name=doc["providerName"],
            title=doc["title"],
            notes=doc.get("notes", ""),
            status=doc["status"],
            current_document_ids=list(doc.get("currentDocumentIds", [])),
            proposal_document_ids=list(doc.get("proposalDocumentIds", [])),
            created_at=created,
            updated_at=updated,
            version=int(doc.get("version", 1)),
        )
