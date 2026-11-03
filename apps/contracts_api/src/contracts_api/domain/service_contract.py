from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Literal

from contracts_api.domain.errors import ValidationError

ServiceType = Literal["electricity", "gas", "insurance", "mobile", "internet", "other"]
ContractStatus = Literal["draft", "active", "under_review", "archived"]

SERVICE_TYPES: frozenset[str] = frozenset(
    {"electricity", "gas", "insurance", "mobile", "internet", "other"}
)
CONTRACT_STATUSES: frozenset[str] = frozenset(
    {"draft", "active", "under_review", "archived"}
)


def _non_empty(label: str, value: str) -> str:
    trimmed = value.strip()
    if not trimmed:
        raise ValidationError(f"{label} must not be empty")
    return trimmed


def assert_service_type(value: str) -> ServiceType:
    if value not in SERVICE_TYPES:
        raise ValidationError(f"Invalid serviceType: {value}")
    return value  # type: ignore[return-value]


def assert_contract_status(value: str) -> ContractStatus:
    if value not in CONTRACT_STATUSES:
        raise ValidationError(f"Invalid status: {value}")
    return value  # type: ignore[return-value]


@dataclass
class ServiceContract:
    id: str
    household_id: str
    owner_id: str
    service_type: ServiceType
    provider_name: str
    title: str
    notes: str = ""
    status: ContractStatus = "draft"
    current_document_ids: list[str] = field(default_factory=list)
    proposal_document_ids: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    version: int = 1

    @classmethod
    def create(
        cls,
        *,
        id: str,
        household_id: str,
        owner_id: str,
        service_type: str,
        provider_name: str,
        title: str,
        notes: str = "",
        now: datetime | None = None,
    ) -> ServiceContract:
        stamp = now or datetime.now(UTC)
        return cls(
            id=_non_empty("id", id),
            household_id=_non_empty("householdId", household_id),
            owner_id=_non_empty("ownerId", owner_id),
            service_type=assert_service_type(service_type),
            provider_name=_non_empty("providerName", provider_name),
            title=_non_empty("title", title),
            notes=(notes or "").strip(),
            status="draft",
            current_document_ids=[],
            proposal_document_ids=[],
            created_at=stamp,
            updated_at=stamp,
            version=1,
        )

    def belongs_to(self, owner_id: str, household_id: str) -> bool:
        return self.owner_id == owner_id and self.household_id == household_id

    def update_details(
        self,
        *,
        title: str | None = None,
        provider_name: str | None = None,
        notes: str | None = None,
        service_type: str | None = None,
        status: str | None = None,
        now: datetime | None = None,
    ) -> None:
        self._assert_not_archived()
        if title is not None:
            self.title = _non_empty("title", title)
        if provider_name is not None:
            self.provider_name = _non_empty("providerName", provider_name)
        if notes is not None:
            self.notes = notes.strip()
        if service_type is not None:
            self.service_type = assert_service_type(service_type)
        if status is not None:
            next_status = assert_contract_status(status)
            if next_status == "archived":
                raise ValidationError("Use archive() to archive a contract")
            self.status = next_status
        self._touch(now)

    def archive(self, now: datetime | None = None) -> None:
        self._assert_not_archived()
        self.status = "archived"
        self._touch(now)

    def attach_document(
        self, document_id: str, role: Literal["current", "proposal"], now: datetime | None = None
    ) -> None:
        self._assert_not_archived()
        doc_id = document_id.strip()
        if not doc_id:
            raise ValidationError("documentId must not be empty")
        if doc_id in self.current_document_ids or doc_id in self.proposal_document_ids:
            raise ValidationError(f"Document already attached: {doc_id}")
        if role == "current":
            self.current_document_ids.append(doc_id)
        else:
            self.proposal_document_ids.append(doc_id)
        if self.status == "draft":
            self.status = "active"
        self._touch(now)

    def can_request_comparison(self) -> None:
        self._assert_not_archived()
        if len(self.current_document_ids) < 1:
            raise ValidationError("Comparison requires at least one current document")
        if len(self.proposal_document_ids) < 1:
            raise ValidationError("Comparison requires at least one proposal document")

    def snapshot(self) -> ServiceContract:
        return replace(
            self,
            current_document_ids=list(self.current_document_ids),
            proposal_document_ids=list(self.proposal_document_ids),
        )

    def _assert_not_archived(self) -> None:
        if self.status == "archived":
            raise ValidationError("Archived contracts cannot be modified")

    def _touch(self, now: datetime | None) -> None:
        self.updated_at = now or datetime.now(UTC)
        self.version += 1
