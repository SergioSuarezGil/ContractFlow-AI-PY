from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from contracts_api.domain.document import ContractDocument
from contracts_api.domain.errors import ConflictError
from contracts_api.domain.job import Job, OutboxEvent
from contracts_api.domain.report import Report
from contracts_api.infrastructure.persistence.mongo_document_repository import (
    MongoContractDocumentRepository,
)
from contracts_api.infrastructure.persistence.mongo_job_repository import MongoJobRepository
from contracts_api.infrastructure.persistence.mongo_report_repository import MongoReportRepository
from pymongo.errors import DuplicateKeyError


def _match(doc: dict[str, Any], filt: dict[str, Any]) -> bool:
    for key, expected in filt.items():
        if key == "outbox" and isinstance(expected, dict) and "$ne" in expected:
            if doc.get("outbox") == expected["$ne"]:
                return False
            continue
        if key == "status" and isinstance(expected, dict) and "$in" in expected:
            if doc.get("status") not in expected["$in"]:
                return False
            continue
        current: Any = doc
        for part in key.split("."):
            if not isinstance(current, dict):
                current = None
                break
            current = current.get(part)
        if current != expected:
            return False
    return True


class _Cursor:
    def __init__(self, docs: list[dict[str, Any]]) -> None:
        self._docs = docs

    def sort(self, key: str, direction: int) -> _Cursor:
        empty = datetime.min.replace(tzinfo=UTC)
        self._docs.sort(key=lambda item: item.get(key) or empty, reverse=direction < 0)
        return self

    def limit(self, count: int) -> _Cursor:
        self._docs = self._docs[:count]
        return self

    async def to_list(self, length: int | None = None) -> list[dict[str, Any]]:
        docs = self._docs if length is None else self._docs[:length]
        return [dict(doc) for doc in docs]


class _Collection:
    def __init__(self) -> None:
        self.docs: list[dict[str, Any]] = []

    async def create_index(self, *_args: Any, **_kwargs: Any) -> str:
        return "idx"

    async def insert_one(self, doc: dict[str, Any]) -> None:
        if any(item.get("id") == doc.get("id") for item in self.docs):
            raise DuplicateKeyError("E11000 duplicate key")
        self.docs.append(dict(doc))

    async def find_one(self, filt: dict[str, Any]) -> dict[str, Any] | None:
        for doc in self.docs:
            if _match(doc, filt):
                return dict(doc)
        return None

    def find(self, filt: dict[str, Any]) -> _Cursor:
        return _Cursor([dict(doc) for doc in self.docs if _match(doc, filt)])

    async def update_one(
        self, filt: dict[str, Any], update: dict[str, Any], upsert: bool = False
    ) -> SimpleNamespace:
        for doc in self.docs:
            if _match(doc, filt):
                doc.update(update["$set"])
                return SimpleNamespace(matched_count=1)
        if upsert:
            self.docs.append(dict(update["$set"]))
        return SimpleNamespace(matched_count=0)


class _DB(dict):
    def __getitem__(self, name: str) -> _Collection:
        if name not in self:
            super().__setitem__(name, _Collection())
        return super().__getitem__(name)


def test_document_and_report_roundtrip() -> None:
    db = _DB()
    documents = MongoContractDocumentRepository(db)
    reports = MongoReportRepository(db)
    now = datetime(2026, 11, 3, tzinfo=UTC)
    current = ContractDocument.create(
        id="d1",
        contract_id="c1",
        household_id="hh",
        owner_id="owner",
        role="current",
        file_name="a.txt",
        content_type="text/plain",
        size_bytes=4,
        storage_key="hh/c1/d1",
        now=now,
    )
    later = ContractDocument.create(
        id="d2",
        contract_id="c1",
        household_id="hh",
        owner_id="owner",
        role="proposal",
        file_name="b.txt",
        content_type="text/plain",
        size_bytes=4,
        storage_key="hh/c1/d2",
        now=datetime(2026, 11, 4, tzinfo=UTC),
    )

    async def _run() -> None:
        await documents.save(current)
        await documents.save(later)
        found = await documents.find_by_id("d1")
        assert found is not None and found.file_name == "a.txt"
        listed = await documents.list_by_contract("c1")
        assert [item.id for item in listed] == ["d2", "d1"]
        report = Report.create(
            id="r1",
            job_id="j1",
            contract_id="c1",
            owner_id="owner",
            household_id="hh",
            comparison_id="cmp",
            storage_key="reports/j1/r1.pdf",
            file_name="r1.pdf",
            content_type="application/pdf",
            size_bytes=10,
        )
        await reports.save(report)
        loaded = await reports.find_by_id("r1")
        assert loaded is not None and loaded.job_id == "j1"

    import asyncio

    asyncio.run(_run())


def test_job_optimistic_lock_and_outbox() -> None:
    db = _DB()
    repo = MongoJobRepository(db)
    job = Job.create(
        id="j1",
        contract_id="c1",
        household_id="hh",
        owner_id="owner",
        correlation_id="corr",
        outbox=OutboxEvent(routing_key="comparison.requested.v1", envelope={"ok": True}),
    )

    async def _run() -> None:
        await repo.save(job)
        pending = await repo.find_pending_outbox(10)
        assert [item.id for item in pending] == ["j1"]
        job.mark_outbox_published()
        await repo.save(job)
        assert await repo.find_pending_outbox(10) == []
        loaded = await repo.find_by_id("j1")
        assert loaded is not None and loaded.status == "PROCESSING"
        with pytest.raises(ConflictError):
            await repo.save(job)

    import asyncio

    asyncio.run(_run())
