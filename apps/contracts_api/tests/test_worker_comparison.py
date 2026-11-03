import os

from fastapi.testclient import TestClient

os.environ["AUTH_MODE"] = "dev"
os.environ["CONTRACTS_REPO"] = "memory"
os.environ["OBJECT_STORAGE"] = "memory"
os.environ["MESSAGING"] = "noop"
os.environ["AI_WORKER_GRPC_TARGET"] = ""

from contractflow_shared import get_settings  # noqa: E402
from contracts_api.main import app  # noqa: E402


def test_worker_comparison_without_grpc_is_not_found_view() -> None:
    get_settings.cache_clear()
    headers = {"X-Owner-Id": "demo", "X-Household-Id": "hh_demo"}
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/contracts",
            json={"serviceType": "electricity", "providerName": "Acme", "title": "Home"},
            headers=headers,
        )
        assert created.status_code == 201
        contract_id = created.json()["id"]
        current = client.post(
            f"/api/v1/contracts/{contract_id}/documents",
            headers=headers,
            files={"file": ("current.txt", b"Price: 55 monthly", "text/plain")},
            data={"role": "current"},
        )
        proposal = client.post(
            f"/api/v1/contracts/{contract_id}/documents",
            headers=headers,
            files={"file": ("proposal.txt", b"Price: 40 monthly", "text/plain")},
            data={"role": "proposal"},
        )
        assert current.status_code == 201
        assert proposal.status_code == 201
        job = client.post(f"/api/v1/contracts/{contract_id}/comparisons", headers=headers)
        assert job.status_code == 202
        job_id = job.json()["jobId"]
        lookup = client.get(f"/api/v1/jobs/{job_id}/worker-comparison", headers=headers)
        assert lookup.status_code == 200
        body = lookup.json()
        assert body["jobId"] == job_id
        assert body["worker"]["found"] is False
        missing = client.get("/api/v1/jobs/missing/worker-comparison", headers=headers)
        assert missing.status_code == 404
    get_settings.cache_clear()
