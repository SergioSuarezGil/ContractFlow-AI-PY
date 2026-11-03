from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4

from contractflow_contracts import validate_event
from pdf_worker.application.pdf_generator import MultipagePdfGenerator, PdfReportInput

logger = logging.getLogger(__name__)


class ObjectStorage(Protocol):
    async def put(self, *, bucket: str, key: str, body: bytes, content_type: str) -> None: ...


class EventPublisher(Protocol):
    async def publish(self, routing_key: str, envelope: dict[str, Any]) -> None: ...


class IdempotencyStore(Protocol):
    async def seen(self, job_id: str) -> bool: ...

    async def mark(self, job_id: str, report_id: str) -> bool: ...


class InMemoryReportIdempotency:
    def __init__(self) -> None:
        self._done: dict[str, str] = {}

    async def seen(self, job_id: str) -> bool:
        return job_id in self._done

    async def mark(self, job_id: str, report_id: str) -> bool:
        if job_id in self._done:
            return False
        self._done[job_id] = report_id
        return True


class ReportUploader(Protocol):
    async def upload(
        self,
        *,
        report_id: str,
        job_id: str,
        contract_id: str,
        owner_id: str,
        household_id: str,
        comparison_id: str,
        storage_key: str,
        file_name: str,
        content_type: str,
        body: bytes,
    ) -> dict[str, Any] | None: ...


class ReportRequestedHandler:
    def __init__(
        self,
        *,
        storage: ObjectStorage,
        publisher: EventPublisher,
        idempotency: IdempotencyStore | None = None,
        generator: MultipagePdfGenerator | None = None,
        bucket: str = "reports",
        uploader: ReportUploader | None = None,
    ) -> None:
        self._storage = storage
        self._publisher = publisher
        self._idempotency = idempotency or InMemoryReportIdempotency()
        self._generator = generator or MultipagePdfGenerator()
        self._bucket = bucket
        self._uploader = uploader

    async def handle(self, raw_event: Any) -> dict[str, Any] | None:
        validated = validate_event(raw_event)
        if not validated["ok"]:
            raise ValueError(f"Invalid event: {validated['error']}")
        envelope = validated["event"]
        if envelope["eventType"] != "report.requested.v1":
            return None

        payload = envelope["payload"]
        job_id = str(payload["jobId"])
        if await self._idempotency.seen(job_id):
            logger.info("Idempotent skip report for job %s", job_id)
            return None

        comparison = payload.get("comparison") or {}
        report_id = _stable_report_id(job_id)
        pdf_bytes = self._generator.generate(
            PdfReportInput(
                title=str(comparison.get("summary") or "Contract comparison")[:80],
                job_id=job_id,
                contract_id=str(payload["contractId"]),
                verdict=str(comparison.get("verdict") or payload.get("verdict") or "depends"),
                summary=str(comparison.get("summary") or ""),
                price_notes=str(comparison.get("priceNotes") or ""),
                coverage_notes=str(comparison.get("coverageNotes") or ""),
                disclaimer=str(
                    comparison.get("disclaimer")
                    or "Informational only — not legal or financial advice."
                ),
                analysis_mode=str(comparison.get("analysisMode") or "mock"),
                risks=list(comparison.get("risks") or []),
                citations=list(comparison.get("citations") or []),
            )
        )
        storage_key = f"reports/{job_id}/{report_id}.pdf"
        await self._storage.put(
            bucket=self._bucket,
            key=storage_key,
            body=pdf_bytes,
            content_type="application/pdf",
        )
        if self._uploader is not None:
            await self._uploader.upload(
                report_id=report_id,
                job_id=job_id,
                contract_id=str(payload["contractId"]),
                owner_id=str(payload["ownerId"]),
                household_id=str(envelope["householdId"]),
                comparison_id=str(payload["comparisonId"]),
                storage_key=storage_key,
                file_name=f"{report_id}.pdf",
                content_type="application/pdf",
                body=pdf_bytes,
            )

        inserted = await self._idempotency.mark(job_id, report_id)
        if not inserted:
            return None

        completed = {
            "eventId": str(uuid4()),
            "eventType": "report.completed.v1",
            "schemaVersion": 1,
            "correlationId": envelope["correlationId"],
            "causationId": envelope["eventId"],
            "householdId": envelope["householdId"],
            "occurredAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "payload": {
                "jobId": job_id,
                "contractId": str(payload["contractId"]),
                "ownerId": str(payload["ownerId"]),
                "reportId": report_id,
                "comparisonId": str(payload["comparisonId"]),
                "storageKey": storage_key,
                "fileName": f"{report_id}.pdf",
                "contentType": "application/pdf",
                "sizeBytes": len(pdf_bytes),
            },
        }
        await self._publisher.publish("report.completed.v1", completed)
        return completed["payload"]

    async def publish_terminal_failure(self, raw_event: Any, error_message: str) -> None:
        validated = validate_event(raw_event)
        if not validated["ok"]:
            return
        envelope = validated["event"]
        payload = envelope.get("payload") or {}
        await self._publish_failed(envelope, payload, error_message)

    async def _publish_failed(
        self, envelope: dict[str, Any], payload: dict[str, Any], error: str
    ) -> None:
        failed = {
            "eventId": str(uuid4()),
            "eventType": "report.failed.v1",
            "schemaVersion": 1,
            "correlationId": envelope["correlationId"],
            "causationId": envelope["eventId"],
            "householdId": envelope["householdId"],
            "occurredAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "payload": {
                "jobId": str(payload["jobId"]),
                "contractId": str(payload["contractId"]),
                "ownerId": str(payload["ownerId"]),
                "errorMessage": error[:2000],
            },
        }
        try:
            await self._publisher.publish("report.failed.v1", failed)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to publish report.failed.v1")


def _stable_report_id(job_id: str) -> str:
    return hashlib.sha256(f"report:{job_id}".encode()).hexdigest()[:32]
