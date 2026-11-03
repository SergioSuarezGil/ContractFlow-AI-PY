from __future__ import annotations

import asyncio
import logging

from contracts_api.application.ports import EventPublisher, JobRepository

logger = logging.getLogger(__name__)


class OutboxRelay:
    def __init__(
        self,
        jobs: JobRepository,
        publisher: EventPublisher,
        *,
        interval_ms: int = 500,
    ) -> None:
        self._jobs = jobs
        self._publisher = publisher
        self._interval = max(interval_ms, 100) / 1000
        self._task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop(), name="outbox-relay")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        await self.drain()

    async def _loop(self) -> None:
        while True:
            await self.drain()
            await asyncio.sleep(self._interval)

    async def drain(self) -> None:
        async with self._lock:
            try:
                pending = await self._jobs.find_pending_outbox(20)
                for job in pending:
                    snap = job.snapshot()
                    outbox = snap.outbox
                    if outbox is None or outbox.published_at:
                        continue
                    try:
                        await self._publisher.publish(outbox.routing_key, outbox.envelope)
                        job.mark_outbox_published()
                        await self._jobs.save(job)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("Outbox publish failed for job %s: %s", snap.id, exc)
            except Exception as exc:  # noqa: BLE001
                logger.error("Outbox drain error: %s", exc)
