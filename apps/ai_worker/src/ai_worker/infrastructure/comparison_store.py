from __future__ import annotations

from typing import Any, Protocol

from pymongo.errors import DuplicateKeyError


class ComparisonStore(Protocol):
    async def insert(self, document: dict[str, Any]) -> bool: ...

    async def find_by_job_id(self, job_id: str) -> dict[str, Any] | None: ...


class InMemoryComparisonStore:
    def __init__(self) -> None:
        self._items: dict[str, dict[str, Any]] = {}

    async def insert(self, document: dict[str, Any]) -> bool:
        job_id = str(document.get("jobId") or "")
        if not job_id or job_id in self._items:
            return False
        self._items[job_id] = dict(document)
        return True

    async def find_by_job_id(self, job_id: str) -> dict[str, Any] | None:
        found = self._items.get(job_id)
        return dict(found) if found else None


class MongoComparisonStore:
    def __init__(self, db: Any) -> None:
        self._collection = db["comparisons"]
        self._indexes_ready = False

    async def _ensure_indexes(self) -> None:
        if self._indexes_ready:
            return
        await self._collection.create_index("jobId", unique=True)
        await self._collection.create_index("id", unique=True)
        self._indexes_ready = True

    async def insert(self, document: dict[str, Any]) -> bool:
        await self._ensure_indexes()
        try:
            await self._collection.insert_one(dict(document))
        except DuplicateKeyError:
            return False
        return True

    async def find_by_job_id(self, job_id: str) -> dict[str, Any] | None:
        await self._ensure_indexes()
        doc = await self._collection.find_one({"jobId": job_id})
        if doc is None:
            return None
        return {
            "id": doc.get("id"),
            "jobId": doc.get("jobId"),
            "contractId": doc.get("contractId"),
            "verdict": doc.get("verdict"),
            "summary": doc.get("summary"),
            "createdAt": doc.get("createdAt"),
        }


def empty_lookup(job_id: str) -> dict[str, str | bool]:
    return {
        "found": False,
        "jobId": job_id,
        "comparisonId": "",
        "contractId": "",
        "verdict": "",
        "summary": "",
        "createdAt": "",
    }


def lookup_view(job_id: str, doc: dict[str, Any] | None) -> dict[str, str | bool]:
    if not doc:
        return empty_lookup(job_id)
    return {
        "found": True,
        "jobId": str(doc.get("jobId") or job_id),
        "comparisonId": str(doc.get("id") or ""),
        "contractId": str(doc.get("contractId") or ""),
        "verdict": str(doc.get("verdict") or ""),
        "summary": str(doc.get("summary") or ""),
        "createdAt": str(doc.get("createdAt") or ""),
    }
