from contracts_api.domain.job import Job


class InMemoryJobRepository:
    def __init__(self) -> None:
        self._items: dict[str, Job] = {}

    async def save(self, job: Job) -> None:
        self._items[job.id] = job.snapshot()

    async def find_by_id(self, job_id: str) -> Job | None:
        found = self._items.get(job_id)
        return found.snapshot() if found else None

    async def find_pending_outbox(self, limit: int) -> list[Job]:
        pending = [
            item.snapshot()
            for item in self._items.values()
            if item.outbox is not None and item.outbox.published_at is None
        ]
        pending.sort(key=lambda j: j.created_at)
        return pending[:limit]

    def clear(self) -> None:
        self._items.clear()
