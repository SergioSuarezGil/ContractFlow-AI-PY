from __future__ import annotations

import logging
from typing import Any

from contracts_api.domain.errors import ConflictError
from contracts_api.domain.job import Job, OutboxEvent
from contracts_api.infrastructure.persistence.mongo_codec import as_datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

logger = logging.getLogger(__name__)


class MongoJobRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._collection = db["jobs"]
        self._indexes_ready = False

    async def _ensure_indexes(self) -> None:
        if self._indexes_ready:
            return
        await self._collection.create_index("id", unique=True)
        await self._collection.create_index(
            [("outbox.publishedAt", 1), ("status", 1), ("updatedAt", 1)]
        )
        self._indexes_ready = True

    async def save(self, job: Job) -> None:
        await self._ensure_indexes()
        doc = _to_doc(job)
        if job.version == 0:
            try:
                await self._collection.insert_one(doc)
            except DuplicateKeyError as exc:
                raise ConflictError(f"Job concurrent update conflict: {job.id}") from exc
            return

        expected = job.version - 1
        result = await self._collection.update_one(
            {"id": job.id, "version": expected},
            {"$set": doc},
        )
        if result.matched_count == 0:
            logger.warning("Optimistic lock failed for job %s version %s", job.id, expected)
            raise ConflictError(f"Job concurrent update conflict: {job.id}")

    async def find_by_id(self, job_id: str) -> Job | None:
        await self._ensure_indexes()
        doc = await self._collection.find_one({"id": job_id})
        return _to_domain(doc) if doc else None

    async def find_pending_outbox(self, limit: int) -> list[Job]:
        await self._ensure_indexes()
        cursor = (
            self._collection.find(
                {
                    "outbox.publishedAt": None,
                    "outbox": {"$ne": None},
                    "status": {"$in": ["PENDING", "PROCESSING"]},
                }
            )
            .sort("updatedAt", 1)
            .limit(limit)
        )
        docs = await cursor.to_list(length=limit)
        return [_to_domain(doc) for doc in docs]


def _to_doc(job: Job) -> dict[str, Any]:
    outbox = None
    if job.outbox is not None:
        outbox = {
            "routingKey": job.outbox.routing_key,
            "envelope": dict(job.outbox.envelope),
            "publishedAt": job.outbox.published_at,
        }
    return {
        "id": job.id,
        "type": job.job_type,
        "status": job.status,
        "contractId": job.contract_id,
        "householdId": job.household_id,
        "ownerId": job.owner_id,
        "correlationId": job.correlation_id,
        "comparisonId": job.comparison_id,
        "reportId": job.report_id,
        "errorMessage": job.error_message,
        "version": job.version,
        "outbox": outbox,
        "createdAt": job.created_at,
        "updatedAt": job.updated_at,
    }


def _to_domain(doc: dict[str, Any]) -> Job:
    raw_outbox = doc.get("outbox")
    outbox = None
    if isinstance(raw_outbox, dict):
        outbox = OutboxEvent(
            routing_key=str(raw_outbox.get("routingKey") or ""),
            envelope=dict(raw_outbox.get("envelope") or {}),
            published_at=raw_outbox.get("publishedAt"),
        )
    return Job(
        id=doc["id"],
        contract_id=doc["contractId"],
        household_id=doc["householdId"],
        owner_id=doc["ownerId"],
        correlation_id=doc["correlationId"],
        status=doc["status"],
        job_type=doc.get("type") or "COMPARE_PROPOSALS",
        comparison_id=doc.get("comparisonId"),
        report_id=doc.get("reportId"),
        error_message=doc.get("errorMessage"),
        version=int(doc.get("version") or 0),
        outbox=outbox,
        created_at=as_datetime(doc["createdAt"]),
        updated_at=as_datetime(doc["updatedAt"]),
    )
