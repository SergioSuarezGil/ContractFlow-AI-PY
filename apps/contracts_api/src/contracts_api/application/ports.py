from typing import Any, Protocol

from contracts_api.domain.document import ContractDocument
from contracts_api.domain.job import Job
from contracts_api.domain.report import Report
from contracts_api.domain.service_contract import ServiceContract


class ServiceContractRepository(Protocol):
    async def save(self, contract: ServiceContract) -> None: ...

    async def find_by_id(self, contract_id: str) -> ServiceContract | None: ...

    async def list_by_household(
        self, household_id: str, owner_id: str
    ) -> list[ServiceContract]: ...

    async def attach_document_id(
        self, contract_id: str, document_id: str, role: str
    ) -> None: ...


class ContractDocumentRepository(Protocol):
    async def save(self, document: ContractDocument) -> None: ...

    async def find_by_id(self, document_id: str) -> ContractDocument | None: ...

    async def list_by_contract(self, contract_id: str) -> list[ContractDocument]: ...


class JobRepository(Protocol):
    async def save(self, job: Job) -> None: ...

    async def find_by_id(self, job_id: str) -> Job | None: ...

    async def find_pending_outbox(self, limit: int) -> list[Job]: ...


class ReportRepository(Protocol):
    async def save(self, report: Report) -> None: ...

    async def find_by_id(self, report_id: str) -> Report | None: ...


class ObjectStoragePort(Protocol):
    async def put_object(
        self, *, bucket: str, key: str, body: bytes, content_type: str
    ) -> None: ...

    async def get_object(self, bucket: str, key: str) -> bytes | None: ...

    async def delete_object(self, bucket: str, key: str) -> None: ...


class EventPublisher(Protocol):
    async def publish(self, routing_key: str, envelope: dict[str, Any]) -> None: ...
