import os

from fastapi.testclient import TestClient

os.environ["PDF_STORAGE"] = "memory"
os.environ["MESSAGING"] = "noop"
os.environ["PDF_WORKER_CONSUME"] = "false"
os.environ.pop("CONTRACTS_API_INTERNAL_URL", None)

from pdf_worker.main import app  # noqa: E402


def test_pdf_metrics() -> None:
    with TestClient(app) as client:
        response = client.get("/metrics")
    assert response.status_code == 200
    assert "contractflow_process_up" in response.text
    assert "pdf-worker" in response.text
