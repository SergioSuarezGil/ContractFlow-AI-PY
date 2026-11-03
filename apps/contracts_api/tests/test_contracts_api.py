import os

import pytest
from fastapi.testclient import TestClient

# Force test-safe auth before app settings cache is used.
os.environ["AUTH_MODE"] = "dev"
os.environ["ENVIRONMENT"] = "test"
os.environ["CONTRACTS_REPO"] = "memory"

from contractflow_shared import get_settings  # noqa: E402
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


def test_health_reports_dev_auth(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["authMode"] == "dev"


def test_create_list_get_contract(client: TestClient) -> None:
    created = client.post(
        "/api/v1/contracts",
        json={
            "serviceType": "electricity",
            "providerName": "Acme",
            "title": "Home power",
            "notes": "demo",
        },
        headers={"X-Owner-Id": "user-a", "X-Household-Id": "hh-a"},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["serviceType"] == "electricity"
    assert body["ownerId"] == "user-a"
    assert body["status"] == "draft"
    contract_id = body["id"]

    listed = client.get(
        "/api/v1/contracts",
        headers={"X-Owner-Id": "user-a", "X-Household-Id": "hh-a"},
    )
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    fetched = client.get(
        f"/api/v1/contracts/{contract_id}",
        headers={"X-Owner-Id": "user-a", "X-Household-Id": "hh-a"},
    )
    assert fetched.status_code == 200
    assert fetched.json()["title"] == "Home power"


def test_isolation_hides_foreign_contract(client: TestClient) -> None:
    created = client.post(
        "/api/v1/contracts",
        json={
            "serviceType": "gas",
            "providerName": "GasCo",
            "title": "Kitchen",
        },
        headers={"X-Owner-Id": "user-a", "X-Household-Id": "hh-a"},
    )
    contract_id = created.json()["id"]

    foreign = client.get(
        f"/api/v1/contracts/{contract_id}",
        headers={"X-Owner-Id": "user-b", "X-Household-Id": "hh-b"},
    )
    assert foreign.status_code == 404


def test_archive_contract(client: TestClient) -> None:
    created = client.post(
        "/api/v1/contracts",
        json={
            "serviceType": "mobile",
            "providerName": "Telco",
            "title": "Phone",
        },
        headers={"X-Owner-Id": "user-a", "X-Household-Id": "hh-a"},
    )
    contract_id = created.json()["id"]
    archived = client.delete(
        f"/api/v1/contracts/{contract_id}",
        headers={"X-Owner-Id": "user-a", "X-Household-Id": "hh-a"},
    )
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
