from contractflow_observability.build_info import get_build_info
from contractflow_observability.llm_metrics import LlmMetrics, estimate_llm_cost_usd
from contractflow_observability.metrics import create_service_metrics
from prometheus_client import generate_latest


def test_build_info_defaults(monkeypatch) -> None:
    monkeypatch.delenv("APP_SERVICE_NAME", raising=False)
    monkeypatch.delenv("APP_GIT_SHA", raising=False)
    info = get_build_info("ai-worker")
    assert info.service == "ai-worker"
    assert info.git_sha == "unknown"


def test_llm_metrics_render() -> None:
    metrics = create_service_metrics("ai-worker")
    llm = LlmMetrics(metrics.registry)
    llm.record(
        provider="mock",
        model="mock",
        outcome="success",
        duration_s=0.01,
        input_tokens=12,
        output_tokens=4,
        retries=1,
    )
    text = generate_latest(metrics.registry).decode()
    assert "contractflow_process_up" in text
    assert "contractflow_llm_requests_total" in text
    assert estimate_llm_cost_usd("mock", 1000, 1000) == 0
