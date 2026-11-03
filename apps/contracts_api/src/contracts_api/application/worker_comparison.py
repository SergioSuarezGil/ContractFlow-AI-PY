from __future__ import annotations

from collections.abc import Awaitable, Callable

from contracts_api.application.actor import ActorContext
from contracts_api.application.ports import JobRepository
from contracts_api.domain.errors import NotFoundError


class WorkerComparisonService:
    """Authorize a job, then proxy the ai-worker gRPC comparison lookup."""

    def __init__(
        self,
        jobs: JobRepository,
        lookup: Callable[[str], Awaitable[dict[str, object]]],
    ) -> None:
        self._jobs = jobs
        self._lookup = lookup

    async def get(self, actor: ActorContext, job_id: str) -> dict[str, object]:
        job = await self._jobs.find_by_id(job_id)
        if job is None or not job.belongs_to(actor.owner_id, actor.household_id):
            raise NotFoundError(f"Job not found: {job_id}")
        worker = await self._lookup(job_id)
        return {"jobId": job_id, "worker": worker}
