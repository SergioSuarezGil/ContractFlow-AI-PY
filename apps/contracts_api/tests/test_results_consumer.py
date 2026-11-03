import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from contracts_api.domain.job import Job, OutboxEvent
from contracts_api.infrastructure.messaging.results_consumer import ResultsEventApplier
from contracts_api.infrastructure.persistence.memory_job_repository import (
    InMemoryJobRepository,
)
from contracts_api.infrastructure.persistence.memory_report_repository import (
    InMemoryReportRepository,
)


def _envelope(event_type: str, payload: dict) -> dict:
    return {
        "eventId": str(uuid4()),
        "eventType": event_type,
        "schemaVersion": 1,
        "correlationId": str(uuid4()),
        "causationId": None,
        "householdId": "hh_demo",
        "occurredAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "payload": payload,
    }


def test_results_applier_completes_job() -> None:
    jobs = InMemoryJobRepository()
    reports = InMemoryReportRepository()
    job_id = str(uuid4())
    job = Job.create(
        id=job_id,
        contract_id="c1",
        household_id="hh_demo",
        owner_id="demo",
        correlation_id=str(uuid4()),
        outbox=OutboxEvent(routing_key="comparison.requested.v1", envelope={}),
    )
    job.mark_outbox_published()
    asyncio.run(jobs.save(job))

    applier = ResultsEventApplier(jobs, reports)
    comparison_id = "cmp-" + job_id[:8]
    asyncio.run(
        applier.apply(
            _envelope(
                "comparison.completed.v1",
                {
                    "jobId": job_id,
                    "contractId": "c1",
                    "ownerId": "demo",
                    "comparisonId": comparison_id,
                    "verdict": "better",
                    "comparison": {
                        "id": comparison_id,
                        "jobId": job_id,
                        "contractId": "c1",
                        "verdict": "better",
                        "summary": "ok",
                        "priceNotes": "",
                        "coverageNotes": "",
                        "risks": [],
                        "disclaimer": "info",
                        "createdAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                    },
                },
            )
        )
    )
    mid = asyncio.run(jobs.find_by_id(job_id))
    assert mid is not None
    assert mid.status == "PROCESSING"
    assert mid.comparison_id == comparison_id

    report_id = "rep-" + job_id[:8]
    asyncio.run(
        applier.apply(
            _envelope(
                "report.completed.v1",
                {
                    "jobId": job_id,
                    "contractId": "c1",
                    "ownerId": "demo",
                    "comparisonId": comparison_id,
                    "reportId": report_id,
                    "storageKey": f"reports/{job_id}.pdf",
                    "fileName": f"{report_id}.pdf",
                    "contentType": "application/pdf",
                    "sizeBytes": 1234,
                },
            )
        )
    )
    done = asyncio.run(jobs.find_by_id(job_id))
    assert done is not None
    assert done.status == "COMPLETED"
    assert done.report_id == report_id
    assert asyncio.run(reports.find_by_id(report_id)) is not None
