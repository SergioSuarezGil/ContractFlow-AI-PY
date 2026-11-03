from __future__ import annotations

from uuid import uuid4

from contracts_api.application.actor import ActorContext
from contracts_api.application.object_body import read_object
from contracts_api.application.ports import (
    ContractDocumentRepository,
    ObjectStoragePort,
    ServiceContractRepository,
)
from contracts_api.domain.document import (
    ContractDocument,
    assert_allowed_document_upload,
    assert_document_role,
)
from contracts_api.domain.errors import ForbiddenError, NotFoundError, ValidationError


class DocumentsService:
    def __init__(
        self,
        contracts: ServiceContractRepository,
        documents: ContractDocumentRepository,
        storage: ObjectStoragePort,
        *,
        documents_bucket: str = "documents",
    ) -> None:
        self._contracts = contracts
        self._documents = documents
        self._storage = storage
        self._bucket = documents_bucket

    async def list(self, actor: ActorContext, contract_id: str) -> list[ContractDocument]:
        await self._require_contract(actor, contract_id)
        return await self._documents.list_by_contract(contract_id)

    async def load_body_for_worker(self, document_id: str) -> tuple[ContractDocument, bytes]:
        """Internal worker fetch — no actor check (token-gated at HTTP edge)."""
        document = await self._documents.find_by_id(document_id)
        if document is None:
            raise NotFoundError(f"Document not found: {document_id}")
        body = await read_object(self._storage, self._bucket, document.storage_key)
        if body is None:
            raise NotFoundError(f"Document body missing: {document_id}")
        return document.snapshot(), body

    async def attach(
        self,
        actor: ActorContext,
        *,
        contract_id: str,
        role: str,
        file_name: str,
        content_type: str,
        body: bytes,
    ) -> ContractDocument:
        if not body:
            raise ValidationError("Empty file upload")
        assert_allowed_document_upload(file_name, content_type)
        doc_role = assert_document_role(role)
        contract = await self._require_contract(actor, contract_id)

        document_id = str(uuid4())
        storage_key = f"{actor.household_id}/{contract.id}/{document_id}"
        await self._storage.put_object(
            bucket=self._bucket,
            key=storage_key,
            body=body,
            content_type=content_type,
        )
        document = ContractDocument.create(
            id=document_id,
            contract_id=contract.id,
            household_id=actor.household_id,
            owner_id=actor.owner_id,
            role=doc_role,
            file_name=file_name,
            content_type=content_type,
            size_bytes=len(body),
            storage_key=storage_key,
        )
        try:
            await self._documents.save(document)
            await self._contracts.attach_document_id(contract.id, document.id, doc_role)
        except Exception:
            await self._storage.delete_object(self._bucket, storage_key)
            raise
        return document.snapshot()

    async def _require_contract(self, actor: ActorContext, contract_id: str):
        contract = await self._contracts.find_by_id(contract_id)
        if contract is None:
            raise NotFoundError(f"Contract not found: {contract_id}")
        if not contract.belongs_to(actor.owner_id, actor.household_id):
            raise ForbiddenError("Access denied to this contract")
        return contract
