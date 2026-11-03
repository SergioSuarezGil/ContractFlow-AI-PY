from __future__ import annotations

from uuid import uuid4

from contractflow_contracts import validate_event
from contracts_api.application.actor import ActorContext
from contracts_api.application.event_envelope import create_envelope
from contracts_api.application.ports import JobRepository, ServiceContractRepository
from contracts_api.domain.errors import ForbiddenError, NotFoundError
from contracts_api.domain.job import Job, OutboxEvent


class JobsService:
    def __init__(
        self,
        contracts: ServiceContractRepository,
        jobs: JobRepository,
    ) -> None:
        self._contracts = contracts
        self._jobs = jobs

    async def request_comparison(self, actor: ActorContext, contract_id: str) -> dict:
        contract = await self._contracts.find_by_id(contract_id)
        if contract is None:
            raise NotFoundError(f"Contract not found: {contract_id}")
        if not contract.belongs_to(actor.owner_id, actor.household_id):
            raise ForbiddenError("Access denied to this contract")
        contract.can_request_comparison()
        snap = contract.snapshot()

        job_id = str(uuid4())
        correlation_id = str(uuid4())
        event_id = str(uuid4())
        envelope = create_envelope(
            event_id=event_id,
            event_type="comparison.requested.v1",
            correlation_id=correlation_id,
            household_id=actor.household_id,
            payload={
                "jobId": job_id,
                "contractId": snap.id,
                "ownerId": actor.owner_id,
                "currentDocumentIds": list(snap.current_document_ids),
                "proposalDocumentIds": list(snap.proposal_document_ids),
                "title": snap.title,
                "providerName": snap.provider_name,
                "serviceType": snap.service_type,
            },
        )
        validated = validate_event(envelope)
        if not validated["ok"]:
            raise RuntimeError(f"Invalid comparison.requested envelope: {validated['error']}")

        job = Job.create(
            id=job_id,
            contract_id=snap.id,
            household_id=actor.household_id,
            owner_id=actor.owner_id,
            correlation_id=correlation_id,
            outbox=OutboxEvent(
                routing_key="comparison.requested.v1",
                envelope=envelope,
                published_at=None,
            ),
        )
        await self._jobs.save(job)
        return {
            "jobId": job.id,
            "status": job.status,
            "correlationId": correlation_id,
        }

    async def get(self, actor: ActorContext, job_id: str) -> Job:
        job = await self._jobs.find_by_id(job_id)
        if job is None or not job.belongs_to(actor.owner_id, actor.household_id):
            raise NotFoundError(f"Job not found: {job_id}")
        return job.snapshot()
