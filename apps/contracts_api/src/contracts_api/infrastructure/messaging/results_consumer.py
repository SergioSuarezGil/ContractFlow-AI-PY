from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Protocol

import aio_pika
from aio_pika.abc import AbstractIncomingMessage
from contractflow_contracts import validate_event
from contractflow_shared.rabbit_retry import (
    backoff_seconds,
    headers_with_retry,
    is_transient_results_error,
    retry_count_from_headers,
    should_republish,
)
from contracts_api.domain.report import Report
from contracts_api.infrastructure.http.metrics_router import JOB_TRANSITIONS

logger = logging.getLogger(__name__)


class JobRepository(Protocol):
    async def find_by_id(self, job_id: str) -> Any: ...

    async def save(self, job: Any) -> None: ...


class ReportRepository(Protocol):
    async def find_by_id(self, report_id: str) -> Report | None: ...

    async def save(self, report: Report) -> None: ...


class ResultsEventApplier:
    """Apply comparison/report result events to jobs (and reports)."""

    def __init__(self, jobs: JobRepository, reports: ReportRepository) -> None:
        self._jobs = jobs
        self._reports = reports

    async def apply(self, raw_event: dict[str, Any]) -> None:
        validated = validate_event(raw_event)
        if not validated["ok"]:
            raise ValueError(f"Invalid event: {validated['error']}")
        envelope = validated["event"]
        event_type = envelope["eventType"]
        if event_type == "comparison.requested.v1":
            return

        payload = envelope["payload"]
        job_id = payload.get("jobId")
        if not job_id:
            return
        job = await self._jobs.find_by_id(str(job_id))
        if job is None:
            logger.warning("No job for result event %s jobId=%s", event_type, job_id)
            return

        if event_type == "comparison.completed.v1":
            job.mark_comparison_completed(str(payload["comparisonId"]))
            await self._jobs.save(job)
            JOB_TRANSITIONS.labels(event_type=event_type).inc()
            return

        if event_type in {"comparison.failed.v1", "report.failed.v1"}:
            job.mark_failed(str(payload.get("errorMessage") or "Worker failed"))
            await self._jobs.save(job)
            JOB_TRANSITIONS.labels(event_type=event_type).inc()
            return

        if event_type == "report.completed.v1":
            report_id = str(payload["reportId"])
            existing = await self._reports.find_by_id(report_id)
            if existing is None:
                report = Report.create(
                    id=report_id,
                    job_id=str(payload["jobId"]),
                    contract_id=str(payload["contractId"]),
                    owner_id=str(payload["ownerId"]),
                    household_id=str(envelope["householdId"]),
                    comparison_id=str(payload["comparisonId"]),
                    storage_key=str(payload["storageKey"]),
                    file_name=str(payload["fileName"]),
                    content_type=str(payload["contentType"]),
                    size_bytes=int(payload["sizeBytes"]),
                )
                await self._reports.save(report)
            job.mark_completed(report_id)
            await self._jobs.save(job)
            JOB_TRANSITIONS.labels(event_type=event_type).inc()


class RabbitMqResultsConsumer:
    def __init__(
        self,
        *,
        url: str,
        applier: ResultsEventApplier,
        exchange_name: str = "contractflow.events",
        queue_name: str = "contractflow.api.results",
        prefetch: int = 10,
    ) -> None:
        self._url = url
        self._applier = applier
        self._exchange_name = exchange_name
        self._queue_name = queue_name
        self._prefetch = prefetch
        self._connection: aio_pika.RobustConnection | None = None
        self._channel: aio_pika.Channel | None = None
        self._exchange: aio_pika.Exchange | None = None

    async def start(self) -> None:
        self._connection = await aio_pika.connect_robust(self._url)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=self._prefetch)
        exchange = await self._channel.declare_exchange(
            self._exchange_name, aio_pika.ExchangeType.TOPIC, durable=True
        )
        self._exchange = exchange
        queue = await self._channel.declare_queue(
            self._queue_name,
            durable=True,
            arguments={"x-dead-letter-exchange": "contractflow.events.dlx"},
        )
        for key in (
            "comparison.completed.v1",
            "comparison.failed.v1",
            "report.completed.v1",
            "report.failed.v1",
        ):
            await queue.bind(exchange, routing_key=key)
        await queue.consume(self._on_message)
        logger.info("Results consumer listening on %s", self._queue_name)

    async def stop(self) -> None:
        if self._channel is not None:
            await self._channel.close()
        if self._connection is not None:
            await self._connection.close()

    async def _republish(self, message: AbstractIncomingMessage, retries: int) -> None:
        if self._exchange is None:
            raise RuntimeError("Rabbit exchange is not ready")
        await asyncio.sleep(backoff_seconds(retries))
        headers = headers_with_retry(message.headers, retries)
        republished = aio_pika.Message(
            body=message.body,
            headers=headers,
            content_type=message.content_type,
            delivery_mode=message.delivery_mode or aio_pika.DeliveryMode.PERSISTENT,
            correlation_id=message.correlation_id,
            message_id=message.message_id,
        )
        await self._exchange.publish(republished, routing_key=message.routing_key or "")

    async def _on_message(self, message: AbstractIncomingMessage) -> None:
        try:
            payload = json.loads(message.body.decode("utf-8"))
        except json.JSONDecodeError:
            logger.warning("Rejecting non-JSON results message")
            await message.reject(requeue=False)
            return
        try:
            await self._applier.apply(payload)
        except ValueError as exc:
            logger.error("Permanent results failure: %s", exc)
            await message.reject(requeue=False)
            return
        except Exception as exc:
            retries = retry_count_from_headers(message.headers)
            text = str(exc)
            if is_transient_results_error(text) and should_republish(retries):
                logger.warning("Retrying results event (%s/3): %s", retries + 1, text)
                await self._republish(message, retries)
                await message.ack()
                return
            logger.exception("Results event dead-lettered: %s", text)
            await message.reject(requeue=False)
            return
        await message.ack()
