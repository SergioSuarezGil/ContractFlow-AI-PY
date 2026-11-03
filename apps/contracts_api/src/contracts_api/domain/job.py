from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any, Literal

from contracts_api.domain.errors import ValidationError

JobStatus = Literal["PENDING", "PROCESSING", "COMPLETED", "FAILED"]


@dataclass
class OutboxEvent:
    routing_key: str
    envelope: dict[str, Any]
    published_at: str | None = None


@dataclass
class Job:
    id: str
    contract_id: str
    household_id: str
    owner_id: str
    correlation_id: str
    status: JobStatus = "PENDING"
    job_type: str = "COMPARE_PROPOSALS"
    comparison_id: str | None = None
    report_id: str | None = None
    error_message: str | None = None
    version: int = 0
    outbox: OutboxEvent | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(
        cls,
        *,
        id: str,
        contract_id: str,
        household_id: str,
        owner_id: str,
        correlation_id: str,
        outbox: OutboxEvent,
        now: datetime | None = None,
    ) -> Job:
        stamp = now or datetime.now(UTC)
        return cls(
            id=id,
            contract_id=contract_id,
            household_id=household_id,
            owner_id=owner_id,
            correlation_id=correlation_id,
            status="PENDING",
            version=0,
            outbox=outbox,
            created_at=stamp,
            updated_at=stamp,
        )

    def belongs_to(self, owner_id: str, household_id: str) -> bool:
        return self.owner_id == owner_id and self.household_id == household_id

    def snapshot(self) -> Job:
        outbox = None
        if self.outbox is not None:
            outbox = OutboxEvent(
                routing_key=self.outbox.routing_key,
                envelope=dict(self.outbox.envelope),
                published_at=self.outbox.published_at,
            )
        return replace(self, outbox=outbox)

    def mark_outbox_published(self, now: datetime | None = None) -> None:
        if self.outbox is None or self.outbox.published_at:
            return
        self._assert_not_terminal()
        self.outbox.published_at = (now or datetime.now(UTC)).isoformat()
        if self.status == "PENDING":
            self.status = "PROCESSING"
        self._bump(now)

    def mark_comparison_completed(
        self, comparison_id: str, now: datetime | None = None
    ) -> None:
        if self.status in {"COMPLETED", "FAILED"}:
            return
        self.comparison_id = comparison_id
        self.status = "PROCESSING"
        self._bump(now)

    def mark_completed(self, report_id: str, now: datetime | None = None) -> None:
        if self.status == "COMPLETED":
            return
        if self.status == "FAILED":
            raise ValidationError("Failed jobs cannot complete")
        self.report_id = report_id
        self.status = "COMPLETED"
        self._bump(now)

    def mark_failed(self, message: str, now: datetime | None = None) -> None:
        if self.status in {"COMPLETED", "FAILED"}:
            return
        self.status = "FAILED"
        self.error_message = message
        self._bump(now)

    def _assert_not_terminal(self) -> None:
        if self.status in {"COMPLETED", "FAILED"}:
            raise ValidationError(f"Job {self.id} is terminal ({self.status})")

    def _bump(self, now: datetime | None) -> None:
        self.updated_at = now or datetime.now(UTC)
        self.version += 1
