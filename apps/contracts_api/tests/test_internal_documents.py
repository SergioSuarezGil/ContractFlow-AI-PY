import base64
import os

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
)
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


def _headers() -> dict[str, str]:
    return {"X-Owner-Id": "user-a", "X-Household-Id": "hh-a"}


def test_internal_document_requires_token(client: TestClient) -> None:
    created = client.post(
        "/api/v1/contracts",
        json={"serviceType": "electricity", "providerName": "Acme", "title": "Home"},
        headers=_headers(),
    )
    contract_id = created.json()["id"]
    uploaded = client.post(
        f"/api/v1/contracts/{contract_id}/documents",
        data={"role": "current"},
        files={"file": ("c.txt", b"Price: 55", "text/plain")},
        headers=_headers(),
    )
    doc_id = uploaded.json()["id"]

    denied = client.get(f"/internal/v1/documents/{doc_id}")
    assert denied.status_code == 401

    ok = client.get(
        f"/internal/v1/documents/{doc_id}",
        headers={"X-Internal-Token": "dev-internal"},
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body["id"] == doc_id
    assert body["role"] == "current"
    assert base64.b64decode(body["bodyBase64"]) == b"Price: 55"


def test_internal_document_404(client: TestClient) -> None:
    missing = client.get(
        "/internal/v1/documents/does-not-exist",
        headers={"X-Internal-Token": "dev-internal"},
    )
    assert missing.status_code == 404
