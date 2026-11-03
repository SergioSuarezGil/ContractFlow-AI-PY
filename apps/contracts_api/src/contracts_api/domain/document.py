from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Literal

from contracts_api.domain.errors import ValidationError

DocumentRole = Literal["current", "proposal"]

ALLOWED_EXTENSIONS = frozenset({"pdf", "xlsx", "xls", "csv", "md", "txt", "docx"})
ALLOWED_CONTENT_TYPES = frozenset(
    {
        "application/pdf",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
        "text/markdown",
        "text/x-markdown",
        "text/csv",
        "application/csv",
        "application/octet-stream",
    }
)


def assert_document_role(value: str) -> DocumentRole:
    if value not in {"current", "proposal"}:
        raise ValidationError(f"Invalid document role: {value}")
    return value  # type: ignore[return-value]


def assert_allowed_document_upload(file_name: str, content_type: str) -> None:
    ext = file_name.rsplit(".", 1)[-1].lower().strip() if "." in file_name else ""
    if not ext or ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            f"Unsupported file type '.{ext or 'unknown'}'. "
            "Allowed: pdf, xlsx, xls, csv, md, txt, docx"
        )
    mime = (content_type or "").split(";", 1)[0].strip().lower()
    if mime and mime not in ALLOWED_CONTENT_TYPES:
        raise ValidationError(
            f"Unsupported content type '{content_type}'. "
            "Allowed: PDF, Excel, CSV, Markdown, text, Word"
        )


@dataclass
class ContractDocument:
    id: str
    contract_id: str
    household_id: str
    owner_id: str
    role: DocumentRole
    file_name: str
    content_type: str
    size_bytes: int
    storage_key: str
    created_at: datetime

    @classmethod
    def create(
        cls,
        *,
        id: str,
        contract_id: str,
        household_id: str,
        owner_id: str,
        role: str,
        file_name: str,
        content_type: str,
        size_bytes: int,
        storage_key: str,
        now: datetime | None = None,
    ) -> ContractDocument:
        if size_bytes <= 0:
            raise ValidationError("sizeBytes must be positive")
        return cls(
            id=id.strip(),
            contract_id=contract_id.strip(),
            household_id=household_id.strip(),
            owner_id=owner_id.strip(),
            role=assert_document_role(role),
            file_name=file_name.strip(),
            content_type=content_type.strip(),
            size_bytes=size_bytes,
            storage_key=storage_key.strip(),
            created_at=now or datetime.now(UTC),
        )

    def snapshot(self) -> ContractDocument:
        return replace(self)
