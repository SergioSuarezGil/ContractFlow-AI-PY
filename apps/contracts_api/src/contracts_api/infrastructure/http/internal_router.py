from __future__ import annotations

import base64
import os
from typing import Annotated

from contracts_api.application.documents_service import DocumentsService
from contracts_api.application.reports_service import ReportsService
from contracts_api.deps import get_documents_service, get_reports_service
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/internal/v1", tags=["internal"])


class InternalReportUpload(BaseModel):
    jobId: str
    contractId: str
    ownerId: str
    householdId: str
    comparisonId: str
    fileName: str = Field(default="")
    contentType: str = "application/pdf"
    storageKey: str | None = None
    bodyBase64: str


def _require_internal_token(
    x_internal_token: Annotated[str | None, Header()] = None,
) -> None:
    expected = os.getenv("INTERNAL_API_TOKEN", "dev-internal").strip()
    if not expected or x_internal_token != expected:
        raise HTTPException(status_code=401, detail="Invalid internal token")


@router.get("/documents/{document_id}")
async def get_document_for_worker(
    document_id: str,
    _: Annotated[None, Depends(_require_internal_token)],
    service: Annotated[DocumentsService, Depends(get_documents_service)],
) -> dict:
    document, body = await service.load_body_for_worker(document_id)
    return {
        "id": document.id,
        "contractId": document.contract_id,
        "role": document.role,
        "fileName": document.file_name,
        "contentType": document.content_type,
        "storageKey": document.storage_key,
        "bodyBase64": base64.b64encode(body).decode("ascii"),
    }


@router.put("/reports/{report_id}")
async def put_report_from_worker(
    report_id: str,
    payload: InternalReportUpload,
    _: Annotated[None, Depends(_require_internal_token)],
    service: Annotated[ReportsService, Depends(get_reports_service)],
) -> dict:
    body = base64.b64decode(payload.bodyBase64)
    report = await service.store_from_worker(
        report_id=report_id,
        job_id=payload.jobId,
        contract_id=payload.contractId,
        owner_id=payload.ownerId,
        household_id=payload.householdId,
        comparison_id=payload.comparisonId,
        file_name=payload.fileName or f"{report_id}.pdf",
        content_type=payload.contentType,
        body=body,
        storage_key=payload.storageKey,
    )
    return {
        "id": report.id,
        "storageKey": report.storage_key,
        "sizeBytes": report.size_bytes,
    }
