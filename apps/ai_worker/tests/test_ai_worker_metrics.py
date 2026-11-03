import os

from fastapi.testclient import TestClient

os.environ["DOCUMENT_SOURCE"] = "memory"
os.environ["COMPARISON_STORE"] = "memory"
os.environ["MESSAGING"] = "noop"
os.environ["AI_WORKER_CONSUME"] = "false"
os.environ["AI_WORKER_GRPC_ENABLED"] = "false"
os.environ.pop("CONTRACTS_API_INTERNAL_URL", None)

from ai_worker.main import app  # noqa: E402


def test_metrics_exposes_llm_and_process() -> None:
    with TestClient(app) as client:
        response = client.get("/metrics")
    assert response.status_code == 200
    assert "contractflow_process_up" in response.text
    assert "contractflow_llm_requests_total" in response.text
