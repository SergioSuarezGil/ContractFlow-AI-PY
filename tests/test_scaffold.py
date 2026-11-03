from contractflow_shared import get_settings
from contracts_api.main import app
from fastapi.testclient import TestClient


def test_settings_default_llm_is_mock() -> None:
    get_settings.cache_clear()
    settings = get_settings()
    assert settings.llm_provider == "mock"
    assert settings.app_name == "contractflow-ai-py"


def test_contracts_api_health() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "contracts-api"
