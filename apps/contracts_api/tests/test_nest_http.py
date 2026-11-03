import os

import pytest
from fastapi.testclient import TestClient

os.environ["AUTH_MODE"] = "dev"
os.environ["ENVIRONMENT"] = "test"
os.environ["CONTRACTS_REPO"] = "memory"
os.environ["MESSAGING"] = "noop"
os.environ["OUTBOX_ENABLED"] = "true"

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
    get_settings.cache_clear()


def test_validation_error_is_422_with_nest_shape() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/contracts",
            json={"serviceType": "electricity", "providerName": "Acme", "title": ""},
        )
    assert response.status_code == 422
    body = response.json()
    assert body["statusCode"] == 422
    assert body["error"] == "Unprocessable Entity"
    assert body["message"]


def test_health_includes_build_identity_and_metrics_increment() -> None:
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["version"]["gitSha"]
        created = client.post(
            "/api/v1/contracts",
            json={"serviceType": "gas", "providerName": "Acme", "title": "Home"},
        )
        assert created.status_code == 201
        metrics = client.get("/metrics")
    text = metrics.text
    assert "contractflow_http_requests_total" in text
    assert "contractflow_http_request_duration_seconds" in text
    assert 'route="/api/v1/contracts"' in text
    assert "process_cpu_seconds_total" in text
    assert "python_info" in text
