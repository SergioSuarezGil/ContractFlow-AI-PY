import os

import pytest
from fastapi.testclient import TestClient

os.environ["AUTH_MODE"] = "dev"
os.environ["ENVIRONMENT"] = "test"
os.environ["CONTRACTS_REPO"] = "memory"
os.environ["MESSAGING"] = "noop"
os.environ["OUTBOX_ENABLED"] = "true"

from contractflow_shared import get_settings  # noqa: E402
from contracts_api.application.outbox_relay import OutboxRelay  # noqa: E402
from contracts_api.deps import (  # noqa: E402
    get_memory_contract_repository,
    get_memory_document_repository,
    get_memory_job_repository,
    get_memory_storage,
    get_noop_publisher,
)
from contracts_api.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    get_settings.cache_clear()
    get_memory_contract_repository().clear()
    get_memory_document_repository().clear()
    get_memory_job_repository().clear()
    get_memory_storage().clear()
    get_noop_publisher().clear()
    yield
    get_memory_contract_repository().clear()
    get_memory_document_repository().clear()
    get_memory_job_repository().clear()
    get_memory_storage().clear()
    get_noop_publisher().clear()
    get_settings.cache_clear()


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def _headers() -> dict[str, str]:
    return {"X-Owner-Id": "user-a", "X-Household-Id": "hh-a"}


def _create_contract(client: TestClient) -> str:
    response = client.post(
        "/api/v1/contracts",
        json={
            "serviceType": "electricity",
            "providerName": "Acme",
            "title": "Home power",
        },
        headers=_headers(),
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_upload_documents_and_request_comparison(client: TestClient) -> None:
    contract_id = _create_contract(client)

    current = client.post(
        f"/api/v1/contracts/{contract_id}/documents",
        data={"role": "current"},
        files={"file": ("current.txt", b"Price: 55 monthly", "text/plain")},
        headers=_headers(),
    )
    assert current.status_code == 201
    assert current.json()["role"] == "current"

    proposal = client.post(
        f"/api/v1/contracts/{contract_id}/documents",
        data={"role": "proposal"},
        files={"file": ("proposal.txt", b"Price: 42 monthly", "text/plain")},
        headers=_headers(),
    )
    assert proposal.status_code == 201

    listed = client.get(
        f"/api/v1/contracts/{contract_id}/documents",
        headers=_headers(),
    )
    assert listed.status_code == 200
    assert len(listed.json()) == 2

    accepted = client.post(
        f"/api/v1/contracts/{contract_id}/comparisons",
        headers=_headers(),
    )
    assert accepted.status_code == 202
    body = accepted.json()
    assert body["status"] == "PENDING"
    job_id = body["jobId"]

    job = client.get(f"/api/v1/jobs/{job_id}", headers=_headers())
    assert job.status_code == 200
    assert job.json()["id"] == job_id
    assert job.json()["status"] in {"PENDING", "PROCESSING"}


def test_outbox_relay_publishes_noop() -> None:
    import asyncio

    from contracts_api.application.actor import ActorContext
    from contracts_api.application.contracts_service import ContractsService
    from contracts_api.application.documents_service import DocumentsService
    from contracts_api.application.jobs_service import JobsService

    async def _run() -> None:
        actor = ActorContext(owner_id="user-a", household_id="hh-a")
        contracts = ContractsService(get_memory_contract_repository())
        documents = DocumentsService(
            get_memory_contract_repository(),
            get_memory_document_repository(),
            get_memory_storage(),
        )
        jobs = JobsService(
            get_memory_contract_repository(), get_memory_job_repository()
        )

        contract = await contracts.create(
            actor,
            service_type="electricity",
            provider_name="Acme",
            title="Home",
        )
        await documents.attach(
            actor,
            contract_id=contract.id,
            role="current",
            file_name="c.txt",
            content_type="text/plain",
            body=b"Price: 1",
        )
        await documents.attach(
            actor,
            contract_id=contract.id,
            role="proposal",
            file_name="p.txt",
            content_type="text/plain",
            body=b"Price: 2",
        )
        accepted = await jobs.request_comparison(actor, contract.id)
        publisher = get_noop_publisher()
        relay = OutboxRelay(get_memory_job_repository(), publisher, interval_ms=100)
        await relay.drain()
        assert len(publisher.published) == 1
        routing_key, envelope = publisher.published[0]
        assert routing_key == "comparison.requested.v1"
        assert envelope["payload"]["jobId"] == accepted["jobId"]
        stored = await get_memory_job_repository().find_by_id(accepted["jobId"])
        assert stored is not None
        assert stored.outbox is not None
        assert stored.outbox.published_at is not None
        assert stored.status == "PROCESSING"

    asyncio.run(_run())
