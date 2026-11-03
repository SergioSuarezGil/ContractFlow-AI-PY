from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class ExtractionRunRecord:
    job_id: str
    contract_id: str
    status: str
    document_count: int
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    payload: dict[str, Any] = field(default_factory=dict)


class InMemoryIdempotencyStore:
    def __init__(self) -> None:
        self._items: dict[str, ExtractionRunRecord] = {}

    async def get(self, job_id: str) -> ExtractionRunRecord | None:
        return self._items.get(job_id)

    async def put_if_absent(self, record: ExtractionRunRecord) -> bool:
        """Return True if inserted, False if job already processed."""
        if record.job_id in self._items:
            return False
        self._items[record.job_id] = record
        return True

    def clear(self) -> None:
        self._items.clear()
