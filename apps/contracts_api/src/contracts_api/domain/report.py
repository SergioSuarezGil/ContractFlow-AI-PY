from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class Report:
    id: str
    job_id: str
    contract_id: str
    owner_id: str
    household_id: str
    comparison_id: str
    storage_key: str
    file_name: str
    content_type: str
    size_bytes: int
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(
        cls,
        *,
        id: str,
        job_id: str,
        contract_id: str,
        owner_id: str,
        household_id: str,
        comparison_id: str,
        storage_key: str,
        file_name: str,
        content_type: str,
        size_bytes: int,
    ) -> Report:
        return cls(
            id=id,
            job_id=job_id,
            contract_id=contract_id,
            owner_id=owner_id,
            household_id=household_id,
            comparison_id=comparison_id,
            storage_key=storage_key,
            file_name=file_name,
            content_type=content_type,
            size_bytes=size_bytes,
        )
