"""In-process interview-spine: API → analyze → PDF → job COMPLETED (noop bus)."""

from __future__ import annotations

import asyncio
import os

import pytest
from fastapi.testclient import TestClient

os.environ["AUTH_MODE"] = "dev"
os.environ["ENVIRONMENT"] = "test"
os.environ["CONTRACTS_REPO"] = "memory"
os.environ["MESSAGING"] = "noop"
os.environ["OUTBOX_ENABLED"] = "true"
os.environ["LLM_PROVIDER"] = "mock"

from ai_worker.application.comparison_handler import ComparisonRequestedHandler
from ai_worker.application.comparison_pipeline import ComparisonPipeline
from ai_worker.application.types import SourceDocument
from ai_worker.infrastructure.event_publisher import NoopEventPublisher as AiPublisher
from ai_worker.infrastructure.idempotency import InMemoryIdempotencyStore
from ai_worker.infrastructure.llm.mock_analyzer import MockContractAnalyzer
from ai_worker.infrastructure.memory_document_source import InMemoryDocumentSource
from contractflow_shared import get_settings  # noqa: E402
from contracts_api.application.outbox_relay import OutboxRelay  # noqa: E402
from contracts_api.deps import (  # noqa: E402
    get_memory_contract_repository,
    get_memory_document_repository,
    get_memory_job_repository,
    get_memory_report_repository,
    get_memory_storage,
    get_noop_publisher,
    get_results_applier,
)
from contracts_api.main import app  # noqa: E402
from pdf_worker.application.report_handler import ReportRequestedHandler
from pdf_worker.infrastructure.memory_storage import InMemoryObjectStorage as PdfStorage
from pdf_worker.infrastructure.publisher import NoopEventPublisher as PdfPublisher


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


def _headers() -> dict[str, str]:
    return {"X-Owner-Id": "user-a", "X-Household-Id": "hh-a"}


def test_spine_e2e_mock_pipeline_completes_job() -> None:
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/contracts",
            json={
                "serviceType": "electricity",
                "providerName": "Acme",
                "title": "Home power",
            },
            headers=_headers(),
        )
        assert created.status_code == 201
        contract_id = created.json()["id"]

        assert (
            client.post(
                f"/api/v1/contracts/{contract_id}/documents",
                data={"role": "current"},
                files={"file": ("current.txt", b"Price: 55 monthly", "text/plain")},
                headers=_headers(),
            ).status_code
            == 201
        )
        assert (
            client.post(
                f"/api/v1/contracts/{contract_id}/documents",
                data={"role": "proposal"},
                files={
                    "file": (
                        "proposal.txt",
                        b"Price: 40 monthly\ncoverage: green energy",
                        "text/plain",
                    )
                },
                headers=_headers(),
            ).status_code
            == 201
        )

        accepted = client.post(
            f"/api/v1/contracts/{contract_id}/comparisons",
            headers=_headers(),
        )
        assert accepted.status_code == 202
        job_id = accepted.json()["jobId"]

        relay = OutboxRelay(
            get_memory_job_repository(),
            get_noop_publisher(),
            interval_ms=50,
        )
        asyncio.run(relay.drain())
        outbox_events = get_noop_publisher().published
        assert outbox_events
        requested = next(
            env for key, env in outbox_events if key == "comparison.requested.v1"
        )

        docs = asyncio.run(
            get_memory_document_repository().list_by_contract(contract_id)
        )
        source = InMemoryDocumentSource()
        storage = get_memory_storage()
        for doc in docs:
            body = storage.get(bucket="documents", key=doc.storage_key)
            assert body is not None
            source.put(
                SourceDocument(
                    document_id=doc.id,
                    file_name=doc.file_name,
                    role=doc.role,
                    content_type=doc.content_type,
                    body=body,
                )
            )

        ai_publisher = AiPublisher()
        comparison = asyncio.run(
            ComparisonRequestedHandler(
                ComparisonPipeline(source, analyzer=MockContractAnalyzer()),
                InMemoryIdempotencyStore(),
                publisher=ai_publisher,
            ).handle(requested)
        )
        assert comparison is not None
        assert comparison.verdict == "better"

        completed_cmp = next(
            env for key, env in ai_publisher.published if key == "comparison.completed.v1"
        )
        report_req = next(
            env for key, env in ai_publisher.published if key == "report.requested.v1"
        )

        pdf_publisher = PdfPublisher()
        pdf_storage = PdfStorage()
        report_payload = asyncio.run(
            ReportRequestedHandler(
                storage=pdf_storage, publisher=pdf_publisher
            ).handle(report_req)
        )
        assert report_payload is not None
        assert report_payload["sizeBytes"] > 0
        assert any(v.startswith(b"%PDF") for v in pdf_storage.objects.values())

        report_done = next(
            env for key, env in pdf_publisher.published if key == "report.completed.v1"
        )

        applier = get_results_applier()
        asyncio.run(applier.apply(completed_cmp))
        asyncio.run(applier.apply(report_done))

        job = client.get(f"/api/v1/jobs/{job_id}", headers=_headers())
        assert job.status_code == 200
        body = job.json()
        assert body["status"] == "COMPLETED"
        assert body["comparisonId"]
        assert body["reportId"]

        metrics = client.get("/metrics")
        assert metrics.status_code == 200
        assert "contractflow_" in metrics.text
