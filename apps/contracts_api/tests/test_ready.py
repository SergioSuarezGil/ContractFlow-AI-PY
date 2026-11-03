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


def test_ready_noop_messaging() -> None:
    with TestClient(app) as client:
        response = client.get("/ready")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["version"]["gitSha"]
        assert body["checks"]["rabbitmq"]["status"] == "skipped"
        assert body["checks"]["mongodb"]["status"] == "skipped"
        ready = client.get("/health/ready")
        assert ready.status_code == 200
        assert ready.json()["checks"]["outbox"]["status"] == "up"
