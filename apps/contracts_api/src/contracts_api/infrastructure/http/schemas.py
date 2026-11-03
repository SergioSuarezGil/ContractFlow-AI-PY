from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ServiceType = Literal["electricity", "gas", "insurance", "mobile", "internet", "other"]
ContractStatus = Literal["draft", "active", "under_review", "archived"]


class CreateContractRequest(BaseModel):
    service_type: ServiceType = Field(alias="serviceType")
    provider_name: str = Field(alias="providerName", min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)

    model_config = {"populate_by_name": True}


class UpdateContractRequest(BaseModel):
    service_type: ServiceType | None = Field(default=None, alias="serviceType")
    provider_name: str | None = Field(
        default=None, alias="providerName", min_length=1, max_length=200
    )
    title: str | None = Field(default=None, min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=2000)
    status: Literal["draft", "active", "under_review"] | None = None

    model_config = {"populate_by_name": True}


class ContractResponse(BaseModel):
    id: str
    household_id: str = Field(serialization_alias="householdId")
    owner_id: str = Field(serialization_alias="ownerId")
    service_type: ServiceType = Field(serialization_alias="serviceType")
    provider_name: str = Field(serialization_alias="providerName")
    title: str
    notes: str
    status: ContractStatus
    current_document_ids: list[str] = Field(serialization_alias="currentDocumentIds")
    proposal_document_ids: list[str] = Field(serialization_alias="proposalDocumentIds")
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")
    version: int

    model_config = {"populate_by_name": True, "from_attributes": True}


class DocumentResponse(BaseModel):
    id: str
    contract_id: str = Field(serialization_alias="contractId")
    role: Literal["current", "proposal"]
    file_name: str = Field(serialization_alias="fileName")
    content_type: str = Field(serialization_alias="contentType")
    size_bytes: int = Field(serialization_alias="sizeBytes")
    created_at: datetime = Field(serialization_alias="createdAt")

    model_config = {"populate_by_name": True}


class ComparisonAcceptedResponse(BaseModel):
    job_id: str = Field(serialization_alias="jobId")
    status: str
    correlation_id: str = Field(serialization_alias="correlationId")

    model_config = {"populate_by_name": True}


class ReportResponse(BaseModel):
    id: str
    job_id: str = Field(serialization_alias="jobId")
    contract_id: str = Field(serialization_alias="contractId")
    file_name: str = Field(serialization_alias="fileName")
    created_at: datetime = Field(serialization_alias="createdAt")

    model_config = {"populate_by_name": True}


class JobResponse(BaseModel):
    id: str
    type: str
    status: str
    contract_id: str = Field(serialization_alias="contractId")
    household_id: str = Field(serialization_alias="householdId")
    owner_id: str = Field(serialization_alias="ownerId")
    correlation_id: str = Field(serialization_alias="correlationId")
    comparison_id: str | None = Field(default=None, serialization_alias="comparisonId")
    report_id: str | None = Field(default=None, serialization_alias="reportId")
    error_message: str | None = Field(default=None, serialization_alias="errorMessage")
    version: int
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")

    model_config = {"populate_by_name": True}
