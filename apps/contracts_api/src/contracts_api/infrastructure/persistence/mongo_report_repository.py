from __future__ import annotations

from typing import Any

from contracts_api.domain.report import Report
from contracts_api.infrastructure.persistence.mongo_codec import as_datetime
from motor.motor_asyncio import AsyncIOMotorDatabase


class MongoReportRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._collection = db["reports"]
        self._indexes_ready = False

    async def _ensure_indexes(self) -> None:
        if self._indexes_ready:
            return
        await self._collection.create_index("id", unique=True)
        await self._collection.create_index("jobId", unique=True)
        self._indexes_ready = True

    async def save(self, report: Report) -> None:
        await self._ensure_indexes()
        await self._collection.update_one(
            {"id": report.id},
            {"$set": _to_doc(report)},
            upsert=True,
        )

    async def find_by_id(self, report_id: str) -> Report | None:
        await self._ensure_indexes()
        doc = await self._collection.find_one({"id": report_id})
        return _to_domain(doc) if doc else None


def _to_doc(report: Report) -> dict[str, Any]:
    return {
        "id": report.id,
        "jobId": report.job_id,
        "contractId": report.contract_id,
        "householdId": report.household_id,
        "ownerId": report.owner_id,
        "comparisonId": report.comparison_id,
        "storageKey": report.storage_key,
        "fileName": report.file_name,
        "contentType": report.content_type,
        "sizeBytes": report.size_bytes,
        "createdAt": report.created_at,
    }


def _to_domain(doc: dict[str, Any]) -> Report:
    return Report(
        id=doc["id"],
        job_id=doc["jobId"],
        contract_id=doc["contractId"],
        owner_id=doc["ownerId"],
        household_id=doc["householdId"],
        comparison_id=doc["comparisonId"],
        storage_key=doc["storageKey"],
        file_name=doc["fileName"],
        content_type=doc["contentType"],
        size_bytes=int(doc["sizeBytes"]),
        created_at=as_datetime(doc["createdAt"]),
    )
