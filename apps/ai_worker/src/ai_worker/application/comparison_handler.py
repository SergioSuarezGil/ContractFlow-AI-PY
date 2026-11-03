from __future__ import annotations

import logging
import os
import time
from typing import Any

from ai_worker.application.comparison_pipeline import ComparisonPipeline
from ai_worker.application.comparison_result import ComparisonResult
from ai_worker.infrastructure.event_publisher import (
    EventPublisher,
    NoopEventPublisher,
    build_envelope,
)
from ai_worker.infrastructure.idempotency import (
    ExtractionRunRecord,
    InMemoryIdempotencyStore,
)
from contractflow_contracts import validate_event
from contractflow_shared.rabbit_retry import RetryableWorkerError, is_permanent_ai_error

logger = logging.getLogger(__name__)


class ComparisonRequestedHandler:
    """Extract → analyze → verify citations → publish completed + report.requested."""

    def __init__(
        self,
        pipeline: ComparisonPipeline,
        idempotency: InMemoryIdempotencyStore,
        publisher: EventPublisher | None = None,
        comparison_store: Any | None = None,
        llm_metrics: Any | None = None,
    ) -> None:
        self._pipeline = pipeline
        self._idempotency = idempotency
        self._publisher = publisher or NoopEventPublisher()
        self._comparison_store = comparison_store
        self._llm_metrics = llm_metrics

    async def handle(self, raw_event: Any) -> ComparisonResult | None:
        validated = validate_event(raw_event)
        if not validated["ok"]:
            raise ValueError(f"Invalid event: {validated['error']}")
        envelope = validated["event"]
        if envelope["eventType"] != "comparison.requested.v1":
            return None

        payload = envelope["payload"]
        job_id = str(payload["jobId"])
        existing = await self._idempotency.get(job_id)
        if existing is not None:
            logger.info("Idempotent skip for job %s", job_id)
            return None

        owner_id = str(payload["ownerId"])
        contract_id = str(payload["contractId"])
        started = time.perf_counter()
        try:
            result = await self._pipeline.run(
                job_id=job_id,
                contract_id=contract_id,
                title=str(payload.get("title") or "Contract"),
                provider_name=str(payload.get("providerName") or "Unknown"),
                service_type=str(payload.get("serviceType") or "other"),
                current_document_ids=list(payload.get("currentDocumentIds") or []),
                proposal_document_ids=list(payload.get("proposalDocumentIds") or []),
            )
        except Exception as exc:
            self._record_llm(outcome="error", duration_s=time.perf_counter() - started)
            if is_permanent_ai_error(exc):
                await self._publish_failure(
                    envelope,
                    job_id=job_id,
                    contract_id=contract_id,
                    owner_id=owner_id,
                    error_message=str(exc),
                )
                raise
            raise RetryableWorkerError(str(exc)) from exc

        self._record_llm(
            outcome="success",
            duration_s=time.perf_counter() - started,
            usage=result.llm_usage,
        )
        if self._comparison_store is not None:
            saved = await self._comparison_store.insert(
                {
                    **result.to_event_dict(),
                    "householdId": str(envelope["householdId"]),
                    "ownerId": owner_id,
                }
            )
            if not saved:
                logger.info("Duplicate comparison for job %s", job_id)
                return None

        inserted = await self._idempotency.put_if_absent(
            ExtractionRunRecord(
                job_id=job_id,
                contract_id=result.contract_id,
                status="COMPLETED",
                document_count=0,
                payload={"verdict": result.verdict, "comparisonId": result.id},
            )
        )
        if not inserted:
            logger.info("Duplicate comparison race for job %s", job_id)
            return None

        comparison = result.to_event_dict()
        await self._publisher.publish(
            "comparison.completed.v1",
            build_envelope(
                event_type="comparison.completed.v1",
                correlation_id=str(envelope["correlationId"]),
                household_id=str(envelope["householdId"]),
                causation_id=str(envelope["eventId"]),
                payload={
                    "jobId": job_id,
                    "contractId": contract_id,
                    "ownerId": owner_id,
                    "comparisonId": result.id,
                    "verdict": result.verdict,
                    "comparison": comparison,
                },
            ),
        )
        await self._publisher.publish(
            "report.requested.v1",
            build_envelope(
                event_type="report.requested.v1",
                correlation_id=str(envelope["correlationId"]),
                household_id=str(envelope["householdId"]),
                causation_id=str(envelope["eventId"]),
                payload={
                    "jobId": job_id,
                    "contractId": contract_id,
                    "ownerId": owner_id,
                    "comparisonId": result.id,
                    "comparison": comparison,
                },
            ),
        )
        return result

    def _record_llm(
        self,
        *,
        outcome: str,
        duration_s: float,
        usage: dict[str, Any] | None = None,
    ) -> None:
        if self._llm_metrics is None:
            return
        usage = usage or {}
        provider = str(usage.get("provider") or os.getenv("LLM_PROVIDER") or "mock")
        model = str(usage.get("model") or provider)
        self._llm_metrics.record(
            provider=provider,
            model=model,
            outcome=outcome,
            duration_s=duration_s,
            input_tokens=int(usage.get("inputTokens") or 0),
            output_tokens=int(usage.get("outputTokens") or 0),
            retries=int(usage.get("retries") or 0),
        )

    async def publish_terminal_failure(self, raw_event: Any, error_message: str) -> None:
        validated = validate_event(raw_event)
        if not validated["ok"]:
            return
        envelope = validated["event"]
        payload = envelope.get("payload") or {}
        await self._publish_failure(
            envelope,
            job_id=str(payload.get("jobId") or ""),
            contract_id=str(payload.get("contractId") or ""),
            owner_id=str(payload.get("ownerId") or ""),
            error_message=error_message,
        )

    async def _publish_failure(
        self,
        envelope: dict[str, Any],
        *,
        job_id: str,
        contract_id: str,
        owner_id: str,
        error_message: str,
    ) -> None:
        try:
            await self._publisher.publish(
                "comparison.failed.v1",
                build_envelope(
                    event_type="comparison.failed.v1",
                    correlation_id=str(envelope["correlationId"]),
                    household_id=str(envelope["householdId"]),
                    causation_id=str(envelope["eventId"]),
                    payload={
                        "jobId": job_id,
                        "contractId": contract_id,
                        "ownerId": owner_id,
                        "errorMessage": error_message[:2000],
                    },
                ),
            )
        except Exception:  # noqa: BLE001
            logger.exception("Failed to publish comparison.failed.v1")
