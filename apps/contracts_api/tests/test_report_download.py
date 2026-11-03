import base64
import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

os.environ["AUTH_MODE"] = "dev"
os.environ["ENVIRONMENT"] = "test"
os.environ["CONTRACTS_REPO"] = "memory"
os.environ["MESSAGING"] = "noop"
os.environ["OUTBOX_ENABLED"] = "true"
os.environ["INTERNAL_API_TOKEN"] = "dev-internal"

from contractflow_shared import get_settings  # noqa: E402
from contracts_api.deps import (  # noqa: E402
    get_memory_contract_repository,
    get_memory_document_repository,
    get_memory_job_repository,
    get_memory_report_repository,
    get_memory_storage,
    get_noop_publisher,
    get_results_applier,
)
from contracts_api.domain.job import Job, OutboxEvent  # noqa: E402
from contracts_api.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def _reset() -> None:
    get_settings.cache_clear()
    get_memory_contract_repository().clear()
    get_memory_document_repository().clear()
    get_memory_job_repository().clear()
    get_memory_report_repository().clear()
    get_memory_storage().clear()
    get_noop_publisher().clear()
    yield
    get_memory_contract_repository().clear()
    get_memory_document_repository().clear()
    get_memory_job_repository().clear()
    get_memory_report_repository().clear()
    get_memory_storage().clear()
    get_noop_publisher().clear()
    get_settings.cache_clear()


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def test_internal_put_then_download_report(client: TestClient) -> None:
    import asyncio

    job_id = str(uuid4())
    report_id = "rep-" + job_id[:8]
    comparison_id = "cmp-" + job_id[:8]
    job = Job.create(
        id=job_id,
        contract_id="c1",
        household_id="hh-a",
        owner_id="user-a",
        correlation_id=str(uuid4()),
        outbox=OutboxEvent(routing_key="comparison.requested.v1", envelope={}),
    )
    job.mark_outbox_published()
    job.mark_comparison_completed(comparison_id)
    asyncio.run(get_memory_job_repository().save(job))

    pdf_bytes = b"%PDF-1.4 demo report"
    put = client.put(
        f"/internal/v1/reports/{report_id}",
        headers={"X-Internal-Token": "dev-internal"},
        json={
            "jobId": job_id,
            "contractId": "c1",
            "ownerId": "user-a",
            "householdId": "hh-a",
            "comparisonId": comparison_id,
            "fileName": f"{report_id}.pdf",
            "contentType": "application/pdf",
            "storageKey": f"reports/{job_id}/{report_id}.pdf",
            "bodyBase64": base64.b64encode(pdf_bytes).decode("ascii"),
        },
    )
    assert put.status_code == 200

    asyncio.run(
        get_results_applier().apply(
            {
                "eventId": str(uuid4()),
                "eventType": "report.completed.v1",
                "schemaVersion": 1,
                "correlationId": str(uuid4()),
                "causationId": None,
                "householdId": "hh-a",
                "occurredAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "payload": {
                    "jobId": job_id,
                    "contractId": "c1",
                    "ownerId": "user-a",
                    "comparisonId": comparison_id,
                    "reportId": report_id,
                    "storageKey": f"reports/{job_id}/{report_id}.pdf",
                    "fileName": f"{report_id}.pdf",
                    "contentType": "application/pdf",
                    "sizeBytes": len(pdf_bytes),
                },
            }
        )
    )

    downloaded = client.get(
        f"/api/v1/jobs/{job_id}/report",
        headers={"X-Owner-Id": "user-a", "X-Household-Id": "hh-a"},
    )
    assert downloaded.status_code == 200
    assert downloaded.content.startswith(b"%PDF")
    assert downloaded.headers["content-type"].startswith("application/pdf")

    meta = client.get(
        f"/api/v1/reports/{report_id}",
        headers={"X-Owner-Id": "user-a", "X-Household-Id": "hh-a"},
    )
    assert meta.status_code == 200
    body = meta.json()
    assert body["id"] == report_id
    assert body["jobId"] == job_id
    assert body["contractId"] == "c1"
    assert body["fileName"] == f"{report_id}.pdf"
    assert "createdAt" in body

    pdf = client.get(
        f"/api/v1/reports/{report_id}/download",
        headers={"X-Owner-Id": "user-a", "X-Household-Id": "hh-a"},
    )
    assert pdf.status_code == 200
    assert pdf.content == pdf_bytes
    assert "attachment;" in pdf.headers["content-disposition"]

    missing = client.get(
        "/api/v1/reports/missing",
        headers={"X-Owner-Id": "user-a", "X-Household-Id": "hh-a"},
    )
    assert missing.status_code == 404
    err = missing.json()
    assert err["statusCode"] == 404
    assert err["error"] == "NotFoundError"
    assert "message" in err
