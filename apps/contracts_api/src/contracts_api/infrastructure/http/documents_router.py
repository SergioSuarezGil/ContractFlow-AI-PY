from typing import Annotated

from contracts_api.application.actor import ActorContext
from contracts_api.application.documents_service import DocumentsService
from contracts_api.deps import get_documents_service
from contracts_api.infrastructure.auth.deps import get_actor
from contracts_api.infrastructure.http.schemas import DocumentResponse
from fastapi import APIRouter, Depends, File, Form, UploadFile, status

router = APIRouter(
    prefix="/api/v1/contracts/{contract_id}/documents",
    tags=["documents"],
)


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    contract_id: str,
    actor: Annotated[ActorContext, Depends(get_actor)],
    service: Annotated[DocumentsService, Depends(get_documents_service)],
) -> list[DocumentResponse]:
    items = await service.list(actor, contract_id)
    return [
        DocumentResponse(
            id=item.id,
            contract_id=item.contract_id,
            role=item.role,
            file_name=item.file_name,
            content_type=item.content_type,
            size_bytes=item.size_bytes,
            created_at=item.created_at,
        )
        for item in items
    ]


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    contract_id: str,
    actor: Annotated[ActorContext, Depends(get_actor)],
    service: Annotated[DocumentsService, Depends(get_documents_service)],
    role: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
) -> DocumentResponse:
    body = await file.read()
    document = await service.attach(
        actor,
        contract_id=contract_id,
        role=role,
        file_name=file.filename or "upload.bin",
        content_type=file.content_type or "application/octet-stream",
        body=body,
    )
    return DocumentResponse(
        id=document.id,
        contract_id=document.contract_id,
        role=document.role,
        file_name=document.file_name,
        content_type=document.content_type,
        size_bytes=document.size_bytes,
        created_at=document.created_at,
    )
